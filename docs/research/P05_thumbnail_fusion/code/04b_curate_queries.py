"""P05 04b단계 — 쿼리 후보 선별(curation) (PREREGISTRATION.md §0.2 선별 규칙).

raw 560 후보(query_candidates.json)에 **사전 freeze된 분류 규칙**을 적용해 decision+reason을
전량 기록한다(exclusion log → Appendix funnel). 명백한 것은 규칙이 자동 처리하고, 애매·
navigational 가능성은 REVIEW로 라우팅해 **사람이 동일 정의로 재검토**한다.

decision:
  - EXCLUDE / NON_CONTENT_SERVICE : 상품·서비스·거래·금융·도구 검색(보험·대출·가방·앱 등)
  - EXCLUDE / CATEGORY_MISMATCH   : 실제 주제가 딴 카테고리(음악·게임·장난감·키즈)
  - FLAG    / TOO_BROAD           : 사실상 카테고리/trigger 단어 → 제외 아님, Pilot에서 처리
  - REVIEW  / AMBIGUOUS           : 단일 토큰(navigational 가능)·형식소비·경계 → 사람 판정
  - KEEP    / TOPICAL             : (잠정) 다토큰 + 위 규칙 미해당 = 주제성 정보요구 후보
      ⚠️ KEEP은 잠정 — 공백 포함 navigational(예: '여행가 제이')이 남을 수 있어 사람이 스캔.

규칙 lists는 이 파일에 명시(= frozen operationalization). navigational은 자동 판별이
불안정하므로 auto-EXCLUDE하지 않고 REVIEW로 보낸다(고유명사 유무가 아니라 의도로 판정).

입력: query_candidates.json, query_triggers.json
출력: query_curation.json (query/category/source_trigger/decision/reason_code/review_required)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04b_curate_queries.py
"""

import json
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CAND_PATH = DATA_DIR / "query_candidates.json"
TRIG_PATH = DATA_DIR / "query_triggers.json"
OUT_PATH = DATA_DIR / "query_curation.json"

# ── frozen 규칙 lists (§0.2) ──────────────────────────────────────
SERVICE_TERMS = ["보험", "대출", "토토", "다운로드", "다운받", "렌트", "렌탈", "리스",
                 "중고", "매물", "가방", "스피커", "헤드셋", "이어폰", "구매", "할인",
                 "쿠폰", "어플", " 앱", "앱 ", "가입", "견적", "대여", "예매", "택배", "배송"]
MUSIC_TERMS = ["노래", "브금", "자장가", "플리", "플레이리스트", "팝송", "듣는 음악",
               "듣기 좋은", "가사", "asmr 음악"]           # category != 음악일 때 mismatch
KIDS_TOY_TERMS = ["장난감", "동요", "다이캐스트"]           # 어느 카테고리든 mismatch
GAME_TITLES = ["동물의숲", "동물의 숲", "동물의숲 게임"]     # 게임 아닌데 게임 제목
NAV_HINTS = ["tv", "티비", " 채널", "채널명"]               # 명백한 채널 힌트(보조)


def _norm(s):
    return re.sub(r"\s+", " ", s.strip()).lower()


def classify(query, category, triggers):
    q = _norm(query)
    toks = q.split()
    # 1) too_broad: trigger와 동일
    if q in {_norm(t) for t in triggers}:
        return "FLAG", "TOO_BROAD"
    # 2) non_content_service
    if any(t.strip() and t.strip() in q for t in SERVICE_TERMS):
        return "EXCLUDE", "NON_CONTENT_SERVICE"
    # 3) category_mismatch — 음악어(음악 카테고리 제외)
    if category != "음악" and (any(m in q for m in MUSIC_TERMS) or q.endswith("음악") or " 음악" in q):
        return "EXCLUDE", "CATEGORY_MISMATCH_MUSIC"
    # 4) category_mismatch — 게임(게임 카테고리 제외)
    if category != "게임" and (any(g in q for g in GAME_TITLES) or "게임" in q):
        return "EXCLUDE", "CATEGORY_MISMATCH_GAME"
    # 5) category_mismatch — 키즈/장난감/모델
    if any(k in q for k in KIDS_TOY_TERMS):
        return "EXCLUDE", "CATEGORY_MISMATCH_KIDS"
    # 6) navigational 힌트(보조) → REVIEW(자동제외 안 함)
    if any(h in q for h in NAV_HINTS):
        return "REVIEW", "MAYBE_NAVIGATIONAL"
    # 7) 단일 토큰(공백 없음)이면서 trigger가 아님 → navigational/broad 가능 → REVIEW
    if len(toks) == 1:
        return "REVIEW", "SINGLE_TOKEN_CHECK_NAV"
    # 8) 나머지 다토큰 = 잠정 KEEP(topical). 사람이 잔여 navigational 스캔.
    return "KEEP", "TOPICAL_TENTATIVE"


def main():
    cand = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    trig = json.loads(TRIG_PATH.read_text(encoding="utf-8"))["categories"]
    out = {"_meta": {
        "rule": "PREREGISTRATION §0.2 curation rule (frozen 2026-08-08)",
        "note": "KEEP=잠정 topical(사람이 잔여 navigational 스캔), REVIEW=사람 판정(동일 정의+사유 기록).",
        "lists": {"service": SERVICE_TERMS, "music": MUSIC_TERMS, "kids_toy": KIDS_TOY_TERMS,
                  "game_titles": GAME_TITLES, "nav_hints": NAV_HINTS},
    }, "categories": {}}
    funnel = Counter()
    percat = {}
    for cid, c in cand["categories"].items():
        name = c["name"]
        triggers = trig[cid]["triggers"]
        prov = c.get("provenance", {})
        items = []
        for q in c["candidates"]:
            dec, reason = classify(q, name, triggers)
            items.append({"query": q, "category": name, "source_trigger": prov.get(q, ""),
                          "decision": dec, "reason_code": reason,
                          "review_required": dec == "REVIEW"})
            funnel[dec] += 1
            funnel[f"{dec}:{reason}"] += 1
        out["categories"][cid] = {"name": name, "items": items}
        cc = Counter(it["decision"] for it in items)
        percat[name] = {"KEEP": cc["KEEP"], "REVIEW": cc["REVIEW"], "EXCLUDE": cc["EXCLUDE"], "FLAG": cc["FLAG"]}

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== 전체 funnel ===")
    for k in ["KEEP", "REVIEW", "FLAG", "EXCLUDE"]:
        print(f"  {k}: {funnel[k]}")
    print("  (사유) " + " / ".join(f"{k.split(':',1)[1]}={v}" for k, v in sorted(funnel.items()) if ":" in k))
    print("\n=== 카테고리별 (KEEP 잠정 / REVIEW / EXCLUDE / FLAG) ===")
    for name, cc in percat.items():
        print(f"  {name:<10} KEEP {cc['KEEP']:>2} | REVIEW {cc['REVIEW']:>2} | EXCLUDE {cc['EXCLUDE']:>2} | FLAG {cc['FLAG']}")
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
