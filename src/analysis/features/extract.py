"""특징 추출 실행 — DB에서 모아 계산하고 meta_feature에 쓴다 (B1).

**토큰 집계는 DB에서 한다.** `token_text`를 전부 파이썬으로 끌어오면 163,407청크
분의 문자열이 넘어온다. `unnest(string_to_array(...))`로 서버에서 접으면
(dataset_id, 토큰, 빈도)만 온다.

**TF-IDF는 전체를 한 번에 계산한다.** IDF가 "다른 데이터셋에도 나오는가"이므로
데이터셋 하나만 떼어 계산할 수 없다. 그래서 `--dataset` 옵션을 줘도 집계는 전부
읽고 **저장만** 그 데이터셋에 한다.
"""

import logging
from collections import Counter
from typing import Dict, List, Optional

from psycopg2.extras import Json, execute_values

from src.analysis.features import stats, text
from src.analysis.features.sources import CATALOG_VEC, SPECS
from src.database.db import get_conn
from src.search import tokenize

logger = logging.getLogger(__name__)


def _datasets(cur) -> List[tuple]:
    cur.execute("SELECT dataset_id, source_type, title FROM dcat_dataset ORDER BY dataset_id")
    return cur.fetchall()


def _token_counts(cur) -> List[tuple]:
    """(dataset_id, 토큰, 빈도) — 아이템 청크 + 카탈로그 청크를 합쳐 센다.

    원천마다 vec 테이블이 달라 UNION ALL로 잇는다. shopping/persona는 아이템
    청크 테이블이 없어 카탈로그 쪽만 기여한다.
    """
    parts = []
    for src, spec in SPECS.items():
        if spec.vec:
            parts.append(
                f"SELECT b.dataset_id, v.token_text "
                f"FROM {spec.vec} v JOIN {spec.base} b ON b.{spec.base_key} = v.{spec.key} "
                f"WHERE v.token_text <> ''"
            )
    parts.append(f"SELECT dataset_id, token_text FROM {CATALOG_VEC} WHERE token_text <> ''")

    cur.execute(f"""
        WITH src AS ({' UNION ALL '.join(parts)})
        SELECT s.dataset_id, t.word, count(*)::int
        FROM   src s, unnest(string_to_array(s.token_text, ' ')) AS t(word)
        WHERE  t.word <> ''
        GROUP  BY 1, 2
    """)
    return cur.fetchall()


def _chunks_for(cur, dataset_id: str, source_type: str, limit: int = 4000):
    """대표 문장 후보. 전부 읽을 필요가 없어 상한을 둔다."""
    spec = SPECS.get(source_type)
    if not spec or not spec.vec:
        cur.execute(f"SELECT embed_text, token_text FROM {CATALOG_VEC} "
                    f"WHERE dataset_id = %s AND token_text <> ''", (dataset_id,))
        return cur.fetchall()
    cur.execute(
        f"SELECT v.embed_text, v.token_text "
        f"FROM {spec.vec} v JOIN {spec.base} b ON b.{spec.base_key} = v.{spec.key} "
        f"WHERE b.dataset_id = %s AND v.token_text <> '' LIMIT %s",
        (dataset_id, limit))
    return cur.fetchall()


def _raw_stats(cur, dataset_id: str, source_type: str) -> Dict:
    """기술통계 재료를 원천별로 긁어온다."""
    spec = SPECS.get(source_type)
    out: Dict = {}
    if spec is None:
        return out

    content_col = "has_content" if spec.has_content else None
    cols = ["count(*)"]
    if content_col:
        cols.append(f"count(*) FILTER (WHERE {content_col})")
    cur.execute(f"SELECT {', '.join(cols)} FROM {spec.base} WHERE dataset_id = %s", (dataset_id,))
    row = cur.fetchone()
    out["item_count"] = row[0]
    if content_col:
        out["with_content"] = row[1]

    if spec.vec:
        cur.execute(
            f"SELECT count(*), coalesce(array_agg(length(v.embed_text)), '{{}}') "
            f"FROM {spec.vec} v JOIN {spec.base} b ON b.{spec.base_key} = v.{spec.key} "
            f"WHERE b.dataset_id = %s", (dataset_id,))
        cnt, lens = cur.fetchone()
        out["chunk_count"] = cnt
        out["lengths"] = lens

    # 관측 기간은 **지표 시계열에서 직접 센다.** data_registry.temporal_*는 원천
    # 데이터의 수록 기간이고, 여기서 알고 싶은 것은 "우리가 몇 번 관측했나"다.
    # 발견형 소스가 1일뿐인 것을 드러내는 수치라 특징으로 남길 값어치가 있다
    # (P0-7, docs/database/metadata_quality_probe.md).
    cur.execute(
        f"SELECT min(a.{spec.time_col})::date, max(a.{spec.time_col})::date, "
        f"       count(DISTINCT a.{spec.time_col}::date) "
        f"FROM {spec.active} a JOIN {spec.base} b ON b.{spec.base_key} = a.meta_id "
        f"WHERE b.dataset_id = %s", (dataset_id,))
    lo, hi, days = cur.fetchone()
    out["period_start"], out["period_end"], out["observed_days"] = lo, hi, days
    return out


def extract(dataset_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, int]:
    """특징을 계산해 meta_feature에 upsert한다."""
    conn = get_conn()
    cur = conn.cursor()
    method = f"tfidf/{tokenize.version()}"

    datasets = _datasets(cur)
    logger.info("데이터셋 %d개 — 토큰 집계 중…", len(datasets))
    counts = _token_counts(cur)
    logger.info("토큰 (데이터셋,단어) 쌍 %d개", len(counts))

    tf: Dict[str, Counter] = {}
    for ds, word, n in counts:
        tf.setdefault(ds, Counter())[word] = n

    keywords = text.tfidf(tf)
    logger.info("TF-IDF 완료 — 키워드가 산출된 데이터셋 %d개", len(keywords))

    payload = []
    targets = [d for d in datasets if dataset_id is None or d[0] == dataset_id]
    for ds, source_type, title in targets:
        rows = stats.build(ds, _raw_stats(cur, ds, source_type))
        vocab = len(tf.get(ds, {}))
        if vocab:
            rows.append({"feature_name": "vocab_size", "value": vocab})

        kws = keywords.get(ds, [])
        if kws:
            rows.append({"feature_name": "top_keywords", "value": kws})
            reps = text.representative_chunks(_chunks_for(cur, ds, source_type), kws)
            if reps:
                rows.append({"feature_name": "representative_text", "value": reps})

        for r in rows:
            payload.append((ds, "dataset", "", r["feature_name"], Json(r["value"]), method))

    if dry_run:
        logger.info("dry-run — %d행을 쓰지 않는다", len(payload))
        return {"datasets": len(targets), "features": len(payload), "written": 0}

    execute_values(
        cur,
        "INSERT INTO meta_feature (dataset_id, scope, target, feature_name, value, method) "
        "VALUES %s "
        "ON CONFLICT (dataset_id, scope, target, feature_name) DO UPDATE "
        "SET value = EXCLUDED.value, method = EXCLUDED.method, computed_at = now()",
        payload, page_size=500, fetch=False)
    conn.commit()
    logger.info("meta_feature %d행 저장 (데이터셋 %d개)", len(payload), len(targets))
    return {"datasets": len(targets), "features": len(payload), "written": len(payload)}
