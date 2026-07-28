"""Naver 블로그 발견형 파이프라인 — 뉴스와 같은 원리 + 반응 수(ADR-006) 수집.

뉴스 파이프라인 개발 중 확립한 두 원칙을 그대로 따른다:
  1) 검색 API는 sort=date 슬라이딩 윈도우라 "검색 결과 부재"만으로 삭제 판정하지
     않는다 — URL을 직접 재확인(HEAD)해서 404/410 확정시만 is_removed 처리
     (04_Collection_Pipeline_Operations.md §6.1 참조)
  2) 같은 게시물이 여러 검색어에 매칭될 수 있어 실행 중(run 내) 처리 여부를
     추적해서 중복 INSERT·중복 API 호출을 막는다

반응 수(공감 등)는 ADR-006으로 검증된 platform='naver' 게시물만 수집한다.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.collectors import naver_blog_collector
from src.database import dcat
from src.database import meta_naver_blog
from src.database.db import get_conn
from src.storage import jsonld_export, raw_export

AGENT = "naver_blog_collector"
logger = logging.getLogger(__name__)


def _get_registry_status(dataset_id: str) -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM data_registry WHERE dataset_id = %s", (dataset_id,))
        row = cur.fetchone()
        return row[0] if row else "pending"
    finally:
        conn.close()


def _current_item_count(dataset_id: str) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM meta_naver_blog WHERE dataset_id = %s", (dataset_id,))
        return cur.fetchone()[0]
    finally:
        conn.close()


def _current_row_count(dataset_id: str) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT count(*) FROM active_meta_naver_blog a
            JOIN meta_naver_blog m ON m.id = a.meta_id
            WHERE m.dataset_id = %s
            """,
            (dataset_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def _collect_reaction_stats(meta_id: int, post: Dict[str, Any], prev: Optional[Dict[str, Any]]) -> None:
    if post["platform"] != "naver" or not post["blog_id"] or not post["log_no"]:
        return
    stats = naver_blog_collector.fetch_reaction_stats(post["blog_id"], post["log_no"])
    if stats is None:
        return
    delta = None
    if prev is not None and prev.get("reaction_count") is not None:
        delta = stats["reaction_count"] - prev["reaction_count"]
    meta_naver_blog.insert_active_meta_naver_blog(
        meta_id, stats["reaction_count"], stats["reaction_breakdown"], delta,
    )


def run(dataset_id: str, triggered_by: str) -> None:
    dataset = dcat.fetch_dcat_dataset(dataset_id)
    was_pending = _get_registry_status(dataset_id) == "pending"
    client_id = dcat.get_api_key(dataset_id, "naver_client_id")
    client_secret = dcat.get_api_key(dataset_id, "naver_client_secret")
    keywords = dataset["subjects"] if isinstance(dataset["subjects"], list) else json.loads(dataset["subjects"])
    started_at = datetime.now(timezone.utc)

    try:
        existing = meta_naver_blog.get_existing_posts(dataset_id)
        remote_urls = set()
        processed_this_run = set()
        new_count, updated_count, removed_count = 0, 0, 0

        for keyword in keywords:
            for item in naver_blog_collector.search_all(client_id, client_secret, keyword):
                post = naver_blog_collector.normalize_post(item, keyword)
                url = post["post_url"]
                remote_urls.add(url)

                if url in processed_this_run:
                    continue
                processed_this_run.add(url)

                if url not in existing:
                    content = naver_blog_collector.fetch_post_content(
                        url, post["platform"], post["blog_id"], post["log_no"]
                    )
                    meta_id = meta_naver_blog.insert_meta_naver_blog(dataset_id, post, content)
                    _collect_reaction_stats(meta_id, post, prev=None)
                    if content:
                        try:
                            raw_export.write_article_content(dataset_id, "blog", meta_id, content)
                        except Exception as e:
                            logger.warning(f"raw 본문 업로드 실패 (meta_id={meta_id}): {e}")
                    existing[url] = {
                        "id": meta_id, "platform": post["platform"],
                        "blog_id": post["blog_id"], "log_no": post["log_no"],
                        "is_removed": False,
                    }
                    new_count += 1
                else:
                    meta_id = existing[url]["id"]
                    meta_naver_blog.clear_removed_flag(meta_id)
                    prev = meta_naver_blog.get_latest_active_meta(meta_id)
                    _collect_reaction_stats(meta_id, post, prev)
                    updated_count += 1

        for url, info in existing.items():
            if url in remote_urls or info["is_removed"]:
                continue
            still_exists = naver_blog_collector.check_post_still_exists(url)
            if still_exists is False:
                meta_naver_blog.mark_removed(info["id"], removed_at=datetime.now(timezone.utc))
                removed_count += 1

        ended_at = datetime.now(timezone.utc)

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
            item_count=_current_item_count(dataset_id),
            row_count=_current_row_count(dataset_id),
            last_collected_at=ended_at,
            next_collect_at=ended_at + dcat.parse_iso8601_duration_to_timedelta(dataset["accrual_periodicity"]),
            last_error=None,
        )

        try:
            s3_raw_prefix, s3_jsonld_prefix = jsonld_export.export_dataset(dataset_id)
            dcat.update_data_registry(dataset_id, s3_raw_prefix=s3_raw_prefix, s3_jsonld_prefix=s3_jsonld_prefix)
        except Exception as e:
            logger.warning(f"S3 export 실패, 수집 자체는 성공 처리: {e}")
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
