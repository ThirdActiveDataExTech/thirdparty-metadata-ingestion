"""P05 01단계 — 코퍼스 수집 (PREREGISTRATION.md §0.1 규격).

FREEZE된 수집 규칙을 그대로 구현한다:
  - 표집 틀: videoCategories.list(regionCode='KR', hl='ko')의 assignable 카테고리(실측 14개).
    이는 코퍼스 Sampling 틀이지 평가 쿼리가 아니다.
  - 카테고리 필터: videoCategoryId는 search에서 부적합(실측)이므로 사용하지 않는다.
    대신 search로 수집 → videos.list의 snippet.categoryId를 받아 원하는 14개
    카테고리로 **사후 필터링**한다.
  - 검색어(seed): 카테고리당 **복수 seed**(data/seeds.json)를 쓴다. seed는 사람이 작성해
    박제한 커버리지용 Sampling 키워드이지 평가 쿼리가 아니다. 최종 seed는 Seed Pilot
    (00_seed_pilot.py)이 잔존율로 확정한다. seeds.json에 나열된 seed를 그대로 사용.
  - 정렬 3혼합: relevance + viewCount + date를 섞어 표집 편향 완화(단일 정렬 편향 방지 +
    viewCount 붕괴 카테고리를 relevance분이 보충).
  - 채널당 최대 5개: 채널 편향 차단.
  - Long-form only: search에 videoDuration='long'을 적용해 장편만 수집(Shorts 제외).
    duration은 기록용으로 계속 저장한다.
  - 목표: 카테고리당 100편(미달 시 확보량 그대로) 균형(층화)표집, 총 ~1,400편.

출력(모두 data/):
  - categories.json : 수집에 쓴 카테고리 목록 스냅샷(id, 한국어명)
  - corpus.jsonl    : 영상 1편 = 1줄. 재현성의 핵심 산출물(git 커밋 대상)

이 스크립트는 "최초 코퍼스 구축용"이다. 인기순/검색결과는 시간에 따라 변하므로 재실행하면
다른 영상이 나온다 — 재현은 커밋된 corpus.jsonl로 하고, 하류 단계(02~)는 이 파일만 읽는다.

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

# ── 사전 고정 파라미터 (PREREGISTRATION.md §0.1) ──────────────────
REGION = "KR"
RELEVANCE_LANG = "ko"
PUBLISHED_AFTER = "2025-01-01T00:00:00Z"   # 기간 하한 (재현성)
VIDEO_DURATION = "long"                     # Long-form only (Shorts 제외)
ORDERS = ["relevance", "viewCount", "date"]  # 3정렬 혼합
TARGET_PER_CATEGORY = 100
MAX_PER_CHANNEL = 5                          # 채널 편향 차단
PAGES_PER_ORDER = 2                          # 정렬당 검색 페이지 수 (50/페이지) — 쿼터 관리
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEDS_PATH = DATA_DIR / "seeds_frozen.json"  # Seed Pilot 확정본(status=frozen). 후보 풀은 seeds.json.


def _retry(request, tries=3, base=1.0):
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
    return {
        it["id"]: it["snippet"]["title"]
        for it in resp.get("items", [])
        if it["snippet"].get("assignable")
    }


def search_video_ids(svc, query: str) -> list:
    """한 seed 검색어에 대해 3정렬 혼합으로 video_id 수집(순서 유지, 중복 제거)."""
    seen = set()
    ids = []
    for order in ORDERS:
        page_token = None
        for _ in range(PAGES_PER_ORDER):
            resp = _retry(
                svc.search().list(
                    part="id", type="video", q=query, order=order,
                    relevanceLanguage=RELEVANCE_LANG, regionCode=REGION,
                    publishedAfter=PUBLISHED_AFTER, videoDuration=VIDEO_DURATION,
                    maxResults=50, pageToken=page_token,
                )
            )
            for it in resp.get("items", []):
                vid = it["id"]["videoId"]
                if vid not in seen:
                    seen.add(vid)
                    ids.append(vid)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
            time.sleep(0.1)
    return ids


def _pick_thumbnail(thumbs: dict):
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbs:
            return thumbs[key]["url"]
    return None


def fetch_details(svc, video_ids: list) -> dict:
    """video_id → 상세 메타데이터 dict. 50개씩 배치. {video_id: row}."""
    out = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _retry(
            svc.videos().list(
                part="snippet,statistics,contentDetails,status,topicDetails",
                id=",".join(batch),
            )
        )
        for it in resp.get("items", []):
            snip = it.get("snippet", {})
            stats = it.get("statistics", {})
            content = it.get("contentDetails", {})
            status = it.get("status", {})
            topics = it.get("topicDetails", {})
            duration = content.get("duration", "PT0S")
            thumb = _pick_thumbnail(snip.get("thumbnails", {}))
            if not thumb:
                continue  # 썸네일 없음 제외 (Shorts는 search videoDuration='long'으로 이미 배제)
            out[it["id"]] = {
                "video_id": it["id"],
                "title": snip.get("title", ""),
                "description": snip.get("description", ""),
                "tags": snip.get("tags", []),
                "category_id": snip.get("categoryId"),
                "published_at": snip.get("publishedAt"),
                "channel_id": snip.get("channelId"),
                "channel_title": snip.get("channelTitle"),
                "duration": duration,
                "duration_seconds": youtube_collector.parse_duration_seconds(duration),
                "thumbnail_url": thumb,
                "view_count": int(stats["viewCount"]) if "viewCount" in stats else None,
                "like_count": int(stats["likeCount"]) if "likeCount" in stats else None,
                "comment_count": int(stats["commentCount"]) if "commentCount" in stats else None,
                "default_language": snip.get("defaultLanguage"),
                "default_audio_language": snip.get("defaultAudioLanguage"),
                "live_broadcast_content": snip.get("liveBroadcastContent"),
                "made_for_kids": status.get("madeForKids"),
                "licensed_content": content.get("licensedContent"),
                "topic_categories": topics.get("topicCategories", []),
            }
        time.sleep(0.1)
    return out


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    api_key = config.require_env("YOUTUBE_API_KEY")
    svc = youtube_collector.build_service(api_key)
    collected_at = datetime.now(timezone.utc).isoformat()

    # 실측 카테고리 스냅샷(재현용) — 표집 틀 근거 기록
    assignable = get_assignable_categories(svc)
    (DATA_DIR / "categories.json").write_text(
        json.dumps(
            {"region": REGION, "collected_at": collected_at, "categories": assignable},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    # 확정된 복수 seed 로드 (Seed Pilot로 압축된 seeds.json)
    seeds_doc = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    seed_cats = seeds_doc["categories"]
    print(f"seeds.json 카테고리 {len(seed_cats)}개 (status={seeds_doc.get('_meta', {}).get('status')})")

    global_seen = set()          # 전 카테고리 통틀어 중복 video 제거
    corpus = []
    per_cat_counts = {}
    for cid, entry in seed_cats.items():
        name = entry["name"]
        seeds = entry["seeds"]
        # 1) 카테고리의 복수 seed를 각각 3정렬 혼합 수집 → 순서 유지 병합·중복 제거
        merged_ids = []
        seen_local = set()
        for seed in seeds:
            for vid in search_video_ids(svc, seed):
                if vid in seen_local or vid in global_seen:
                    continue
                seen_local.add(vid)
                merged_ids.append(vid)
        # 2) 상세 조회
        details = fetch_details(svc, merged_ids)
        # 3) 사후 필터: 실제 categoryId가 이 카테고리(cid)인 것만
        in_category = [row for row in details.values() if row.get("category_id") == cid]
        # 4) 채널당 최대 MAX_PER_CHANNEL, 카테고리당 TARGET까지 (균형표집)
        chan_count = {}
        kept = []
        for row in in_category:  # 검색 순서(관련성 우선) 유지
            ch = row.get("channel_id")
            if chan_count.get(ch, 0) >= MAX_PER_CHANNEL:
                continue
            chan_count[ch] = chan_count.get(ch, 0) + 1
            row["sampled_category_id"] = cid
            row["sampled_category_name"] = name
            row["sampled_seeds"] = seeds
            row["collected_at"] = collected_at
            kept.append(row)
            global_seen.add(row["video_id"])
            if len(kept) >= TARGET_PER_CATEGORY:
                break
        corpus.extend(kept)
        per_cat_counts[f"{cid}:{name}"] = len(kept)
        print(
            f"  cat {cid:>2} {name:<10} seed{len(seeds)} 후보 {len(merged_ids):>4} "
            f"→ 상세 {len(details):>4} → 카테고리일치 {len(in_category):>4} "
            f"→ 채택 {len(kept):>3} (채널 {len(chan_count)})"
        )

    out_path = DATA_DIR / "corpus.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_channels = len({r["channel_id"] for r in corpus})
    print(f"\n총 {len(corpus)}편 / 채널 {n_channels}개 → {out_path}")
    print("카테고리별 채택 수:", json.dumps(per_cat_counts, ensure_ascii=False))
    short = {k: v for k, v in per_cat_counts.items() if v < TARGET_PER_CATEGORY}
    if short:
        print(f"⚠️ 목표({TARGET_PER_CATEGORY}) 미달:", json.dumps(short, ensure_ascii=False))


if __name__ == "__main__":
    main()
