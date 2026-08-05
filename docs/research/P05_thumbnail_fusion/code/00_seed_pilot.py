"""P05 00단계 — Seed Pilot (PREREGISTRATION.md §0.1 Seed Pilot 규격).

목적: `data/seeds.json`의 후보 seed를 **categoryId 잔존율**로 압축하기 위한 실측.
      본 수집(01) 전에 얕게 돌려, 카테고리당 잔존율 상위 seed만 남길 근거를 만든다.

핵심 원칙:
  - 잔존율 = (검색 결과 중 실제 categoryId가 그 카테고리인 비율). **커버리지 지표**이며
    gap·Δrank 어떤 가설 변수와도 직교하므로, 이 값으로 seed를 고르는 것은 성능 튜닝이 아님.
  - 얕게: seed당 **relevance 1정렬 × 1페이지(50건)** 만 조회 → seed당 약 100 units.
    (search.list 100 + videos.list 1 ≈ 101; videos.list는 50건 배치 1회.)
  - Long-form 표집 정합성 확인을 위해 search에 `videoDuration='long'`도 함께 적용해,
    본 수집과 같은 조건에서 잔존율을 잰다.

이 스크립트는 **seeds.json(후보)을 수정하지 않는다.** 두 산출물만 쓴다:
  - data/seed_pilot_report.json : seed별 후보수/장편수/카테고리일치수/잔존율 (전체 추적용)
  - data/seeds_frozen.json      : **초안(draft)** — 잔존율 하한 통과분 중 상위 3~4개 제안

seeds_frozen.json은 사람이 검토·확정(status를 'draft'→'frozen')한 뒤 본 수집(01)이 읽는다.
선택 규칙: 잔존율은 최대화 대상이 아니라 하한 가드다. 하한(RETENTION_FLOOR) 통과 seed 중
상위 KEEP_TOP_N개를 제안하되, 최종 다양성 판단은 사람이 한다(seeds.json의 selection_rule).

실행: 저장소 루트에서
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/00_seed_pilot.py
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
PUBLISHED_AFTER = "2025-01-01T00:00:00Z"
VIDEO_DURATION = "long"          # 본 수집과 동일 조건(Long-form only)
PILOT_ORDER = "relevance"        # 얕은 파일럿은 relevance 1정렬만
PILOT_MAX_RESULTS = 50           # 1페이지
KEEP_TOP_N = 4                   # 추천으로 남길 상위 seed 수(참고용)
RETENTION_FLOOR = 0.5            # 잔존율 하한 가드(이 미만 seed는 제안에서 제외)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROGRESS_PATH = DATA_DIR / "seed_pilot_progress.json"  # 재개용 진행 저장(seed마다 갱신)


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


def pilot_seed(svc, query: str) -> dict:
    """한 seed를 얕게 조회해 카테고리 분포를 잰다. video_id 목록도 반환(중복 진단용)."""
    resp = _retry(
        svc.search().list(
            part="id", type="video", q=query, order=PILOT_ORDER,
            relevanceLanguage=RELEVANCE_LANG, regionCode=REGION,
            publishedAfter=PUBLISHED_AFTER, videoDuration=VIDEO_DURATION,
            maxResults=PILOT_MAX_RESULTS,
        )
    )
    ids = [it["id"]["videoId"] for it in resp.get("items", [])]
    if not ids:
        return {"candidates": 0, "detailed": 0, "category_counts": {}, "video_ids": []}

    resp2 = _retry(svc.videos().list(part="snippet,contentDetails", id=",".join(ids)))
    cat_counts = {}
    detailed = 0
    for it in resp2.get("items", []):
        detailed += 1
        cid = it.get("snippet", {}).get("categoryId")
        cat_counts[cid] = cat_counts.get(cid, 0) + 1
    return {
        "candidates": len(ids),
        "detailed": detailed,
        "category_counts": cat_counts,
        "video_ids": ids,
    }


def _is_quota_error(e: HttpError) -> bool:
    status = getattr(e.resp, "status", None)
    return status is not None and int(status) in (403, 429)


def _load_progress() -> dict:
    """seed마다 저장된 진행 파일 로드. 없으면 빈 구조."""
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {"measured": {}}  # measured[cid][seed] = {candidates,in_category,retention,category_counts}


def _save_progress(prog: dict) -> None:
    PROGRESS_PATH.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def _finalize(seeds_doc: dict, prog: dict) -> None:
    """모든 seed 측정 완료 시: 리포트 + seeds_frozen.json(초안) 생성."""
    measured = prog["measured"]
    run_at = prog.get("first_run_at")
    report = {"first_run_at": run_at, "params": {
        "region": REGION, "order": PILOT_ORDER, "max_results": PILOT_MAX_RESULTS,
        "video_duration": VIDEO_DURATION, "published_after": PUBLISHED_AFTER,
        "retention_floor": RETENTION_FLOOR, "keep_top_n": KEEP_TOP_N,
    }, "categories": {}}
    frozen_draft = {"_meta": {
        "status": "draft",
        "note": "Seed Pilot 제안(하한 통과분 상위). 사람이 다양성 검토 후 status='frozen'으로 확정. 확정 시 이 목록을 seeds.json에 반영하면 01_build_corpus.py가 사용한다.",
        "generated_at": run_at,
        "retention_floor": RETENTION_FLOOR,
    }, "categories": {}}

    for cid, entry in seeds_doc["categories"].items():
        name = entry["name"]
        rows = [dict(seed=s, **measured[cid][s]) for s in entry["seeds"]]
        rows.sort(key=lambda r: (r["retention"], r["candidates"]), reverse=True)
        passed = [r for r in rows if r["retention"] >= RETENTION_FLOOR]
        suggested = (passed if passed else rows)[:KEEP_TOP_N]
        report["categories"][cid] = {
            "name": name, "seeds": rows,
            "suggested_top": [r["seed"] for r in suggested],
        }
        frozen_draft["categories"][cid] = {"name": name, "seeds": [
            {"seed": r["seed"], "retention": r["retention"], "status": "draft"}
            for r in suggested
        ]}

    (DATA_DIR / "seed_pilot_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "seeds_frozen.json").write_text(
        json.dumps(frozen_draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n✅ 전체 완료 → seed_pilot_report.json + seeds_frozen.json(status='draft')")
    print("다음 단계: seeds_frozen.json을 검토(다양성 확인)해 status='frozen'으로 확정한 뒤 01 실행.")


def main():
    seeds_doc = json.loads((DATA_DIR / "seeds.json").read_text(encoding="utf-8"))
    keys = config.get_youtube_api_keys()
    if not keys:
        raise RuntimeError("YOUTUBE_API_KEY가 없습니다 (.env 확인)")
    key_idx = 0
    svc = youtube_collector.build_service(keys[key_idx])
    print(f"API 키 {len(keys)}개 로드 (기본 + 예비 {len(keys) - 1}개). "
          "주의: 예비키가 같은 GCP 프로젝트면 쿼터를 공유합니다.")

    prog = _load_progress()
    prog.setdefault("measured", {})
    prog.setdefault("first_run_at", datetime.now(timezone.utc).isoformat())

    total = sum(len(e["seeds"]) for e in seeds_doc["categories"].values())
    done = sum(len(v) for v in prog["measured"].values())
    print(f"진행: {done}/{total} seed 측정됨 (재개 시 기존 결과 건너뜀)")

    measured_this_run = 0
    quota_stop = False
    for cid, entry in seeds_doc["categories"].items():
        if quota_stop:
            break
        name = entry["name"]
        prog["measured"].setdefault(cid, {})
        for seed in entry["seeds"]:
            if seed in prog["measured"][cid]:
                continue  # 이미 측정됨 → 쿼터 절약
            # 쿼터 소진 시 예비키로 전환하며 같은 seed 재시도
            while True:
                try:
                    res = pilot_seed(svc, seed)
                    break
                except HttpError as e:
                    if _is_quota_error(e) and key_idx + 1 < len(keys):
                        key_idx += 1
                        svc = youtube_collector.build_service(keys[key_idx])
                        print(f"  ⚠️ 쿼터 소진 → 예비키 {key_idx + 1}/{len(keys)}로 전환")
                        continue
                    if _is_quota_error(e):
                        print(f"\n⚠️ 모든 키({len(keys)}개) 쿼터 소진 — 진행분 저장됨.")
                        quota_stop = True
                        break
                    raise
            if quota_stop:
                break
            in_cat = res["category_counts"].get(cid, 0)
            retention = round(in_cat / res["detailed"], 3) if res["detailed"] else 0.0
            prog["measured"][cid][seed] = {
                "candidates": res["candidates"],
                "in_category": in_cat,
                "retention": retention,
                "category_counts": res["category_counts"],
            }
            _save_progress(prog)  # seed마다 저장 → 429에도 진행분 보존
            measured_this_run += 1
            print(f"  cat {cid:>2} {name:<10} seed '{seed}': 후보 {res['candidates']:>2} "
                  f"→ 일치 {in_cat:>2} (잔존율 {retention:.2f})")
            time.sleep(0.1)

    newdone = sum(len(v) for v in prog["measured"].values())
    if quota_stop:
        print(f"진행분 저장됨: {newdone}/{total} seed. 쿼터 리셋 후 재실행하면 이어서 측정합니다.")
        return
    print(f"\n이번 실행 {measured_this_run} seed 측정, 누적 {newdone}/{total}.")
    if newdone >= total:
        _finalize(seeds_doc, prog)
    else:
        print("아직 미완료 — 재실행으로 나머지를 마저 측정하세요.")


if __name__ == "__main__":
    main()
