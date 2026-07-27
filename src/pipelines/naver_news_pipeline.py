"""Naver 뉴스 발견형 파이프라인 — §6.1과 같은 원리, "삭제 감지" 방식만 다르다.

YouTube는 채널의 전체 영상 목록을 한 번에 다 가져올 수 있어 "이번에 없으면
삭제"가 안전하다. 뉴스 검색 API는 그렇지 않다 — sort=date 슬라이딩 윈도우라
"검색 결과에 없음"이 몇 분 만에도 뒤집힐 수 있다(실측: 두 번 연속 실행 사이에
기존 기사 146건이 "검색 결과에 없음"으로 나왔는데, 직접 URL을 열어보니 그중
다수가 여전히 200 응답 — 명백한 오탐). 그래서 검색 결과 부재만으로 is_removed
처리하지 않고, 후보 기사의 URL을 **직접 재확인**한다 — 404/410으로 명확히
확인될 때만 삭제로 판정하고, 그 외(200/타임아웃/기타 오류)는 판단을 보류한다.
같은 원칙이 블로그(Phase 2 다음 항목)에도 그대로 적용돼야 한다.

댓글 수는 ADR-005로 검증된 방식대로 is_naver_hosted=TRUE 기사만 수집한다.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.collectors import naver_news_collector
from src.database import dcat
from src.database import meta_naver_news
from src.database.db import get_conn

AGENT = "naver_news_collector"


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
            SELECT count(*) FROM active_meta_naver_news a
            JOIN meta_naver_news m ON m.id = a.meta_id
            WHERE m.dataset_id = %s
            """,
            (dataset_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def _collect_comment_stats(meta_id: int, article: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> None:
    if not article["is_naver_hosted"]:
        return
    stats = naver_news_collector.fetch_comment_stats(article["naver_oid"], article["naver_aid"])
    if stats is None:
        return
    delta = None
    if prev is not None and prev.get("comment_count") is not None and stats.get("comment_count") is not None:
        delta = stats["comment_count"] - prev["comment_count"]
    meta_naver_news.insert_active_meta_naver_news(
        meta_id, stats.get("comment_count"), stats.get("expose_count"), stats.get("reply_count"), delta,
    )


def run(dataset_id: str, triggered_by: str) -> None:
    dataset = dcat.fetch_dcat_dataset(dataset_id)
    was_pending = _get_registry_status(dataset_id) == "pending"
    client_id = dcat.get_api_key(dataset_id, "naver_client_id")
    client_secret = dcat.get_api_key(dataset_id, "naver_client_secret")
    keywords = dataset["subjects"] if isinstance(dataset["subjects"], list) else json.loads(dataset["subjects"])
    started_at = datetime.now(timezone.utc)

    try:
        existing = meta_naver_news.get_existing_articles(dataset_id)
        remote_urls = set()
        processed_this_run = set()  # 여러 검색어에 같은 기사가 매칭돼도 1회만 처리
        new_count, updated_count, removed_count = 0, 0, 0

        for keyword in keywords:
            for item in naver_news_collector.search_all(client_id, client_secret, keyword):
                article = naver_news_collector.normalize_article(item, keyword)
                url = article["article_url"]
                remote_urls.add(url)

                if url in processed_this_run:
                    continue  # 이미 이번 실행에서 다른 검색어로 처리됨 — 중복 API 호출 방지
                processed_this_run.add(url)

                if url not in existing:
                    content = naver_news_collector.fetch_article_content(url)
                    meta_id = meta_naver_news.insert_meta_naver_news(dataset_id, article, content)
                    _collect_comment_stats(meta_id, article, prev=None)
                    # 같은 기사가 다른 검색어에서도 매칭될 수 있어, 이번 실행 중 발견한
                    # 것도 바로 existing에 반영 — 안 하면 두 번째 매칭 때 중복 INSERT 시도함
                    existing[url] = {
                        "id": meta_id, "published_at": article["published_at"],
                        "is_naver_hosted": article["is_naver_hosted"],
                        "naver_oid": article["naver_oid"], "naver_aid": article["naver_aid"],
                        "is_removed": False,
                    }
                    new_count += 1
                else:
                    meta_id = existing[url]["id"]
                    meta_naver_news.clear_removed_flag(meta_id)
                    prev = meta_naver_news.get_latest_active_meta(meta_id)
                    _collect_comment_stats(meta_id, article, prev)
                    updated_count += 1

        # 검색 결과에 없는 기존 기사는 "삭제 후보"일 뿐 — URL을 직접 재확인해서
        # 404/410으로 명확히 확인된 것만 삭제 처리 (윈도우 부재 자체는 근거로 안 씀)
        for url, info in existing.items():
            if url in remote_urls or info["is_removed"]:
                continue
            still_exists = naver_news_collector.check_article_still_exists(url)
            if still_exists is False:
                meta_naver_news.mark_removed(info["id"], removed_at=datetime.now(timezone.utc))
                removed_count += 1

        ended_at = datetime.now(timezone.utc)
        item_count = len(existing) + new_count

        dcat.insert_dcat_provenance(
            dataset_id, activity_type="initial" if was_pending else "update",
            agent=AGENT, triggered_by=triggered_by,
            started_at=started_at, ended_at=ended_at, status="success",
            rows_affected=new_count + updated_count,
            params={"keywords": keywords},
            notes=f"신규 {new_count} / 갱신 {updated_count} / 삭제감지 {removed_count}",
        )
        dcat.update_data_registry(
            dataset_id,
            status="active",
            item_count=item_count,
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
