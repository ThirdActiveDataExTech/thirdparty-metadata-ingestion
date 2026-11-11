"""외부 모듈 실행 — 데이터셋 메타데이터를 모아 모듈에 넘기고, 원하면 결과를 특징으로 남긴다 (C7).

"외부 모듈을 연계한 데이터 분석과 메타데이터 수집": 결과를 `meta_feature`에
`external_<작업>`(method `external:<모듈>`)으로 저장하면 상세 화면·패키지 특징에 함께 실린다.
저장은 호출자가 `save=True`일 때만 — 대체(degraded) 결과는 저장하지 않는다(누가 만든 값인지 흐려진다).
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.external import modules as X

SAMPLE_ITEMS = 20


def dataset_context(dataset_id: str, samples: int = SAMPLE_ITEMS) -> Tuple[Dict[str, Any], bool]:
    """(모듈에 넘길 메타데이터, 외부 반출 가능 여부). 항목 예시는 제목만 — 본문은 넘기지 않는다."""
    from src.database.db import get_conn
    from src.export import policy

    cur = get_conn().cursor()
    cur.execute("SELECT d.title, d.description, d.keywords, d.source_type, d.visibility, d.license, "
                "       d.publisher, r.pg_meta_table "
                "FROM dcat_dataset d LEFT JOIN data_registry r USING (dataset_id) WHERE d.dataset_id = %s",
                (dataset_id,))
    row = cur.fetchone()
    if not row:
        raise X.ModuleError("데이터셋을 찾을 수 없습니다", 404)
    title, desc, kws, st, vis, lic, pub, table = row
    if isinstance(kws, str):
        kws = json.loads(kws)
    titles = []
    if table and re.match(r"^[a-z][a-z0-9_]*$", table):
        cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = 'title'",
                    (table,))
        if cur.fetchone():
            cur.execute(f"SELECT title FROM {table} WHERE dataset_id = %s AND title IS NOT NULL "
                        f"ORDER BY title LIMIT %s", (dataset_id, samples))
            titles = [t for (t,) in cur.fetchall() if t]
    ctx = {"dataset_id": dataset_id, "title": title, "description": desc or "", "keywords": list(kws or [])[:20],
           "publisher": pub, "source_type": st, "samples": titles}
    return ctx, policy.eligibility(st, vis, lic).allowed


def run(name: str, task: str, dataset_id: str, question: str = "", save: bool = False,
        specs: Optional[Dict[str, X.ModuleSpec]] = None) -> Dict[str, Any]:
    specs = specs if specs is not None else X.load_all()
    ctx, export_ok = dataset_context(dataset_id)
    res = X.invoke(specs, name, task, ctx, question=question, export_allowed=export_ok)
    res["dataset_id"] = dataset_id
    res["saved"] = False
    if save and res["ok"] and not res["degraded"] and task in ("summarize", "keywords", "describe"):
        from src.database.db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        value = {"module": res["module"], "output": res["output"],
                 "generated_at": datetime.now(timezone.utc).isoformat()}
        cur.execute("INSERT INTO meta_feature (dataset_id, scope, target, feature_name, value, method) "
                    "VALUES (%s, 'dataset', '', %s, %s::jsonb, %s) "
                    "ON CONFLICT (dataset_id, scope, target, feature_name) DO UPDATE SET "
                    "value = EXCLUDED.value, method = EXCLUDED.method, computed_at = now()",
                    (dataset_id, f"external_{task}", json.dumps(value, ensure_ascii=False),
                     f"external:{res['module']}"))
        conn.commit()
        res["saved"] = True
    return res
