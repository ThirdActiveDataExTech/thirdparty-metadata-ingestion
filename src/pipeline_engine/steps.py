"""파이프라인 단계 — 고정 4단계 템플릿 (C3 최소선).

**근거**: 연구개발계획서 2차년도 "템플릿 기반 파이프라인 구성"
〔SW 모듈 귀속: 모비젠〕

    collect    원천에서 읽는다           (A1 어댑터)
    normalize  meta_* 컬럼 모양으로 바꾼다 (A1 어댑터)
    store      DB에 넣는다               ← **A1이 비워 둔 자리**
    postprocess 임베딩·JSON-LD            (기존 모듈 재사용)

A1은 `collect`·`normalize`까지만 만들었다. 어댑터가 동작하는 것은 증명됐으나
**적재된 행이 0건**이었다 — A1 완료 기준("`meta_*`·`data_registry` 적재 확인")의
미충족분이 여기서 닫힌다.

---

## 왜 `store`가 A1에 없었나

원천마다 `meta_*` 테이블의 컬럼이 다르다. `normalize`가 돌려주는 평평한 dict를
어느 테이블의 어느 컬럼에 넣을지는 **어댑터가 알 수 없다.** 그 매핑이 파이프라인
스펙의 일이고, 그래서 C3로 미뤄져 있었다.

## 멱등하게 넣는다

`meta_*`에는 전부 `UNIQUE(dataset_id, 고유키)`가 있다. `ON CONFLICT DO UPDATE`로
넣으므로 같은 파이프라인을 두 번 돌려도 중복이 생기지 않는다. 손으로 쓴
파이프라인과 같은 테이블을 써도 서로 덮어쓸 뿐 어긋나지 않는다.

## 스펙에 적는 컬럼만 쓴다

`normalize` 결과를 통째로 INSERT하지 않는다. 원천이 필드를 늘리면 없는 컬럼에
쓰려다 실패하거나, 더 나쁘게는 엉뚱한 컬럼에 들어간다. **스펙의 `columns`에
적힌 것만** 간다.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

from psycopg2.extras import execute_values

from src.database.db import get_conn

logger = logging.getLogger(__name__)


class StepError(RuntimeError):
    """단계가 실패했다. 어느 단계인지 메시지에 담는다."""


def collect(adapter, query: Optional[Dict[str, Any]] = None,
            limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """A1 어댑터로 원천에서 읽는다."""
    out = []
    for raw in adapter.fetch(query=query):
        out.append(raw)
        if limit and len(out) >= limit:
            break
    logger.info("collect: %d건", len(out))
    return out


def normalize(adapter, raws: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A1 어댑터로 `meta_*` 컬럼 모양에 맞춘다.

    식별자가 없는 항목은 **버린다.** 중복 판정의 기준이 없으면 넣을 때마다
    새 행이 쌓인다.
    """
    out = []
    dropped = 0
    for raw in raws:
        row = adapter.normalize(raw)
        try:
            adapter.item_id(row)
        except Exception:                         # noqa: BLE001
            dropped += 1
            continue
        out.append(row)
    if dropped:
        logger.warning("normalize: 식별자가 없어 %d건 버림", dropped)
    logger.info("normalize: %d건", len(out))
    return out


def store(rows: Sequence[Dict[str, Any]], dataset_id: str, table: str,
          columns: Sequence[str], conflict_key: str,
          defaults: Optional[Dict[str, Any]] = None,
          dry_run: bool = False) -> Dict[str, int]:
    """정규화된 행을 `meta_*`에 멱등하게 넣는다 — **A1이 비워 둔 자리**.

    columns: 스펙이 허용한 컬럼만. `normalize` 결과를 통째로 넣지 않는다
    conflict_key: `UNIQUE(dataset_id, <이것>)`의 두 번째 컬럼
    defaults: 스펙이 채우는 고정값(NOT NULL 컬럼 등)
    """
    if not rows:
        return {"attempted": 0, "stored": 0}
    defaults = defaults or {}
    cols = ["dataset_id"] + list(columns) + list(defaults)
    if conflict_key not in cols:
        raise StepError(f"store: conflict_key '{conflict_key}'가 columns에 없다")

    payload = []
    for r in rows:
        values = [dataset_id] + [r.get(c) for c in columns] + list(defaults.values())
        payload.append(tuple(values))

    if dry_run:
        logger.info("store(dry-run): %d건을 %s에 쓰지 않는다", len(payload), table)
        return {"attempted": len(payload), "stored": 0}

    # 갱신 대상에서 키 컬럼은 뺀다 — 자기 자신을 덮어쓸 이유가 없다
    updatable = [c for c in cols if c not in ("dataset_id", conflict_key)]
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
    conn = get_conn()
    cur = conn.cursor()
    execute_values(
        cur,
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT (dataset_id, {conflict_key}) DO UPDATE SET "
        f"{update_sql}, updated_at = now()",
        payload, page_size=500, fetch=False)
    conn.commit()
    logger.info("store: %s에 %d건", table, len(payload))
    return {"attempted": len(payload), "stored": len(payload)}


def postprocess(dataset_id: str, source_type: str, actions: Iterable[str],
                dry_run: bool = False) -> Dict[str, Any]:
    """임베딩·JSON-LD 등 후속 처리. 기존 모듈을 그대로 부른다.

    **여기서 새로 만들지 않는다.** 손으로 쓴 파이프라인과 같은 코드를 타야
    결과가 같다 — 따로 구현하면 두 경로의 산출물이 조용히 달라진다.
    """
    out: Dict[str, Any] = {}
    for action in actions:
        if dry_run:
            out[action] = "dry-run"
            continue
        try:
            if action == "embed":
                from src.embedding import sync
                out["embed"] = sync.sync_for_dataset(source_type, dataset_id)
            elif action == "jsonld":
                from src.storage import jsonld_export
                out["jsonld"] = jsonld_export.export_dataset(dataset_id)
            else:
                raise StepError(f"알 수 없는 postprocess: {action}")
        except StepError:
            raise
        except Exception as e:                    # noqa: BLE001
            # 후속 처리 실패가 수집을 무효로 만들지 않는다. 데이터는 이미 들어갔다
            logger.warning("postprocess %s 실패(수집은 유효): %s", action, e)
            out[action] = f"실패: {e}"
    return out
