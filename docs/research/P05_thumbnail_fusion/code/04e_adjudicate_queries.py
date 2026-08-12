"""P05 04e단계 — REVIEW 100 최종 adjudication (PREREGISTRATION.md §0.2, 2026-08-11b freeze).

query_curation_final.json(04d)의 **REVIEW 100건만** 대상으로 intent 판정을 확정한다.
KEEP 341·EXCLUDE 106·FLAG 13은 **건드리지 않는다**(마지막 단계 전체 재선별 방지).

판정 규칙(§0.2, freeze):
  - intent_class = A(navigational) / B(topical-content) / C(ambiguous) 를 기록하되,
    **최종 decision은 반드시 KEEP/EXCLUDE 이진**(C는 판정 과정의 중간 상태일 뿐 pool에 안 남김).
  - KEEP: query 자체에서 해당 카테고리 YouTube content 탐색의 **합리적 dominant intent**를
    식별 가능("100% 확실"이 아니라 "합리적 dominant"; 음악감상·동물원 KEEP).
  - EXCLUDE: navigational(특정 entity 지칭) / category mismatch / non-content·service /
    **또는 content-search intent 식별 불가**(INSUFFICIENT_CONTENT_INTENT; 예: 자동차 낙엽).
  - 웹 확인은 "이 문자열이 특정 entity를 지칭하는가"에만 사용(품질 판단 금지). 근거 불충분 C → EXCLUDE.

⚠️ 판정 사유는 "이상해서"가 아니라 "content 탐색 intent 식별 불가"로 기록(reviewer 방어).

입력: query_curation_final.json
출력: query_curation_adjudicated.json (auto/reviewed/final/adjudicated + intent_class + evidence)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04e_adjudicate_queries.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IN_PATH = DATA_DIR / "query_curation_final.json"
OUT_PATH = DATA_DIR / "query_curation_adjudicated.json"

WEB = "web-checked"   # entity 여부를 웹으로 확인한 항목 표시

# query -> (intent_class, decision, reason, evidence)
#   intent A=navigational, B=topical-content, C=ambiguous(→binary 확정)
ADJ = {
    # ══════════════════ B → KEEP (합리적 dominant content intent, 36) ══════════════════
    "영화리뷰": ("B", "KEEP", "TOPICAL_CONTENT", "영화 리뷰 콘텐츠 탐색"),
    "영화추천": ("B", "KEEP", "TOPICAL_CONTENT", "영화 추천 콘텐츠 탐색"),
    "음악퀴즈": ("B", "KEEP", "TOPICAL_CONTENT", "음악 퀴즈 콘텐츠"),
    "음악방송": ("B", "KEEP", "TOPICAL_CONTENT", "음악 방송/무대 클립 콘텐츠"),
    "음악듣기": ("B", "KEEP", "TOPICAL_CONTENT", "음악 감상 콘텐츠"),
    "음악감상": ("B", "KEEP", "TOPICAL_CONTENT", "음악 감상 콘텐츠"),
    "동물병원": ("B", "KEEP", "TOPICAL_CONTENT", "동물병원/수의 관련 정보·브이로그 콘텐츠"),
    "동물원": ("B", "KEEP", "TOPICAL_CONTENT", "동물원 영상 콘텐츠"),
    "스포츠분석": ("B", "KEEP", "TOPICAL_CONTENT", "스포츠 분석 콘텐츠"),
    "스포츠카": ("B", "KEEP", "TOPICAL_CONTENT", "스포츠카 리뷰/주행 콘텐츠"),
    "스포츠클래식": ("B", "KEEP", "TOPICAL_CONTENT", f"명경기/레전드 스포츠 콘텐츠; 특정 프로그램 미확인 ({WEB})"),
    "스포츠댄스": ("B", "KEEP", "TOPICAL_CONTENT", "댄스스포츠 경기/강습 콘텐츠"),
    "스포츠스태킹": ("B", "KEEP", "TOPICAL_CONTENT", "스포츠스태킹(컵쌓기) 콘텐츠"),
    "여행유튜버": ("B", "KEEP", "TOPICAL_CONTENT", "여행 브이로그 콘텐츠 탐색(특정 채널 미지칭)"),
    "여행영어": ("B", "KEEP", "TOPICAL_CONTENT", "여행 영어회화 학습 콘텐츠"),
    "게임스토리": ("B", "KEEP", "TOPICAL_CONTENT", "게임 스토리 해설 콘텐츠"),
    "게임보이": ("B", "KEEP", "TOPICAL_CONTENT", "게임보이(콘솔) 레트로 게임 콘텐츠"),
    "공부자극": ("B", "KEEP", "TOPICAL_CONTENT", "공부자극 영상(확립된 장르)"),
    "과학실험": ("B", "KEEP", "TOPICAL_CONTENT", "과학실험 콘텐츠"),
    "과학고": ("B", "KEEP", "TOPICAL_CONTENT", "과학고 입시/생활 정보 콘텐츠"),
    "과학동화": ("B", "KEEP", "TOPICAL_CONTENT", "과학 동화(어린이 과학) 콘텐츠"),
    "여행 남자 코디": ("B", "KEEP", "TOPICAL_CONTENT", "여행 남성 코디(여행룩) 콘텐츠 장르"),
    "여행 다꾸": ("B", "KEEP", "TOPICAL_CONTENT", "여행 다이어리 꾸미기(다꾸) 콘텐츠 장르"),
    "여행 다이어리 꾸미기": ("B", "KEEP", "TOPICAL_CONTENT", "다이어리 꾸미기 콘텐츠 장르"),
    "여행 플레이리스트": ("B", "KEEP", "TOPICAL_CONTENT", "여행 플레이리스트(consumption intent 명확)"),
    "공부 플레이리스트": ("B", "KEEP", "TOPICAL_CONTENT", "공부 플레이리스트(확립된 장르)"),
    "공부 남돌 플레이리스트": ("B", "KEEP", "TOPICAL_CONTENT", "공부 플레이리스트(남돌 곡) 콘텐츠 장르"),
    "여행 다이소 꿀템": ("B", "KEEP", "TOPICAL_CONTENT", "다이소 꿀템 하울/추천 콘텐츠(content marker)"),
    "여행 다이소 필수템": ("B", "KEEP", "TOPICAL_CONTENT", "다이소 필수템 추천 콘텐츠(content marker)"),
    "공부 다이소 꿀템": ("B", "KEEP", "TOPICAL_CONTENT", "다이소 공부템 추천 콘텐츠(content marker)"),
    "자동차 강의": ("B", "KEEP", "TOPICAL_CONTENT", "자동차 강의/교육 콘텐츠"),
    "자동차 달리는 소리": ("B", "KEEP", "TOPICAL_CONTENT", "차량 주행음 ASMR/사운드 콘텐츠(content marker '소리')"),

    # ══════════════════ A → EXCLUDE (navigational, 특정 entity 지칭, 13) ══════════════════
    "스포츠한입": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", f"야구 유튜브 채널 (namu.wiki, {WEB})"),
    "스포츠니어스": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", f"축구 언론사 Sports-G 채널 ({WEB})"),
    "게임오버": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", f"게임 유튜브 팀/채널 (namu.wiki, {WEB})"),
    "뉴스룸": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "JTBC 뉴스룸 등 특정 뉴스 프로그램명"),
    "뉴스토마토": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "뉴스토마토(newstomato) 언론 매체명"),
    "노하우부산도배": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "부산 도배 사업체/채널명(지명+업종)"),
    "노하우동스쿨": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "특정 스쿨/채널명"),
    "공부돼지": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", f"한국사/입시 유튜브 채널(이루리) ({WEB})"),
    "스탠드업 코미디 가브리엘": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "코미디언 가브리엘(개인) 지칭"),
    "스탠드업 코미디 가프리": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "코미디언(개인) 지칭(가브리엘 변형 추정)"),
    "스탠딩 코미디 가브리엘": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "코미디언 가브리엘(개인) 지칭"),
    "예능 나영석": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", "PD 나영석(개인) 지칭"),
    "취미는 과학 나폴리": ("A", "EXCLUDE", "NAVIGATIONAL_ENTITY", f"EBS 프로그램 '취미는 과학' ({WEB})"),

    # ══════════════════ C → EXCLUDE (INSUFFICIENT_CONTENT_INTENT, 48) ══════════════════
    # 단일토큰 name-like(미검증)·불명확
    "음악줄넘기": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "음악/줄넘기 결합의 dominant content intent 불명확"),
    "예능매치": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", f"제목형, 특정 프로그램/장르 미확인 ({WEB})"),
    "예능총회": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제목형, content intent 불명확"),
    "예능교회": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제목형, content intent 불명확"),
    "예능사관학교": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", f"프로그램 제목형, 미확인 ({WEB})"),
    "뉴스앞차기": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "세그먼트/채널 제목형 추정, 불명확"),
    "노하우톡톡": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "채널명 추정(미검증), content intent 불명확"),
    "노하우플러스": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "채널명 추정(미검증), content intent 불명확"),
    "노하우어": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "name-like 토큰, content intent 불명확"),
    "노하워즈": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "채널명 추정(미검증), content intent 불명확"),
    "노하운": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "truncated/garbled 토큰, 불명확"),
    # 자동차 AMBIGUOUS_INTENT
    "자동차 가족": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "자동차+가족 결합의 content intent 불명확"),
    "자동차 강아지": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "자동차 납치": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "자동차 날개": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "자동차 낙엽": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    # 음악 AMBIGUOUS_INTENT
    "음악 나오는 사탕": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제품/노벨티, 음악 content intent 아님"),
    "음악 나이": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "음악 나오는 도로": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "멜로디로드 노벨티, 음악 content dominant 아님"),
    "음악 나무": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "음악 나오는 캔디": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제품/노벨티, 음악 content intent 아님"),
    "음악 다이어트": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "역순 표현, dominant intent 불명확"),
    # 스포츠 AMBIGUOUS_INTENT
    "스포츠 나우": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제목형/불명확"),
    "스포츠 다운펌": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "다운펌(헤어)과 결합 불명확"),
    # 여행 AMBIGUOUS_INTENT
    "여행 남자키": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "여행 남사친": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "여행 다이어트": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "여행 다리미": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "제품/결합 불명확"),
    # 게임 AMBIGUOUS_INTENT
    "게임 운동": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "게임+운동 dominant intent 불명확"),
    "게임 남모": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "garbled/불명확"),
    "게임 남자친구": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "게임 남친": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "게임 납치": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "게임 남편": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    # 뉴스 AMBIGUOUS_INTENT
    "뉴스 강아지": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "뉴스 카테고리 content intent 불명확"),
    "뉴스 감기": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "뉴스 가족": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "뉴스 강아지 산책": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    "뉴스 닥스훈트": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "content intent 불명확"),
    # 교육 AMBIGUOUS_INTENT
    "공부 남과 비교": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    "공부 남돌": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "공부+남돌 dominant intent 불명확"),
    "공부 담배": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "결합 불명확"),
    # AMBIGUOUS_TARGET 잔여
    "동물 나루토 춤": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "'나루토 춤' 결합 garbled/불명확"),
    "공부 날씨의 아이": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "영화 '날씨의 아이'+공부 결합 incoherent"),
    # SERVICE_RECHECK 잔여
    "음악 나라의 앨리스": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "odd 표현, 음악 content intent 불명확"),
    # SHOP 잔여(bare store, content marker 없음)
    "여행 다이소": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "bare 매장+카테고리, content marker 없음"),
    # MAYBE_NAVIGATIONAL 잔여
    "자동차 달인": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "'달인' 프로그램/일반 불명확, content intent 약함"),
    "과학 남궁원": ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "인물명-like(미검증), content intent 불명확"),

    # ══════════════════ C → EXCLUDE (CROSS_DOMAIN, 다른 카테고리 매체 명시, 4) ══════════════════
    "자동차 만화": ("C", "EXCLUDE", "CROSS_DOMAIN", "만화 매체 명시 → 애니/키즈 카테고리 콘텐츠(자동차 stratum과 불일치)"),
    "동물 나오는 영화": ("C", "EXCLUDE", "CROSS_DOMAIN", "영화 매체 명시 → 영화 카테고리 콘텐츠(동물 stratum과 불일치)"),
    "동물 나오는 애니": ("C", "EXCLUDE", "CROSS_DOMAIN", "애니 매체 명시 → 애니 카테고리 콘텐츠"),
    "동물 나오는 웹툰": ("C", "EXCLUDE", "CROSS_DOMAIN", "웹툰 매체 명시 → 웹툰 카테고리 콘텐츠"),

    # ══════════════════ C → EXCLUDE (NON_CONTENT_PRODUCT, 3) ══════════════════
    "자동차 가죽시트 클리너": ("C", "EXCLUDE", "NON_CONTENT_PRODUCT", "제품명(사용법/리뷰 marker 없음)"),
    "자동차 나노 코팅제": ("C", "EXCLUDE", "NON_CONTENT_PRODUCT", "제품명(사용법/리뷰 marker 없음)"),
    "스포츠 나시": ("C", "EXCLUDE", "NON_CONTENT_PRODUCT", "의류 제품명(content marker 없음)"),
}


def main():
    d = json.loads(IN_PATH.read_text(encoding="utf-8"))
    out = {"_meta": {
        "base": "query_curation_final.json (04d)",
        "rule": "PREREGISTRATION §0.2 04e adjudication (freeze 2026-08-11b)",
        "note": "REVIEW 100만 adjudication(KEEP/EXCLUDE/FLAG 불변). intent A/B/C 기록 + 최종 이진. "
                "KEEP=합리적 dominant content intent 식별 가능; EXCLUDE=nav/mismatch/service/product "
                "또는 content intent 식별 불가(INSUFFICIENT_CONTENT_INTENT). 웹확인은 entity 여부에만.",
        "n_adjudicated": len(ADJ),
    }, "categories": {}}

    seen = set()
    percat = defaultdict(lambda: Counter())     # category -> Counter(final adjudicated decision)
    intent_ct = Counter()
    reason_ct = Counter()
    missing = []      # REVIEW인데 ADJ에 없음
    stray = set(ADJ)  # ADJ에 있는데 REVIEW 아님(오타 검출)

    for cid, c in d["categories"].items():
        name = c["name"]
        items = []
        for it in c["items"]:
            fd = it["final_decision"]
            base = {k: it.get(k) for k in ("query", "category", "source_trigger",
                    "auto_decision", "auto_reason", "reviewed_decision", "reviewed_reason",
                    "final_decision", "final_reason", "changed_by_semantic")}
            if fd == "REVIEW":
                q = it["query"]
                if q not in ADJ:
                    missing.append((name, q))
                    # 미판정은 안전하게 EXCLUDE(근거 불충분)로 종결 — 절대 잔여 REVIEW 남기지 않음
                    intent, dec, reason, ev = "C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", "판정 목록 누락(안전 제외)"
                else:
                    intent, dec, reason, ev = ADJ[q]
                    stray.discard(q)
                    seen.add(q)
                base.update({"intent_class": intent, "adjudicated_decision": dec,
                             "adjudication_reason": reason, "evidence": ev})
                percat[name][dec] += 1
                intent_ct[intent] += 1
                reason_ct[reason] += 1
            else:
                # KEEP/EXCLUDE/FLAG: adjudicated = final 그대로(불변), audit 위해 필드만 채움
                base.update({"intent_class": "-", "adjudicated_decision": fd,
                             "adjudication_reason": "UNCHANGED_FROM_FINAL", "evidence": ""})
                percat[name][fd] += 1
            items.append(base)
        out["categories"][cid] = {"name": name, "items": items}

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 리포트 ──────────────────────────────────────────────
    if missing:
        print(f"⚠️ ADJ 누락 REVIEW {len(missing)}건(안전 EXCLUDE 처리됨): {missing}")
    if stray:
        print(f"⚠️ ADJ에 있으나 REVIEW 아님(오타 의심) {len(stray)}건: {sorted(stray)}")

    # REVIEW 전용 집계(decision별 사유 분리)
    rev_dec = Counter()
    excl_reason = Counter()
    keep_reason = Counter()
    for cid, c in d["categories"].items():
        for it in c["items"]:
            if it["final_decision"] == "REVIEW":
                intent, dec, reason, _ = ADJ.get(
                    it["query"], ("C", "EXCLUDE", "INSUFFICIENT_CONTENT_INTENT", ""))
                rev_dec[dec] += 1
                (keep_reason if dec == "KEEP" else excl_reason)[reason] += 1

    print(f"=== REVIEW 100 adjudication 결과 ===")
    print(f"  판정 목록 {len(ADJ)}건 / 실제 REVIEW 매칭 {len(seen)}건")
    print(f"  intent_class(REVIEW 100): {dict(intent_ct)}")
    print(f"  REVIEW 100 → KEEP {rev_dec['KEEP']} / EXCLUDE {rev_dec['EXCLUDE']}")
    print(f"  KEEP 사유: {dict(keep_reason)}")
    print(f"  EXCLUDE 사유: {dict(excl_reason)}")

    # ── Appendix QA 표: category별 raw→최종 funnel (재현성 증빙) ──
    raw_ct = Counter()          # category별 raw(=전체 후보) 수
    fromrev_ct = Counter()      # REVIEW → KEEP 복귀 수
    for cid, c in d["categories"].items():
        for it in c["items"]:
            raw_ct[c["name"]] += 1
            if it["final_decision"] == "REVIEW":
                dec = ADJ.get(it["query"], ("C", "EXCLUDE", "", ""))[1]
                if dec == "KEEP":
                    fromrev_ct[c["name"]] += 1

    print("\n=== Appendix QA 표: category별 raw→eligible funnel ===")
    hdr = f"  {'category':<12} {'raw':>4} {'KEEP':>5} {'←REV':>5} {'EXCL':>5} {'FLAG':>4} {'제외율%':>7}"
    print(hdr)
    rows = []
    tot_keep = tot_excl = tot_flag = tot_raw = 0
    for name in sorted(percat):
        k = percat[name]["KEEP"]; e = percat[name]["EXCLUDE"]; f = percat[name]["FLAG"]
        r = raw_ct[name]; fr = fromrev_ct[name]
        tot_keep += k; tot_excl += e; tot_flag += f; tot_raw += r
        rate = (e / (k + e) * 100) if (k + e) else 0
        print(f"  {name:<12} {r:>4} {k:>5} {fr:>5} {e:>5} {f:>4} {rate:>6.1f}")
        rows.append((name, r, k, fr, e, f, round(rate, 1)))
    print(f"  {'TOTAL':<12} {tot_raw:>4} {tot_keep:>5} {sum(fromrev_ct.values()):>5} "
          f"{tot_excl:>5} {tot_flag:>4} {tot_excl/(tot_keep+tot_excl)*100:>6.1f}")

    min_n = min(percat[name]["KEEP"] for name in percat)
    min_cat = min(percat, key=lambda n: percat[n]["KEEP"])
    qa_path = DATA_DIR / "query_curation_qa_table.csv"
    with qa_path.open("w", encoding="utf-8") as fp:
        fp.write("category,raw,keep_eligible,returned_from_review,exclude,flag,exclude_rate_pct\n")
        for row in rows:
            fp.write(",".join(str(x) for x in row) + "\n")
        fp.write(f"TOTAL,{tot_raw},{tot_keep},{sum(fromrev_ct.values())},{tot_excl},{tot_flag},"
                 f"{round(tot_excl/(tot_keep+tot_excl)*100,1)}\n")
        fp.write(f"# min eligible category: {min_cat} (n={min_n}); "
                 f"No category fell below n={min_n} — feasible for N<=14*{min_n}={14*min_n}\n")

    print(f"\n✅ clean eligible pool(KEEP) = {tot_keep}편  "
          f"(최소 category = {min_cat} {min_n}편 → N<={14*min_n}까지 균형표집 가능)")
    print(f"저장: {OUT_PATH}")
    print(f"저장: {qa_path}")


if __name__ == "__main__":
    main()
