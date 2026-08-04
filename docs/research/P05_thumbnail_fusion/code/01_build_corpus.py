"""P05 01단계 — 코퍼스 수집 (YouTube 공식 카테고리별 규칙 표집).

PREREGISTRATION.md §4의 표집 설계를 그대로 구현한다:
  - 표집 틀: videoCategories.list(regionCode='KR', hl='ko')의 assignable 카테고리 (실측 14개)
  - 카테고리별 규칙: search.list(videoCategoryId=C, q=<C의 공식 한국어명>, order=viewCount,
    relevanceLanguage='ko', regionCode='KR', publishedAfter=고정일) — 검색어를 연구자가
    고르지 않고 YouTube 공식 카테고리명으로 고정해 주관 배제. (videoCategoryId 단독은
    API가 0건 반환하므로 q 필수 — 변경이력 2026-08-04 참조)
  - 제외: 중복 video_id, 썸네일 없음, Shorts(≤60초)
  - 목표: 카테고리당 70편(미달 시 확보량 그대로), 총 ~980편

출력(모두 data/):
  - categories.json : 수집에 쓴 카테고리 목록 스냅샷(id, 한국어명)
  - corpus.jsonl    : 영상 1편 = 1줄. 재현성의 핵심 산출물(git 커밋 대상)

이 스크립트는 "최초 코퍼스 구축용"이다. 인기순은 시간에 따라 변하므로 재실행하면 다른
영상이 나온다 — 재현은 커밋된 corpus.jsonl로 하고, 하류 단계(02~)는 이 파일만 읽는다.

실행: 저장소 루트에서
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/01_build_corpus.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError

from src.collectors import youtube_collector
from src.common import config

# ── 사전 고정 파라미터 (PREREGISTRATION.md §4.2) ──────────────────
REGION = "KR"
RELEVANCE_LANG = "ko"
ORDER = "viewCount"
PUBLISHED_AFTER = "2025-01-01T00:00:00Z"  # 기간 하한 (재현성)
TARGET_PER_CATEGORY = 70
EXCLUDE_SHORTS_MAX_SEC = 60  # 이하이면 Shorts로 보고 제외
MAX_SEARCH_PAGES = 6  # 카테고리당 검색 페이지 상한 (안전장치, 50/페이지)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _retry(request, tries=3, base=1.0):
    """5xx만 재시도, 4xx(쿼터 등)는 즉시 전파."""
    for attempt in range(tries):
        try:
            return request.execute()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status and int(status) >= 500 and attempt < tries - 1:
                time.sleep(base * (2**attempt))
                continue
            raise


def get_assignable_categories(svc) -> dict:
    """{category_id: 한국어명} — assignable=true인 KR 카테고리만."""
    resp = _retry(svc.videoCategories().list(part="snippet", regionCode=REGION, hl=RELEVANCE_LANG))
    cats = {}
    for it in resp.get("items", []):
        if it["snippet"].get("assignable"):
            cats[it["id"]] = it["snippet"]["title"]
    return cats


def search_category_video_ids(svc, category_id: str, query_name: str, seen: set) -> list:
    """한 카테고리에서 규칙대로 video_id를 목표 수만큼 수집(중복·기존 제외)."""
    ids = []
    page_token = None
    for _ in range(MAX_SEARCH_PAGES):
        resp = _retry(
            svc.search().list(
                part="id", type="video", videoCategoryId=category_id, q=query_name,
                order=ORDER, relevanceLanguage=RELEVANCE_LANG, regionCode=REGION,
                publishedAfter=PUBLISHED_AFTER, maxResults=50, pageToken=page_token,
            )
        )
        for it in resp.get("items", []):
            vid = it["id"]["videoId"]
            if vid not in seen:
                seen.add(vid)
                ids.append(vid)
        page_token = resp.get("nextPageToken")
        # 목표보다 넉넉히 모아두고(상세조회에서 Shorts 등 탈락 대비) 다음 단계에서 자름
        if len(ids) >= TARGET_PER_CATEGORY * 2 or not page_token:
            break
        time.sleep(0.1)
    return ids


def _pick_thumbnail(thumbs: dict):
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbs:
            return thumbs[key]["url"]
    return None


def fetch_details(svc, video_ids: list) -> list:
    """video_id 목록 → 상세 메타데이터 dict 목록 (50개씩 배치). Shorts·썸네일없음 제외."""
    out = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _retry(
            svc.videos().list(part="snippet,statistics,contentDetails", id=",".join(batch))
        )
        for it in resp.get("items", []):
            snip = it.get("snippet", {})
            stats = it.get("statistics", {})
            content = it.get("contentDetails", {})
            duration = content.get("duration", "PT0S")
            dur_sec = youtube_collector.parse_duration_seconds(duration)
            if dur_sec <= EXCLUDE_SHORTS_MAX_SEC:
                continue  # Shorts 제외
            thumb = _pick_thumbnail(snip.get("thumbnails", {}))
            if not thumb:
                continue  # 썸네일 없음 제외
            out.append(
                {
                    "video_id": it["id"],
                    "title": snip.get("title", ""),
                    "description": snip.get("description", ""),
                    "channel_id": snip.get("channelId"),
                    "channel_title": snip.get("channelTitle"),
                    "category_id": snip.get("categoryId"),
                    "published_at": snip.get("publishedAt"),
                    "duration": duration,
                    "duration_seconds": dur_sec,
                    "thumbnail_url": thumb,
                    "view_count": int(stats["viewCount"]) if "viewCount" in stats else None,
                    "like_count": int(stats["likeCount"]) if "likeCount" in stats else None,
                    "comment_count": int(stats["commentCount"]) if "commentCount" in stats else None,
                }
            )
        time.sleep(0.1)
    return out


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    api_key = config.require_env("YOUTUBE_API_KEY")
    svc = youtube_collector.build_service(api_key)
    collected_at = datetime.now(timezone.utc).isoformat()

    categories = get_assignable_categories(svc)
    print(f"assignable 카테고리 {len(categories)}개: {categories}")
    (DATA_DIR / "categories.json").write_text(
        json.dumps(
            {"region": REGION, "collected_at": collected_at, "categories": categories},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    seen = set()
    corpus = []
    per_cat_counts = {}
    for cid, name in categories.items():
        ids = search_category_video_ids(svc, cid, name, seen)
        details = fetch_details(svc, ids)
        # 규칙대로 order=viewCount 순서를 유지한 채 앞에서 목표 수만큼 자름
        kept = details[:TARGET_PER_CATEGORY]
        for row in kept:
            row["sampled_category_id"] = cid          # 표집에 사용한 카테고리
            row["sampled_category_name"] = name       # 그 카테고리의 공식 한국어명(=검색어)
            row["collected_at"] = collected_at
        corpus.extend(kept)
        per_cat_counts[f"{cid}:{name}"] = len(kept)
        print(f"  cat {cid:>2} {name:<8} 후보 {len(ids):>3} → 정규영상 {len(details):>3} → 채택 {len(kept):>3}")

    out_path = DATA_DIR / "corpus.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n총 {len(corpus)}편 수집 → {out_path}")
    print("카테고리별 채택 수:", json.dumps(per_cat_counts, ensure_ascii=False))
    # 카테고리당 목표 미달 경고 (PREREGISTRATION §4.2: 미달 시 확보량 그대로 기록)
    short = {k: v for k, v in per_cat_counts.items() if v < TARGET_PER_CATEGORY}
    if short:
        print(f"⚠️ 목표({TARGET_PER_CATEGORY}) 미달 카테고리:", json.dumps(short, ensure_ascii=False))


if __name__ == "__main__":
    main()
