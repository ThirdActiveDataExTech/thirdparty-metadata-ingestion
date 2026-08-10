"""P05 04단계 — 평가 쿼리 후보 생성 (PREREGISTRATION.md §0.2).

YouTube의 공개 검색 제안(Suggest) 메커니즘에서 평가 쿼리를 생성한다. seed-독립 trigger
(data/query_triggers.json)로 Suggest를 촉발 → 완성어 수집 → 중복·유사변형 제거 →
카테고리별 후보 pool 산출. **최종 개수·선택은 Query Pilot(§0.6) 이후에 freeze**한다.

⚠️ 정확한 표현: 이 결과는 "YouTube 검색 로그"가 아니라 **YouTube에서 검색 시 공개적으로
제공되는 검색 제안어**다(내부 메커니즘 미공개).

쿼터: **YouTube Data API 쿼터를 쓰지 않는다**(비공식 Suggest endpoint, 무료). 단 과도 호출은
피하고자 요청 간 sleep을 둔다.

circularity 방지: trigger는 코퍼스 seed 구가 아니라 카테고리 수준 단어이며, 쿼리를 우리
코퍼스 텍스트에서 파생하지 않는다.

출력(data/):
  - query_candidates.json : 카테고리별 후보 쿼리 + 출처 trigger(재현·Appendix용)

실행: 저장소 루트에서 (query_triggers.json을 먼저 검수·freeze한 뒤)
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04_gen_queries.py
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRIGGERS_PATH = DATA_DIR / "query_triggers.json"
OUT_PATH = DATA_DIR / "query_candidates.json"

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
MIN_LEN = 2                # 너무 짧은 완성어 제외(글자 수)
MAX_PER_CATEGORY = 40      # 카테고리별 후보 상한(Pilot 전 넉넉히)


def fetch_suggest(term: str) -> list:
    """YouTube Suggest 완성어 목록. client=firefox면 깔끔한 JSON([term,[suggestions]])."""
    params = urllib.parse.urlencode({"client": "firefox", "ds": "yt", "hl": "ko", "q": term})
    req = urllib.request.Request(f"{SUGGEST_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data[1] if isinstance(data, list) and len(data) > 1 else []
    except Exception:
        return []


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip()).lower()


def _is_near_dup(cand: str, kept: list) -> bool:
    """유사변형 제거: 정규화 후 한쪽이 다른쪽을 포함하거나 토큰 자카드>=0.6이면 중복 취급."""
    cn = _norm(cand)
    ct = set(cn.split())
    for k in kept:
        kn = _norm(k)
        if cn == kn or cn in kn or kn in cn:
            return True
        kt = set(kn.split())
        if ct and kt:
            j = len(ct & kt) / len(ct | kt)
            if j >= 0.6:
                return True
    return False


def main():
    doc = json.loads(TRIGGERS_PATH.read_text(encoding="utf-8"))
    if doc.get("_meta", {}).get("status") != "frozen":
        print("⚠️ query_triggers.json status가 'frozen'이 아님 — 검수·확정 후 실행 권장.")
    sweep = doc["_meta"].get("syllable_sweep", [])

    out = {"_meta": {
        "source": "YouTube publicly observable search suggestions (client=firefox, ds=yt, hl=ko)",
        "note": "후보 pool. 최종 쿼리 수·선택은 Query Pilot(§0.6) 후 freeze.",
        "min_len": MIN_LEN, "max_per_category": MAX_PER_CATEGORY,
    }, "categories": {}}

    total = 0
    for cid, entry in doc["categories"].items():
        name = entry["name"]
        raw = []           # (완성어, 출처 trigger)
        seen_terms = set()
        for trig in entry["triggers"]:
            terms = [trig] + [f"{trig} {s}" for s in sweep]
            for t in terms:
                for sug in fetch_suggest(t):
                    if sug not in seen_terms:
                        seen_terms.add(sug)
                        raw.append((sug, trig))
                time.sleep(0.15)
        # 정제: 길이 필터 + 유사변형 제거(등장 순서 유지)
        kept, prov = [], {}
        for sug, trig in raw:
            if len(sug.replace(" ", "")) < MIN_LEN:
                continue
            if _is_near_dup(sug, kept):
                continue
            kept.append(sug)
            prov[sug] = trig
            if len(kept) >= MAX_PER_CATEGORY:
                break
        out["categories"][cid] = {
            "name": name,
            "candidates": kept,
            "provenance": prov,   # 쿼리 → 출처 trigger(재현/Appendix)
            "n_raw": len(raw), "n_kept": len(kept),
        }
        total += len(kept)
        print(f"cat {cid:>2} {name:<10} raw {len(raw):>3} → 정제 {len(kept):>2} : {kept[:6]}{'…' if len(kept)>6 else ''}")

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n총 후보 {total}개 → {OUT_PATH}")
    print("다음: Query Pilot(§0.6)로 pool 크기 확인 후 카테고리당 최종 개수(≈4) 선택·freeze.")


if __name__ == "__main__":
    main()
