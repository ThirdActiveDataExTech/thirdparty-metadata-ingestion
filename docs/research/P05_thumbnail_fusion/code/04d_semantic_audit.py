"""P05 04d단계 — 쿼리 semantic 감사 override 레이어 (PREREGISTRATION.md §0.2).

reviewed(04c) 위에 **의미 판단 override**를 얹는다. lexical 규칙이 못 잡는 (a) semantic
category mismatch, (b) 미등록 navigational(인물/채널/프로그램명), (c) 놓친 product를
사람(LLM)이 **content-search query인가?** 기준으로 판정한다. auto/reviewed를 보존하고
override는 명시 목록으로만 적용(무엇을 왜 바꿨는지 audit).

기준(§0.2 확정): "이 쿼리의 검색 대상이 **YouTube 콘텐츠**인가?"
  - 콘텐츠(리뷰/해설/장면/정보/브이로그 등) → KEEP
  - 제품/서비스/거래 획득 → EXCLUDE:NON_CONTENT_SERVICE
  - 특정 채널/크리에이터/프로그램 찾기 → EXCLUDE:NAVIGATIONAL
  - 주제가 카테고리와 어긋남 → 대개 REVIEW(의미 애매하면 강제 제외 안 함)
  - 애매 → REVIEW(억지 KEEP/EXCLUDE 금지)

⚠️ 이 override 목록은 '명백/준명백' 사례만 담는다. 나머지 borderline은 KEEP 유지 →
14 카테고리 일관성·잔여는 피드백 루프 최종 감사.

입력: query_curation_reviewed.json
출력: query_curation_final.json (auto/reviewed/final 3층 + changed_by_semantic)
"""

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IN_PATH = DATA_DIR / "query_curation_reviewed.json"
OUT_PATH = DATA_DIR / "query_curation_final.json"

# query → (final_decision, final_reason). content-search 기준 semantic 판정.
OVERRIDES = {
    # ── 미등록 navigational(인물/채널/프로그램) → EXCLUDE ──
    "브이로그 강민경": ("EXCLUDE", "NAVIGATIONAL"), "브이로그 남서연": ("EXCLUDE", "NAVIGATIONAL"),
    "브이로그 다영": ("EXCLUDE", "NAVIGATIONAL"),
    "코미디리벤지 이선민": ("EXCLUDE", "NAVIGATIONAL"), "코미디 나이트 차밍조": ("EXCLUDE", "NAVIGATIONAL"),
    "조매력 코미디 나이트": ("EXCLUDE", "NAVIGATIONAL"), "선바 코미디 나이트": ("EXCLUDE", "NAVIGATIONAL"),
    "코미디 나이트 차밍조": ("EXCLUDE", "NAVIGATIONAL"),
    "예능 나혼자산다": ("EXCLUDE", "NAVIGATIONAL"), "예능 나혼산": ("EXCLUDE", "NAVIGATIONAL"),
    "강윤구 노하우": ("EXCLUDE", "NAVIGATIONAL"), "노하우 루시": ("EXCLUDE", "NAVIGATIONAL"),
    "루시 노하우 라이브": ("EXCLUDE", "NAVIGATIONAL"), "루시 노하우 바이올린": ("EXCLUDE", "NAVIGATIONAL"),
    # ── navigational 경계(인물 가능) → REVIEW ──
    "예능 나영석": ("REVIEW", "MAYBE_NAVIGATIONAL_PERSON"),
    "스탠드업 코미디 가브리엘": ("REVIEW", "MAYBE_NAVIGATIONAL_PERSON"),
    "스탠드업 코미디 가프리": ("REVIEW", "MAYBE_NAVIGATIONAL_PERSON"),
    "스탠딩 코미디 가브리엘": ("REVIEW", "MAYBE_NAVIGATIONAL_PERSON"),
    "취미는 과학 나폴리": ("REVIEW", "MAYBE_NAVIGATIONAL"), "과학 남궁원": ("REVIEW", "MAYBE_NAVIGATIONAL"),
    # ── 놓친 product → EXCLUDE:NON_CONTENT_PRODUCT (service와 분리) ──
    "자동차 가습기": ("EXCLUDE", "NON_CONTENT_PRODUCT"),
    "스포츠 나시 추천": ("EXCLUDE", "NON_CONTENT_PRODUCT"),
    # ── target 범위 애매('X가 나오는 Y': 카테고리 콘텐츠일 수도) → REVIEW:AMBIGUOUS_TARGET ──
    # (query가 '명백히 다른 도메인 그 자체'인 경우만 EXCLUDE. 'X 나오는 영화'는 target 범위
    #  문제라 단정 EXCLUDE 대신 REVIEW — 두 번째 AI 리뷰의 더 보수적 판단 채택.)
    "자동차 만화": ("REVIEW", "AMBIGUOUS_TARGET"),
    "동물 나오는 영화": ("REVIEW", "AMBIGUOUS_TARGET"), "동물 나오는 애니": ("REVIEW", "AMBIGUOUS_TARGET"),
    "동물 나오는 웹툰": ("REVIEW", "AMBIGUOUS_TARGET"), "동물 나루토 춤": ("REVIEW", "AMBIGUOUS_TARGET"),
    "공부 날씨의 아이": ("REVIEW", "AMBIGUOUS_TARGET"),
    # ── product vs how-to 애매(제품인지 방법인지) → REVIEW ──
    "자동차 나노 코팅제": ("REVIEW", "PRODUCT_VS_HOWTO"), "자동차 가죽시트 클리너": ("REVIEW", "PRODUCT_VS_HOWTO"),
    "스포츠 나시": ("REVIEW", "PRODUCT_VS_TOPIC"),
    # ── 의도 애매(카테고리 콘텐츠일 수도) → REVIEW:AMBIGUOUS_INTENT (mismatch 단정 아님) ──
    "자동차 강아지": ("REVIEW", "AMBIGUOUS_INTENT"), "자동차 가족": ("REVIEW", "AMBIGUOUS_INTENT"),
    "자동차 날개": ("REVIEW", "AMBIGUOUS_INTENT"), "자동차 낙엽": ("REVIEW", "AMBIGUOUS_INTENT"),
    "자동차 납치": ("REVIEW", "AMBIGUOUS_INTENT"), "자동차 강의": ("REVIEW", "TOO_BROAD_OR_SEED"),
    "자동차 달인": ("REVIEW", "MAYBE_NAVIGATIONAL"), "자동차 달리는 소리": ("REVIEW", "SOUND_ASMR"),
    "게임 운동": ("REVIEW", "AMBIGUOUS_INTENT"), "게임 남자친구": ("REVIEW", "AMBIGUOUS_INTENT"),
    "게임 남친": ("REVIEW", "AMBIGUOUS_INTENT"), "게임 남편": ("REVIEW", "AMBIGUOUS_INTENT"),
    "게임 남모": ("REVIEW", "AMBIGUOUS_INTENT"), "게임 납치": ("REVIEW", "AMBIGUOUS_INTENT"),
    "뉴스 강아지": ("REVIEW", "AMBIGUOUS_INTENT"), "뉴스 감기": ("REVIEW", "AMBIGUOUS_INTENT"),
    "뉴스 닥스훈트": ("REVIEW", "AMBIGUOUS_INTENT"), "뉴스 강아지 산책": ("REVIEW", "AMBIGUOUS_INTENT"),
    "뉴스 가족": ("REVIEW", "AMBIGUOUS_INTENT"),
    "여행 다이소": ("REVIEW", "AMBIGUOUS_SHOP"), "여행 다이소 꿀템": ("REVIEW", "AMBIGUOUS_SHOP"),
    "여행 다이소 필수템": ("REVIEW", "AMBIGUOUS_SHOP"), "여행 다꾸": ("REVIEW", "AMBIGUOUS_INTENT"),
    "여행 다이어리 꾸미기": ("REVIEW", "AMBIGUOUS_INTENT"), "여행 남자키": ("REVIEW", "AMBIGUOUS_INTENT"),
    "여행 남자 코디": ("REVIEW", "AMBIGUOUS_INTENT"), "여행 남사친": ("REVIEW", "AMBIGUOUS_INTENT"),
    "여행 다리미": ("REVIEW", "AMBIGUOUS_INTENT"), "여행 다이어트": ("REVIEW", "AMBIGUOUS_INTENT"),
    "공부 다이소 꿀템": ("REVIEW", "AMBIGUOUS_SHOP"), "공부 남돌": ("REVIEW", "AMBIGUOUS_INTENT"),
    "공부 남과 비교": ("REVIEW", "AMBIGUOUS_INTENT"), "공부 담배": ("REVIEW", "AMBIGUOUS_INTENT"),
    "음악 나오는 사탕": ("REVIEW", "AMBIGUOUS_INTENT"), "음악 나오는 캔디": ("REVIEW", "AMBIGUOUS_INTENT"),
    "음악 나오는 도로": ("REVIEW", "AMBIGUOUS_INTENT"), "음악 다이어트": ("REVIEW", "AMBIGUOUS_INTENT"),
    "음악 나이": ("REVIEW", "AMBIGUOUS_INTENT"), "음악 나무": ("REVIEW", "AMBIGUOUS_INTENT"),
    "스포츠 다운펌": ("REVIEW", "AMBIGUOUS_INTENT"), "스포츠 나우": ("REVIEW", "AMBIGUOUS_INTENT"),
}


def main():
    d = json.loads(IN_PATH.read_text(encoding="utf-8"))
    out = {"_meta": {
        "base": "query_curation_reviewed.json (04c)",
        "note": "semantic override 레이어. auto/reviewed 보존 + semantic final. content-search 기준. "
                "명백한 rule violation(navigational/cross-domain/product-service)은 EXCLUDE로 override, "
                "의미가 경계에 있는 후보는 REVIEW(AMBIGUOUS_INTENT)로 라우팅. 정상 topical/how-to는 KEEP 유지. "
                "→ 남은 REVIEW/잔여 KEEP·14 카테고리 일관성은 루프 최종 감사.",
        "n_overrides": len(OVERRIDES),
    }, "categories": {}}
    applied = Counter()
    percat = {}
    unseen = set(OVERRIDES)
    for cid, c in d["categories"].items():
        items = []
        for it in c["items"]:
            fd, fr = it["final_decision"], it["final_reason"]
            sd, sr, by_sem = fd, fr, False
            if it["query"] in OVERRIDES:
                sd, sr = OVERRIDES[it["query"]]
                by_sem = (sd, sr) != (fd, fr)
                unseen.discard(it["query"])
                if by_sem:
                    applied[f"{fd}:{fr} → {sd}:{sr.split('_')[0]}…"] += 1
            items.append({**{k: it[k] for k in ("query", "category", "source_trigger",
                          "auto_decision", "auto_reason")},
                          "reviewed_decision": fd, "reviewed_reason": fr,
                          "final_decision": sd, "final_reason": sr, "changed_by_semantic": by_sem})
        out["categories"][cid] = {"name": c["name"], "items": items}
        percat[c["name"]] = dict(Counter(x["final_decision"] for x in items))

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    tot = sum(percat[n].get("KEEP", 0) for n in percat)
    print(f"semantic override 적용 {sum(applied.values())}건 (목록 {len(OVERRIDES)}개 중)")
    for k, v in applied.most_common():
        print(f"  {v:>2}  {k}")
    if unseen:
        print(f"⚠️ 코퍼스에 없는 override 키 {len(unseen)}개(오타 확인): {sorted(unseen)[:5]}")
    print(f"\n최종 KEEP 합계 {tot}")
    print("=== 카테고리별 final (KEEP/REVIEW/EXCLUDE/FLAG) ===")
    for name, cc in percat.items():
        print(f"  {name:<10} KEEP {cc.get('KEEP',0):>2} | REVIEW {cc.get('REVIEW',0):>2} | "
              f"EXCLUDE {cc.get('EXCLUDE',0):>2} | FLAG {cc.get('FLAG',0)}")


if __name__ == "__main__":
    main()
