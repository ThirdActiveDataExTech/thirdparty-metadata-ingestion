"""Naver 쇼핑인사이트 선언형 파이프라인 — architecture/04_Collection_Pipeline_Operations.md
§6.2 그대로 구현.

shopping_insight/persona_insight는 신규/기존 분기도 삭제 감지도 필요 없다 —
meta_naver_shopping의 카테고리 목록은 등록 시점에 사용자가 이미 확정한 것이라
Collector가 목록 자체를 바꾸지 않는다. 매 실행마다 그 고정된 카테고리들의
"어제자" 지수만 API로 가져와 active_meta_naver_shopping에 새 행을 추가한다
(당일 데이터는 아직 API에 반영 안 됐을 수 있어 하루 지연 — 레거시 스크립트와
동일한 관례).

anchor 카테고리는 모든 배치 호출에 포함시켜 호출당 최대 3카테고리 제약을
맞춘다(비-anchor 2개씩 묶음). intra_scale(배치 간)·inter_scale(수집 구간 간)
보정은 naver_datalab_scale.py 참조.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from src.collectors import naver_datalab_scale, naver_shopping_collector
from src.database import dcat, meta_naver_shopping
from src.database.db import get_conn

AGENT = "naver_shopping_collector"
GENDERS = ["m", "f"]
AGES = ["10", "20", "30", "40", "50", "60"]


def _get_registry_status(dataset_id: str) -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM data_registry WHERE dataset_id = %s", (dataset_id,))
        row = cur.fetchone()
        return row[0] if row else "pending"
    finally:
        conn.close()


def _current_row_count(dataset_id: str) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT count(*) FROM active_meta_naver_shopping a
            JOIN meta_naver_shopping m ON m.id = a.meta_id
            WHERE m.dataset_id = %s
            """,
            (dataset_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def _chunk(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]


def run(dataset_id: str, triggered_by: str) -> None:
    dataset = dcat.fetch_dcat_dataset(dataset_id)
    was_pending = _get_registry_status(dataset_id) == "pending"
    client_id = dcat.get_api_key(dataset_id, "naver_client_id")
    client_secret = dcat.get_api_key(dataset_id, "naver_client_secret")

    categories = meta_naver_shopping.get_meta_naver_shopping_rows(dataset_id)
    anchor = next(c for c in categories if c["is_anchor"])
    non_anchor = [c for c in categories if not c["is_anchor"]]
    batches = _chunk(non_anchor, 2)

    target_date = (date.today() - timedelta(days=1)).isoformat()
    started_at = datetime.now(timezone.utc)
    rows_written = 0

    try:
        for gender in GENDERS:
            for age in AGES:
                rows_written += _collect_one_combo(
                    dataset_id, anchor, batches, gender, age,
                    target_date, client_id, client_secret,
                )

        ended_at = datetime.now(timezone.utc)
        dcat.insert_dcat_provenance(
            dataset_id, activity_type="initial" if was_pending else "update",
            agent=AGENT, triggered_by=triggered_by,
            started_at=started_at, ended_at=ended_at, status="success",
            rows_affected=rows_written,
            params={"target_date": target_date, "categories": len(categories)},
        )
        dcat.update_data_registry(
            dataset_id,
            status="active",
            item_count=len(categories),
            row_count=_current_row_count(dataset_id),
            last_collected_at=ended_at,
            next_collect_at=ended_at + dcat.parse_iso8601_duration_to_timedelta(dataset["accrual_periodicity"]),
            last_error=None,
        )
    except Exception as e:
        ended_at = datetime.now(timezone.utc)
        dcat.insert_dcat_provenance(
            dataset_id, activity_type="initial" if was_pending else "update",
            agent=AGENT, triggered_by=triggered_by,
            started_at=started_at, ended_at=ended_at, status="failure",
            error_message=str(e),
        )
        dcat.update_data_registry(
            dataset_id, status="error", last_error=str(e),
            next_collect_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        raise


def _collect_one_combo(
    dataset_id: str,
    anchor: Dict[str, Any],
    batches: List[List[Dict[str, Any]]],
    gender: str,
    age: str,
    target_date: str,
    client_id: str,
    client_secret: str,
) -> int:
    """(gender, age) 조합 1개에 대해 배치 전부 호출 → scale 보정 → 저장. 저장 행 수 반환."""
    anchor_pair = (anchor["category_id"], anchor["category_name"])

    # Step 1: 이 (gender, age)의 모든 배치 호출
    batch_results: List[Tuple[int, List[Dict[str, Any]], Any]] = []
    for b_idx, batch in enumerate(batches):
        cats_in_call = [anchor_pair] + [(c["category_id"], c["category_name"]) for c in batch]
        data = naver_shopping_collector.fetch_insight(
            client_id, client_secret, target_date, target_date, "date",
            cats_in_call, gender, age,
        )
        parsed = naver_shopping_collector.parse_response(data) if data else None
        batch_results.append((b_idx, batch, parsed))

    # Step 2: 첫 유효 배치를 기준(ref) anchor로 사용, DB 기존값과 비교해 inter_scale 계산
    ref_anchor: Dict[str, float] = {}
    ref_batch_idx = -1
    for b_idx, _, parsed in batch_results:
        if parsed and parsed.get(anchor["category_name"]):
            ref_anchor = parsed[anchor["category_name"]]
            ref_batch_idx = b_idx
            break

    existing_anchor = meta_naver_shopping.get_existing_anchor_raw(
        anchor["id"], gender, age, list(ref_anchor.keys())
    )
    inter_scale = naver_datalab_scale.compute_inter_scale(existing_anchor, ref_anchor)

    # Step 3: 배치별 intra_scale 계산 후 저장
    rows_written = 0
    for b_idx, batch, parsed in batch_results:
        if not parsed:
            continue
        batch_anchor = parsed.get(anchor["category_name"], {})
        intra_scale = naver_datalab_scale.median_ratio(ref_anchor, batch_anchor) if batch_anchor else 1.0
        scale_factor = inter_scale * intra_scale

        if b_idx == ref_batch_idx:
            for period, raw in batch_anchor.items():
                meta_naver_shopping.upsert_active_meta_naver_shopping(
                    anchor["id"], period, gender, age,
                    raw_ratio=raw, anchor_raw_ratio=raw, normalized_ratio=100.0,
                    scale_factor=scale_factor, pseudo_volume=raw * scale_factor,
                    batch_index=b_idx,
                )
                rows_written += 1

        for cat in batch:
            cat_by_period = parsed.get(cat["category_name"], {})
            for period, raw in cat_by_period.items():
                anchor_raw = batch_anchor.get(period)
                normalized = raw / anchor_raw * 100.0 if anchor_raw else None
                meta_naver_shopping.upsert_active_meta_naver_shopping(
                    cat["id"], period, gender, age,
                    raw_ratio=raw, anchor_raw_ratio=anchor_raw, normalized_ratio=normalized,
                    scale_factor=scale_factor, pseudo_volume=raw * scale_factor,
                    batch_index=b_idx,
                )
                rows_written += 1

    return rows_written
