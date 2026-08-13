"""P05 04(revised) — 초성 pool curation (동일 규칙; 이전 판정 재사용 + 렉시콘).

query_curation_jamo.json(04b) → 이전 adjudicated의 EXCLUDE를 정확일치 재사용 + navigational/
product 렉시콘 + kids/cross-domain 명시목록으로 EXCLUDE, 나머지 topical=KEEP.
※ curation 규칙을 초성 결과에 맞춰 바꾸지 않는다(공정성). best-effort 자동 curation이며
   최종 sampled 56은 별도 정밀 검수한다.

출력: query_curation_jamo_adjudicated.json (schema: categories[].items[].adjudicated_decision)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04_curate_jamo.py
"""

import json
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# 채널/프로그램/매체/페르소나 (navigational, substring)
NAV = ["뉴스타파", "뉴스데스크", "뉴스공장", "뉴스하이킥", "뉴스토마토", "뉴스룸", "뉴스앞차기", "뉴스바사삭",
       "음악중심", "음악대장", "음악의신", "동물농장", "동물의왕국", "게임오버", "게임대장", "게임발굴단",
       "과학드림", "과학쿠키", "과학을보다", "과학할고양", "리뷰엉이", "데프콘",
       "노하우톡톡", "노하우플러스", "노하우어", "노하워즈", "부산도배", "동스쿨", "노하운",
       "루시 노하우", "노하우 루시", "노하우 베이스", "공부돼지", "공부 돼지",
       "스포츠니어스", "스포츠한입", "코미디빅리그", "코미디숏리그", "코미디 리벤지", "여행가 제이", "취미는과학"]
# navigational person/character (해당 카테고리 콘텐츠 주체 지목 — 뉴스 인물주제는 제외 안 함)
PERSON = ["코미디 김단", "코미디 김병만", "코미디 이선민", "코미디 신기루", "코미디 문세윤", "코미디 황제성",
          "여행 김범수", "여행 김동률", "여행 릴러말즈", "브이로그 류희진", "뉴스 리센느", "뉴스 두쫀쿠", "뉴스 라부부"]
PRODUCT = ["브라 추천", "고글 추천", "거치대", "스포츠브라", "스포츠 고글"]
# kids/toy/craft/quiz/cross-domain (다른 카테고리 매체/게임)
CROSS = ["영화 라면 먹방", "자동차 동화", "자동차 그리기", "자동차 놀이", "자동차 레고", "자동차 로고 맞추기",
         "자동차 만들기", "자동차 리뷰 여자", "동물 레고", "동물 동화", "과학 레고", "과학 롤링스카이", "과학 동화",
         "과학 놀이", "음악 놀이", "동물 놀이", "예능 롤", "뉴스 로블록스", "공부 동숲", "공부 디즈니", "게임 금쪽이",
         "스포츠 도박", "스포츠 suv", "코미디 로얄", "코미디 로얄 원숭이", "코미디 로얄 자르반",
         "음악 내체표", "음악 개념체계표", "음악 내용요소", "음악 가치태도"]


def main():
    jam = json.loads((DATA / "query_curation_jamo.json").read_text(encoding="utf-8"))
    adj = json.loads((DATA / "query_curation_adjudicated.json").read_text(encoding="utf-8"))
    prior_excl = {it["query"] for cid, c in adj["categories"].items() for it in c["items"]
                  if it["adjudicated_decision"] == "EXCLUDE"}

    def decide(q, dec04b):
        if dec04b in ("EXCLUDE", "FLAG"):
            return "EXCLUDE", f"04b_{dec04b}"
        if q in prior_excl:
            return "EXCLUDE", "PRIOR_EXCLUDE"
        if any(s in q for s in NAV):
            return "EXCLUDE", "NAVIGATIONAL"
        if q in PERSON:
            return "EXCLUDE", "NAVIGATIONAL_PERSON"
        if any(s in q for s in PRODUCT):
            return "EXCLUDE", "NON_CONTENT_PRODUCT"
        if q in CROSS:
            return "EXCLUDE", "CROSS_OR_KIDS"
        return "KEEP", "TOPICAL"

    out = {"_meta": {"base": "query_curation_jamo.json", "method": "초성 pool 동일-규칙 curation(best-effort)",
                     "note": "이전 EXCLUDE 재사용 + NAV/PERSON/PRODUCT/CROSS 렉시콘. sampled 56은 정밀 검수."},
           "categories": {}}
    per = {}
    for cid, c in jam["categories"].items():
        items = []
        for it in c["items"]:
            d, r = decide(it["query"], it["decision"])
            items.append({"query": it["query"], "category": c["name"],
                          "adjudicated_decision": d, "adjudication_reason": r})
        out["categories"][cid] = {"name": c["name"], "items": items}
        per[c["name"]] = Counter(x["adjudicated_decision"] for x in items)
    (DATA / "query_curation_jamo_adjudicated.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 초성 pool curation 결과 (eligible=KEEP) ===")
    print(f"  {'category':<12} {'KEEP':>5} {'EXCL':>5}  (KEEP≥4?)")
    tot = 0
    for name, cc in per.items():
        k = cc["KEEP"]; tot += k
        print(f"  {name:<12} {k:>5} {cc['EXCLUDE']:>5}  {'OK' if k >= 4 else 'FAIL'}")
    print(f"\n  eligible(KEEP) 총합: {tot}")


if __name__ == "__main__":
    main()
