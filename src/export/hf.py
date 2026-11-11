"""허깅페이스 데이터셋 형식 내려받기 (결정 7, 2026-11-11).

허브에 올리지 않는다 — 사용자가 내려받아 직접 올릴 수 있는 **형식**까지만 만든다.

    <dataset>.zip
      README.md            데이터셋 카드(YAML 머리말 + 설명·출처·라이선스 조건)
      data/metadata.parquet  카탈로그 레코드 1행(DCAT 핵심 필드)
      data/items.parquet     아이템(수집 데이터가 있는 데이터셋만)
      metadata.jsonld        DCAT JSON-LD(C6, 오브젝트 스토리지 내보내기와 같은 형식)

반출 가능 여부는 호출부가 `src/export/policy.py`로 먼저 판정한다 — 여기서는 만들기만 한다.
Parquet 값은 모두 문자열로 맞춘다(JSONB·시각·숫자 혼재 컬럼을 형식 오류 없이 담기 위해).
벡터·바이너리 컬럼은 넣지 않는다.
"""

import json
import re
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from src.export.policy import License

#: 카탈로그 레코드로 내보내는 컬럼(dcat_dataset)
META_COLS = ["dataset_id", "title", "description", "publisher", "source_type", "license",
             "keywords", "theme", "category", "landing_page", "external_ids",
             "temporal_start", "temporal_end", "accrual_periodicity", "updated_at"]

#: 아이템 표에서 빼는 컬럼 형식(pgvector·bytea)
_SKIP_TYPES = {"vector", "bytea"}
_TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _text(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, memoryview)):
        return None
    return str(v)


def _write_parquet(path: Path, names: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    cols = {n: pa.array([_text(r[i]) for r in rows], type=pa.string()) for i, n in enumerate(names)}
    pq.write_table(pa.table(cols), path, compression="zstd")


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)          # JSON 문자열은 YAML 문자열로도 유효하다


def _card(meta: Dict[str, Any], lic: License, item_rows: Optional[int], item_table: Optional[str]) -> str:
    kw = meta.get("keywords") or []
    if isinstance(kw, str):
        try:
            kw = json.loads(kw)
        except ValueError:
            kw = []
    front = ["---", f"license: {lic.hf_id}"]
    if lic.hf_id == "other":
        front += [f"license_name: {_yaml_str(lic.name)}", f"license_link: {lic.link}"]
    front.append(f"pretty_name: {_yaml_str(meta.get('title') or meta['dataset_id'])}")
    tags = [str(k) for k in kw if k][:10]
    if tags:
        front.append("tags:")
        front += [f"- {_yaml_str(t)}" for t in tags]
    front += ["configs:", "- config_name: metadata", "  data_files: data/metadata.parquet"]
    if item_rows is not None:
        front += ["- config_name: items", "  data_files: data/items.parquet", "  default: true"]
    front.append("---")

    body = [
        f"# {meta.get('title') or meta['dataset_id']}", "",
        (meta.get("description") or "").strip(), "",
        "## 출처와 이용 조건", "",
        f"- 데이터셋 ID: `{meta['dataset_id']}`",
        f"- 제공 기관: {meta.get('publisher') or '-'}",
        f"- 라이선스: [{lic.name}]({lic.link})",
        f"- 재배포 조건: {lic.attribution}",
    ]
    if meta.get("landing_page"):
        body.append(f"- 원본 페이지: {meta['landing_page']}")
    body += ["", "## 구성", "",
             "| 파일 | 내용 |", "|---|---|",
             "| `data/metadata.parquet` | 카탈로그 레코드 1행(DCAT 핵심 필드) |"]
    if item_rows is not None:
        body.append(f"| `data/items.parquet` | 아이템 {item_rows}행 (원본 표 `{item_table}`) |")
    body += ["| `metadata.jsonld` | DCAT JSON-LD |", "",
             "모든 값은 문자열로 담았습니다. JSON 값은 JSON 문자열입니다.", "",
             "## 만든 곳", "",
             f"써드파티 액티브 메타데이터 카탈로그(연구개발 시제품)에서 "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}에 내보냈습니다.", ""]
    return "\n".join(front + [""] + body)


def build(conn, dataset_id: str, lic: License, out: Path, jsonld: Dict[str, Any]) -> Dict[str, Any]:
    """zip을 만들고 요약을 돌려준다. 호출부가 반출 가능 여부를 먼저 확인해야 한다."""
    work = out.parent / "hf"
    (work / "data").mkdir(parents=True, exist_ok=True)
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(META_COLS)} FROM dcat_dataset WHERE dataset_id = %s", (dataset_id,))
    row = cur.fetchone()
    if row is None:
        raise LookupError(dataset_id)
    meta = dict(zip(META_COLS, row))
    _write_parquet(work / "data" / "metadata.parquet", META_COLS, [row])

    cur.execute("SELECT pg_meta_table FROM data_registry WHERE dataset_id = %s", (dataset_id,))
    r = cur.fetchone()
    table = r[0] if r and r[0] and _TABLE_RE.match(r[0]) else None
    item_rows: Optional[int] = None
    if table:
        cur.execute("""SELECT column_name, udt_name FROM information_schema.columns
                       WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position""",
                    (table,))
        cols: List[str] = [c for c, t in cur.fetchall() if t not in _SKIP_TYPES]
        if cols:
            cur.execute(f"SELECT {', '.join(cols)} FROM {table} WHERE dataset_id = %s", (dataset_id,))
            rows = cur.fetchall()
            _write_parquet(work / "data" / "items.parquet", cols, rows)
            item_rows = len(rows)

    (work / "README.md").write_text(_card(meta, lic, item_rows, table), encoding="utf-8")
    (work / "metadata.jsonld").write_text(json.dumps(jsonld, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(work.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(work).as_posix())
    return {"items": item_rows, "table": table}
