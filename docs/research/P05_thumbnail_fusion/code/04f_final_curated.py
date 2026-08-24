"""P05 04f(최종) — 사람 큐레이션 표집 (2026-08-24, cap 비구속 재동결 후 품질 정밀선정).

배경: cap=50 초성 절단 편향을 제거(cap=300 비구속)한 뒤, 순수 MD5 랜덤은 노이즈 많은
자동완성 풀에서 채널·작품·기관명·무의미 조합을 그대로 뽑는 한계가 확인됨(리뷰 피드백).
→ 최종 선정을 **사전 정의 기준 기반 사람 큐레이션**으로 전환(IR 테스트컬렉션 표준).
기준: 채널·프로그램·작품·인물·기관명·무의미 조합·과도한 특정 제외; [카테고리+주제] 형태의
topical 쿼리; 카테고리 내 주제 다양성 확보; 검색·라벨링 前 시점(가설 결과에 blind).
모든 쿼리는 자동완성 후보 풀(query_curation_jamo_adjudicated.json의 KEEP)에서 선정 →
"사용자 검색어 근거" 성격 유지. 근거 없는 쿼리는 본 스크립트가 경고한다.

입력: query_curation_jamo_adjudicated.json (KEEP 풀 검증용)
출력: queries_frozen.json (교체; 이전 cap50 backup은 별도 보존)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f_final_curated.py
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# 사람 큐레이션 결정(카테고리당 5). 모두 자동완성 후보 풀에서 선정.
CURATED = {
    "게임": ["게임 추천 모바일", "게임 공략", "게임 리뷰", "게임 순위", "게임 스토리"],
    "과학기술": ["과학 실험", "과학 다큐멘터리", "과학 미스터리", "기술 트렌드", "과학 상식"],
    "교육": ["공부 잘하는 법", "공부 자극", "공부 계획 세우는 법", "공부 브이로그", "교육 다큐멘터리"],
    "노하우/스타일": ["등산 노하우", "살림 노하우", "절약 노하우", "캠핑 노하우", "스타일 코디"],
    "뉴스/정치": ["뉴스 속보", "뉴스 요약", "시사 토론", "뉴스 인터뷰", "뉴스 실시간"],
    "동물": ["동물 다큐멘터리", "동물 브이로그", "동물 구조", "동물 웃긴영상", "동물 도감"],
    "스포츠": ["스포츠 뉴스", "스포츠 다큐멘터리", "스포츠 하이라이트", "스포츠 분석", "스포츠 예능"],
    "엔터테인먼트": ["예능 레전드", "예능 먹방", "예능 추천", "예능 토크쇼", "예능 귀신"],
    "여행/이벤트": ["여행 브이로그", "여행 먹방", "여행 추천", "여행 준비물", "여행 룩북"],
    "영화/애니메이션": ["영화 리뷰", "영화 추천", "영화 결말 포함", "애니메이션 추천", "애니메이션 명장면"],
    "음악": ["음악 추천", "노래 부르는법", "노래방", "노래 커버", "음악 라이브"],
    "인물/블로그": ["브이로그 일상", "브이로그 먹방", "브이로그 직장인", "브이로그 대학생", "브이로그 여행"],
    "자동차": ["자동차 리뷰", "자동차 시승기", "자동차 추천", "자동차 세차", "자동차 튜닝"],
    "코미디": ["코미디 영화", "코미디 드라마", "코미디 몰아보기", "코미디 공포", "코미디 스탠드업"],
}


def main():
    adj = json.loads((DATA / "query_curation_jamo_adjudicated.json").read_text(encoding="utf-8"))
    pool = {c["name"]: {it["query"] for it in c["items"]} for c in adj["categories"].values()}
    keep = {c["name"]: {it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"}
            for c in adj["categories"].values()}

    # 검증: 모든 큐레이션 쿼리가 자동완성 후보(가능하면 KEEP)인지
    warn = 0
    for cat, qs in CURATED.items():
        assert len(qs) == 5, f"{cat}: 5개가 아님({len(qs)})"
        for q in qs:
            if q not in pool.get(cat, set()):
                print(f"  ⚠️ [{cat}] '{q}' 는 자동완성 후보 풀에 없음(근거 부족)"); warn += 1
            elif q not in keep.get(cat, set()):
                print(f"  ℹ️ [{cat}] '{q}' 는 후보엔 있으나 KEEP 아님(REVIEW/EXCLUDE)"); warn += 1

    frozen, i = [], 0
    for cat in sorted(CURATED):
        for q in CURATED[cat]:
            frozen.append({"query_id": f"q{i:02d}", "query": q, "category": cat}); i += 1
    out = {"_meta": {"rule": "PREREGISTRATION §0.2 — 기준 기반 사람 큐레이션(자동완성 풀, 2026-08-24)",
                     "method": "YouTube 자동완성 후보 → 사전정의 포함·배제 기준 + 주제 다양성으로 "
                               "카테고리당 5 선정(검색·라벨링 前, 결과 blind). 채널·작품·기관·무의미 제외.",
                     "n": len(frozen), "k_per_category": 5,
                     "supersedes": "queries_frozen_cap50_backup.json(cap50 MD5), _v2(medoid), _v1(md5 음절)"},
           "queries": frozen}
    (DATA / "queries_frozen.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 큐레이션 {len(frozen)}쿼리 → queries_frozen.json (경고 {warn}건)")
    for cat in sorted(CURATED):
        print(f"  [{cat}] {' · '.join(CURATED[cat])}")


if __name__ == "__main__":
    main()
