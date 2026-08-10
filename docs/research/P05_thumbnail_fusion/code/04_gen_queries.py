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

파이프라인: trigger → Suggest → 정규화 → (매체변형)dedup → **카테고리 귀속** → 균형 후보
  → (Query Pilot + 사람 최종 검수) → query freeze. 한 쿼리가 여러 카테고리 trigger에서
  나오면 억지로 분류하지 않고 drop(ambiguous)한다.

출력(data/):
  - query_candidates.json : 카테고리별 후보 + provenance(출처 trigger) + _meta(생성 시각,
    dedup_rule_version, 귀속 규칙, ambiguous drop 수) + ambiguous_dropped 목록(Appendix 추적용)

실행: 저장소 루트에서 (query_triggers.json을 먼저 검수·freeze한 뒤)
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04_gen_queries.py
"""

import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRIGGERS_PATH = DATA_DIR / "query_triggers.json"
OUT_PATH = DATA_DIR / "query_candidates.json"

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
MIN_LEN = 2                # 너무 짧은 완성어 제외(글자 수)
MAX_PER_CATEGORY = 40      # 카테고리별 후보 상한(Pilot 전 넉넉히)
DEDUP_RULE_VERSION = "v2-conservative-2026-08-07c"  # 완전일치 + 매체접미어만 병합


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


# 검색 '의도'가 아니라 매체를 가리키는 일반 접미어 — 이것만 붙은 변형은 같은 의도로 본다.
# (예: "강아지 영상" ≡ "강아지"). 반면 "축구 하이라이트"는 의도가 다르므로 보존한다.
GENERIC_TAILS = ["영상", "동영상", "유튜브", "채널", "쇼츠", "shorts", "모음", "영상모음"]


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip()).lower()


def _canon(q: str) -> str:
    """일반 접미어를 제거한 표준형(의도 동일성 비교용). **공백으로 구분된 말미 토큰만**
    제거한다 — '강아지 동영상'→'강아지'(OK), 그러나 '동영상'의 '영상'만 잘라 '동'을
    만드는 오류를 방지."""
    c = _norm(q)
    changed = True
    while changed:
        changed = False
        for t in GENERIC_TAILS:
            if c.endswith(" " + t):
                c = c[: -(len(t) + 1)].strip()
                changed = True
                break
    return c


def _is_near_dup(cand: str, kept: list) -> bool:
    """보수적 dedup: (a) 정규화 완전일치, (b) 일반 접미어만 다른 경우만 중복 취급.
    ⚠️ substring/토큰유사도로 제거하지 않는다 — '축구' vs '축구 하이라이트'처럼
    검색 의도가 다른 변형을 보존하기 위함. 미세한 의도 중복은 query freeze 시 사람이
    수동 검토로 제거(공개)."""
    cn, cc = _norm(cand), _canon(cand)
    for k in kept:
        if cn == _norm(k):
            return True
        if cc and cc == _canon(k):
            return True
    return False


def main():
    doc = json.loads(TRIGGERS_PATH.read_text(encoding="utf-8"))
    if doc.get("_meta", {}).get("status") != "frozen":
        print("⚠️ query_triggers.json status가 'frozen'이 아님 — 검수·확정 후 실행 권장.")
    sweep = doc["_meta"].get("syllable_sweep", [])
    ts = datetime.now(timezone.utc).isoformat()
    cat_name = {cid: e["name"] for cid, e in doc["categories"].items()}

    # 1) 전역 수집: (완성어, 출처 카테고리, 출처 trigger)
    raw = []
    for cid, entry in doc["categories"].items():
        for trig in entry["triggers"]:
            for t in [trig] + [f"{trig} {s}" for s in sweep]:
                for sug in fetch_suggest(t):
                    if len(sug.replace(" ", "")) >= MIN_LEN:
                        raw.append({"query": sug, "category": cid, "trigger": trig})
                time.sleep(0.15)
        print(f"  수집 cat {cid:>2} {entry['name']} 누적 raw {len(raw)}")

    # 2) 정규화(canon)로 그룹핑 → 유사(매체)변형 병합
    groups = defaultdict(list)
    for r in raw:
        groups[_canon(r["query"])].append(r)

    # 3) 카테고리 귀속: 단일 카테고리에서만 나온 쿼리만 귀속. 여러 카테고리 → 애매 → drop.
    assigned = defaultdict(list)   # cid -> [{query, trigger}]
    ambiguous = []
    for canon, entries in groups.items():
        cats = sorted(set(e["category"] for e in entries))
        rep = min((e["query"] for e in entries), key=len)  # 가장 짧은(일반) 형태 대표
        if len(cats) == 1:
            cid = cats[0]
            trig = next(e["trigger"] for e in entries)
            assigned[cid].append({"query": rep, "source_trigger": trig})
        else:
            ambiguous.append({"query": rep, "categories": cats})

    # 4) 카테고리별 상한 적용 + 출력 구성
    out = {"_meta": {
        "source": "YouTube publicly observable search suggestions (client=firefox, ds=yt, hl=ko)",
        "note": "후보 pool. 최종 쿼리 수·선택은 Query Pilot(§0.6) + 사람 최종 검수 후 freeze.",
        "generation_timestamp": ts, "dedup_rule_version": DEDUP_RULE_VERSION,
        "min_len": MIN_LEN, "max_per_category": MAX_PER_CATEGORY,
        "assignment_rule": "쿼리는 단일 카테고리 trigger에서만 나온 경우 그 카테고리에 귀속; 복수 카테고리에서 나오면 억지 분류 없이 drop(ambiguous).",
        "n_ambiguous_dropped": len(ambiguous),
    }, "categories": {}, "ambiguous_dropped": ambiguous}

    total = 0
    for cid in doc["categories"]:
        items = assigned.get(cid, [])[:MAX_PER_CATEGORY]
        out["categories"][cid] = {
            "name": cat_name[cid],
            "candidates": [it["query"] for it in items],
            "provenance": {it["query"]: it["source_trigger"] for it in items},
            "n_kept": len(items),
        }
        total += len(items)
        prev = [it["query"] for it in items][:6]
        print(f"cat {cid:>2} {cat_name[cid]:<10} 귀속 {len(items):>2} : {prev}{'…' if len(items)>6 else ''}")

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n총 후보 {total}개, 애매(복수 카테고리)로 drop {len(ambiguous)}개 → {OUT_PATH}")
    print("다음: Query Pilot(§0.6) + 사람 최종 검수로 카테고리당 최종 개수(≈4) 선택·freeze.")


if __name__ == "__main__":
    main()
