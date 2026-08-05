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

  - round-robin 수집: seed를 교대로 채택해 잔존율 최고 seed(예: 강아지)가 카테고리를
    독식하지 못하게 한다("동물=강아지" 편중을 수집 단계에서 차단).

내구성:
  - **다중 키 failover**: config.get_youtube_api_keys()의 기본→예비 키로, 쿼터(429/403)
    소진 시 자동 전환(예비키가 별도 GCP 프로젝트일 때만 실효).
  - **카테고리 단위 재개(resumable)**: 카테고리 완료마다 corpus.jsonl에 append +
    corpus_progress.json에 체크포인트. 모든 키 쿼터 소진 시 우아하게 중단하고, 같은 명령으로
    재실행하면 완료된 카테고리는 건너뛰고 이어서 수집한다.

출력(모두 data/):
  - categories.json      : 수집에 쓴 카테고리 목록 스냅샷(id, 한국어명)
  - corpus.jsonl         : 영상 1편 = 1줄. 재현성의 핵심 산출물(git 커밋 대상)
  - corpus_progress.json : 재개 체크포인트(done 카테고리 + global_seen + funnel)
  - corpus_funnel.csv    : 수집 단계별 감소 표(검색→중복제거→상세→categoryId통과→최종),
                           논문 Methods/Results의 코퍼스 구축 투명성 근거

이 스크립트는 "최초 코퍼스 구축용"이다. 인기순/검색결과는 시간에 따라 변하므로 재실행하면
다른 영상이 나온다 — 재현은 커밋된 corpus.jsonl로 하고, 하류 단계(02~)는 이 파일만 읽는다.
(주의: 처음부터 새로 수집하려면 corpus_progress.json을 삭제한 뒤 실행.)

실행: 저장소 루트에서 (쿼터 소진 시 리셋 후 같은 명령 재실행 → 이어서 수집)
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/01_build_corpus.py
"""

import csv
import json
import time
from collections import Counter
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
PROGRESS_PATH = DATA_DIR / "corpus_progress.json"  # 카테고리 단위 재개 체크포인트


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


def _is_quota_error(e: HttpError) -> bool:
    status = getattr(e.resp, "status", None)
    return status is not None and int(status) in (403, 429)


def _load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return None


def _save_progress(prog: dict) -> None:
    PROGRESS_PATH.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_category(svc, cid: str, name: str, seeds: list, global_seen: set) -> tuple:
    """한 카테고리 수집. global_seen은 **읽기 전용**(쿼터 재시도 시 오염 방지) —
    채택분의 video_id는 호출부가 성공 후 global_seen에 추가한다.
    반환: (kept_rows, funnel_row). funnel_row는 단계별 감소 카운트."""
    collected_at = datetime.now(timezone.utc).isoformat()
    # 1) seed별 후보 id 수집(seed 내부 3정렬 혼합). raw = 중복제거 전 합.
    seed_to_ids = {}
    seen_local = set()
    raw_hits = 0
    for seed in seeds:
        hits = search_video_ids(svc, seed)
        raw_hits += len(hits)
        ids = []
        for vid in hits:
            if vid in seen_local or vid in global_seen:
                continue
            seen_local.add(vid)  # 각 영상은 정확히 한 seed에만 귀속
            ids.append(vid)
        seed_to_ids[seed] = ids
    all_ids = [v for ids in seed_to_ids.values() for v in ids]
    # 2) 상세 조회
    details = fetch_details(svc, all_ids)
    # 3) seed별 categoryId 일치 행(검색 순서 유지)
    seed_to_rows = {
        seed: [details[v] for v in ids if v in details and details[v].get("category_id") == cid]
        for seed, ids in seed_to_ids.items()
    }
    n_in_category = sum(len(r) for r in seed_to_rows.values())
    # 4) round-robin: seed 교대 채택(단일 seed 독식 방지) + 채널당 최대 MAX_PER_CHANNEL
    chan_count = {}
    kept = []
    ptr = {seed: 0 for seed in seeds}
    active = [seed for seed in seeds if seed_to_rows[seed]]
    while len(kept) < TARGET_PER_CATEGORY and active:
        for seed in list(active):
            rows = seed_to_rows[seed]
            while ptr[seed] < len(rows):
                row = rows[ptr[seed]]
                ptr[seed] += 1
                ch = row.get("channel_id")
                if chan_count.get(ch, 0) >= MAX_PER_CHANNEL:
                    continue
                chan_count[ch] = chan_count.get(ch, 0) + 1
                row["sampled_category_id"] = cid
                row["sampled_category_name"] = name
                row["sampled_seed"] = seed
                row["sampled_seeds"] = seeds
                row["collected_at"] = collected_at
                kept.append(row)
                break  # round-robin: 다음 seed로
            if ptr[seed] >= len(rows):
                active.remove(seed)
            if len(kept) >= TARGET_PER_CATEGORY:
                break
    funnel_row = {
        "category_id": cid, "name": name, "n_seeds": len(seeds),
        "searched": raw_hits, "deduped": len(all_ids), "detailed": len(details),
        "categoryid_pass": n_in_category, "final": len(kept),
        "channels": len(chan_count),
        "seed_dist": dict(Counter(r["sampled_seed"] for r in kept)),
    }
    return kept, funnel_row


def _write_funnel(funnel: dict) -> None:
    """수집 단계별 감소 표를 콘솔 출력 + CSV 저장(리뷰어 설득용)."""
    rows = list(funnel.values())
    hdr = ("cat", "카테고리", "검색", "중복제거후", "상세", "categoryId통과", "최종", "채널")
    print("\n=== 수집 funnel (단계별 영상 수) ===")
    print(f"{hdr[0]:>3} {hdr[1]:<10} {hdr[2]:>7} {hdr[3]:>9} {hdr[4]:>6} {hdr[5]:>13} {hdr[6]:>6} {hdr[7]:>5}")
    for r in rows:
        print(f"{r['category_id']:>3} {r['name']:<10} {r['searched']:>7} {r['deduped']:>9} "
              f"{r['detailed']:>6} {r['categoryid_pass']:>13} {r['final']:>6} {r['channels']:>5}")
    tot = {k: sum(r[k] for r in rows) for k in ("searched", "deduped", "detailed", "categoryid_pass", "final")}
    print(f"{'':>3} {'합계':<10} {tot['searched']:>7} {tot['deduped']:>9} {tot['detailed']:>6} "
          f"{tot['categoryid_pass']:>13} {tot['final']:>6}")
    csv_path = DATA_DIR / "corpus_funnel.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category_id", "name", "n_seeds", "searched", "deduped",
                    "detailed", "categoryid_pass", "final", "channels"])
        for r in rows:
            w.writerow([r[k] for k in ("category_id", "name", "n_seeds", "searched",
                                       "deduped", "detailed", "categoryid_pass", "final", "channels")])
    print(f"→ funnel CSV 저장: {csv_path}")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    keys = config.get_youtube_api_keys()
    if not keys:
        raise RuntimeError("YOUTUBE_API_KEY가 없습니다 (.env 확인)")
    key_idx = 0
    svc = youtube_collector.build_service(keys[key_idx])
    print(f"API 키 {len(keys)}개 로드. 주의: 예비키가 같은 GCP 프로젝트면 쿼터 공유.")

    seeds_doc = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    seed_cats = seeds_doc["categories"]
    if seeds_doc.get("_meta", {}).get("status") != "frozen":
        print("⚠️ seeds_frozen.json status가 'frozen'이 아님 — 확정본인지 확인 필요.")

    # 재개 상태 로드(카테고리 단위 체크포인트)
    prog = _load_progress()
    corpus_path = DATA_DIR / "corpus.jsonl"
    if prog is None:
        prog = {"done": [], "global_seen": [], "funnel": {},
                "collected_at": datetime.now(timezone.utc).isoformat()}
        corpus_path.write_text("", encoding="utf-8")  # 새 실행: corpus 초기화
        # 카테고리 스냅샷(표집 틀 근거)
        assignable = get_assignable_categories(svc)
        (DATA_DIR / "categories.json").write_text(
            json.dumps({"region": REGION, "collected_at": prog["collected_at"],
                        "categories": assignable}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    done = set(prog["done"])
    global_seen = set(prog["global_seen"])
    print(f"진행: {len(done)}/{len(seed_cats)} 카테고리 완료 (재개 시 완료분 건너뜀)")

    quota_stop = False
    for cid, entry in seed_cats.items():
        if cid in done:
            continue
        # 쿼터 소진 시 예비키로 전환하며 카테고리 재시도(부분 진행분은 버리고 재수집)
        while True:
            try:
                kept, funnel_row = collect_category(svc, cid, entry["name"], entry["seeds"], global_seen)
                break
            except HttpError as e:
                if _is_quota_error(e) and key_idx + 1 < len(keys):
                    key_idx += 1
                    svc = youtube_collector.build_service(keys[key_idx])
                    print(f"  ⚠️ 쿼터 소진 → 예비키 {key_idx + 1}/{len(keys)}로 전환 후 cat {cid} 재시도")
                    continue
                if _is_quota_error(e):
                    print(f"\n⚠️ 모든 키({len(keys)}개) 쿼터 소진 — cat {cid} 미완. 진행분 저장.")
                    quota_stop = True
                    break
                raise
        if quota_stop:
            break
        # 성공: corpus.jsonl에 append + 체크포인트 저장
        with corpus_path.open("a", encoding="utf-8") as f:
            for row in kept:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                global_seen.add(row["video_id"])
        done.add(cid)
        prog["done"] = list(done)
        prog["global_seen"] = list(global_seen)
        prog["funnel"][cid] = funnel_row
        _save_progress(prog)
        print(f"  cat {cid:>2} {entry['name']:<10} seed{funnel_row['n_seeds']} "
              f"검색{funnel_row['searched']}→중복제거{funnel_row['deduped']}→상세{funnel_row['detailed']}"
              f"→일치{funnel_row['categoryid_pass']}→채택{funnel_row['final']} "
              f"(채널{funnel_row['channels']}) {funnel_row['seed_dist']}")

    remaining = [c for c in seed_cats if c not in done]
    if quota_stop or remaining:
        print(f"\n미완료 {len(remaining)}개 카테고리 — 쿼터 리셋 후 같은 명령으로 재실행하면 이어서 수집.")
        return

    # 전체 완료 → funnel 표 + 요약
    _write_funnel(prog["funnel"])
    channels = set()
    n_total = 0
    with corpus_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n_total += 1
                channels.add(json.loads(line).get("channel_id"))
    short = {r["name"]: r["final"] for r in prog["funnel"].values() if r["final"] < TARGET_PER_CATEGORY}
    print(f"\n✅ 총 {n_total}편 / 고유 채널 {len(channels)}개 → {corpus_path}")
    if short:
        print(f"희소(목표 {TARGET_PER_CATEGORY} 미달, best-effort stratified): {json.dumps(short, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
