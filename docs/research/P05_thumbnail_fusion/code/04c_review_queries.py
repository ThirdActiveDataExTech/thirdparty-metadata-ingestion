"""P05 04c단계 — 쿼리 curation 사람검수(반자동) 레이어 (PREREGISTRATION.md §0.2).

query_curation.json(자동 1차 분류)을 **그대로 보존**하고, 그 위에 개선 규칙으로 **reviewed
레이어**를 만든다. 자동 판정을 덮어쓰지 않고 auto/final을 함께 남겨 **변경(diff)을 감사**할
수 있게 한다. 검수는 **품질 판단이 아니라 frozen rule 위반 여부**만 본다(§0.2 discipline).

이번 패스에서 규칙으로 잡는 것(자동 1차가 놓친 systematic 오분류):
  - **navigational (공백형/복합형)**: 자동은 단일토큰만 REVIEW로 보냈으나, '여행가 제이',
    '코미디빅리그 …', '뉴스 다이브 …', '음악중심 …', '동물농장 …' 등이 KEEP에 잔존 →
    NAV_LIST 부분일치로 EXCLUDE:NAVIGATIONAL.
  - **제품(product) intent**: 카메라/렌즈/마이크/스피커/헤드셋 등 → EXCLUDE:NON_CONTENT_SERVICE.
  - **substring 오탐 복원**: '리스'가 '플레이리스트'/'앨리스'를 오매치한 NON_CONTENT_SERVICE
    등, HARD 서비스어에 해당 안 되면 REVIEW로 되돌림(사람이 최종 판정).

⚠️ 한계(정직히): 의미적 mismatch(예: '뉴스 강아지')와 NAV_LIST에 없는 인물/채널명은 여전히
KEEP에 남는다 → **사람/피드백 루프의 최종 KEEP 스캔 + 14 카테고리 일관성 감사가 필요**하다.
이 파일은 그 감사의 '변경 근거가 남은 reviewed 후보'이지 최종 확정본이 아니다.

입력: query_curation.json
출력: query_curation_reviewed.json (auto_decision/auto_reason + final_decision/final_reason + changed)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04c_review_queries.py
"""

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IN_PATH = DATA_DIR / "query_curation.json"
OUT_PATH = DATA_DIR / "query_curation_reviewed.json"

# 스캔+피드백으로 확정한 navigational 명(부분일치로 매치)
NAV_LIST = [
    "여행가 제이", "여행하는김씨",
    "코미디빅리그", "코미디 빅리그", "코미디숏리그",
    "뉴스 다이브", "뉴스타파", "뉴스공장", "뉴스데스크", "뉴스하이킥",
    "음악중심", "음악대장", "음악의신",
    "동물농장", "동물의왕국",
    "게임대장봉준", "게임발굴단",
    "과학쿠키", "과학드림", "과학을보다", "과학할고양",
]
PRODUCT_TERMS = ["카메라", "렌즈", "마이크", "스피커", "헤드셋", "이어폰", "삼각대",
                 "짐벌", "조명", "마운트", "거치대", "굿즈"]
# '진짜' 서비스/거래어(이것만 매치하면 service 유지). 아래에 없으면 substring 오탐 의심 → REVIEW.
HARD_SERVICE = ["보험", "대출", "토토", "다운로드", "다운받", "렌트", "렌탈", "중고", "매물",
                "가방", "스피커", "헤드셋", "이어폰", "쿠폰", "견적", "대여", "택배", "배송", "예매"]


def review(q, auto_dec, auto_reason):
    if any(nav in q for nav in NAV_LIST):
        return "EXCLUDE", "NAVIGATIONAL"
    if any(p in q for p in PRODUCT_TERMS):
        return "EXCLUDE", "NON_CONTENT_SERVICE"
    if auto_dec == "EXCLUDE" and auto_reason == "NON_CONTENT_SERVICE" \
            and not any(h in q for h in HARD_SERVICE):
        return "REVIEW", "SERVICE_RECHECK_SUBSTRING"   # '리스' 등 오탐 복원 → 사람 최종
    return auto_dec, auto_reason


def main():
    d = json.loads(IN_PATH.read_text(encoding="utf-8"))
    out = {"_meta": {
        "base": "query_curation.json (자동 1차)",
        "note": "reviewed 레이어. auto 보존 + final/changed. 품질 아닌 rule 위반만 판정. "
                "의미적 mismatch·미등록 인물nav는 잔존 → 루프 최종 KEEP 스캔 필요.",
        "nav_list": NAV_LIST, "product_terms": PRODUCT_TERMS,
    }, "categories": {}}
    chg = Counter()
    percat = {}
    for cid, c in d["categories"].items():
        items = []
        for it in c["items"]:
            fd, fr = review(it["query"], it["decision"], it["reason_code"])
            changed = (fd != it["decision"]) or (fr != it["reason_code"])
            items.append({"query": it["query"], "category": it["category"],
                          "source_trigger": it["source_trigger"],
                          "auto_decision": it["decision"], "auto_reason": it["reason_code"],
                          "final_decision": fd, "final_reason": fr, "changed": changed})
            if changed:
                chg[f"{it['decision']}:{it['reason_code']} → {fd}:{fr}"] += 1
        out["categories"][cid] = {"name": c["name"], "items": items}
        cc = Counter(x["final_decision"] for x in items)
        percat[c["name"]] = dict(cc)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    total_changed = sum(chg.values())
    print(f"=== reviewed diff: 변경 {total_changed}건 ===")
    for k, v in chg.most_common():
        print(f"  {v:>2}  {k}")
    print("\n=== reviewed 카테고리별 final (KEEP/REVIEW/EXCLUDE/FLAG) ===")
    for name, cc in percat.items():
        print(f"  {name:<10} KEEP {cc.get('KEEP',0):>2} | REVIEW {cc.get('REVIEW',0):>2} | "
              f"EXCLUDE {cc.get('EXCLUDE',0):>2} | FLAG {cc.get('FLAG',0)}")
    print(f"\n저장: {OUT_PATH}")
    print("⚠️ 잔존: 의미적 mismatch·미등록 인물nav는 여전히 KEEP → 루프 최종 스캔 필요.")


if __name__ == "__main__":
    main()
