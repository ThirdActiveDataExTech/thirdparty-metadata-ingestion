"""P05 04f(final) — MD5 + content-filter 표집 (초성 pool, 2026-08-14 최종 sampling).

3-way audit(04f4) 결과: 초성 pool에서 MD5가 META/NAV 최저·content-natural·최고 재현성.
채택. 단순 MD5 상위4에 **04e급 필터**(META/NAV/product/near-duplicate 건너뜀)를 결합해
카테고리당 content 쿼리 4개를 결정적으로 뽑는다. 규칙:
  - 순서 = md5(SALT+query) 사전식(고정).
  - skip: META(제작/역할/도구/메타), NAV(채널/프로그램), PRODUCT, 그리고 이미 뽑힌 것과
    centered-cos ≥ 0.5(near-duplicate intent).
  - 통과한 것 앞에서부터 4개.

query_id = (카테고리 이름순, 표집순) q00..q55. 이전 medoid 표본 → queries_frozen_v2.json 보존.

입력: query_curation_jamo_adjudicated.json, query_eligible_emb_jamo.npz
출력: queries_frozen.json (교체)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f_final_md5.py
"""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
SALT = "P05-query-sample-v1"
POOL_TOPK = 10
NEAR = 0.5
K = 5   # 카테고리당 쿼리 수 (14×5 = 70, §0.6 범위 내 확대)

META = ["디렉터", "대본", "녹음 프로그램", "만드는 프로그램", "녹화 프로그램", "데스크 셋업", " 셋업",
        "편집 프로그램", "기자 연결", "리뷰 유튜버", " 유튜버", "닉네임", "제작자", "로드맵", "공모전",
        "롱폼", "릴스 찍는법", "릴스 만드는법", "녹음하는법", "리믹스 하는법", "유튜버",
        "분석가", "나레이션"]
NAV = ["뉴스타파", "뉴스데스크", "뉴스공장", "뉴스하이킥", "뉴스토마토", "뉴스룸", "뉴스바사삭", "음악중심",
       "동물농장", "동물의왕국", "게임오버", "과학드림", "과학쿠키", "과학을보다", "리뷰엉이", "데프콘",
       "노하우톡톡", "노하우플러스", "부산도배", "공부돼지", "스포츠니어스", "코미디빅리그", "취미는과학",
       "라이브 kbs", "라이브 ytn", "라이브 sbs",
       # 2026-08-24 cap 비구속 재동결: 커진 풀에서 드러난 동종(언론사/프로그램/채널) navigational 보강
       "시사타파", "시사포커스", "토익연구소", "가요대전", "동물탐험대"]
PRODUCT = ["브라 추천", "고글 추천", "거치대", "스포츠브라", "스포츠 고글"]
JUNK = ["게임 게임", "뉴스 뉴스", "여행 again", "과학 랩", "공부 랩",
        "브이로그 레전드", "뉴스 다시보기"]  # 중복/무의미/meta 토큰

# 2026-08-24 최종 정밀 검수(사전 선언된 단계): cap 비구속 재동결 후 top-제목 sanity check로
# 드러난 채널/인물/무의미 쿼리(coverage 텍스트 신호는 통과했으나 매칭이 카테고리 주제와 무관).
# 균일 규칙(navigational/persona/무의미) 적용 → 각 카테고리에서 MD5 순 다음 후보로 결정론적 교체.
MANUAL_EXCLUDE = ["연애콩", "시사 한 컵", "기술 나메", "스타일 주은 직캠",
                  "깃털 유머 턱", "코미디 타이위", "관광 메들리 트로트", "일상 녹음중",
                  # 위 8개 교체분 재검수에서 추가로 드러난 의도불명/내비게이셔널(매칭 무관)
                  "기술 한국어", "시사 일본어 학원"]


def okey(q):
    return hashlib.md5((SALT + q).encode("utf-8")).hexdigest()


def _nospace(s):
    return s.replace(" ", "")


def bad(q):
    # 공백 무시 부분일치(띄어쓰기 변형 채널·프로그램명 회피 차단). JUNK만 정확일치.
    qn = _nospace(q)
    return (any(_nospace(m) in qn for m in META) or any(_nospace(n) in qn for n in NAV)
            or any(_nospace(p) in qn for p in PRODUCT) or q in JUNK or q in MANUAL_EXCLUDE)


def main():
    adj = json.loads((DATA / "query_curation_jamo_adjudicated.json").read_text(encoding="utf-8"))
    per_cat = {c["name"]: [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
               for c in adj["categories"].values()}
    # eligible 임베딩: 캐시가 현재 KEEP 집합과 일치하면 재사용, 아니면 재생성(완전 재현)
    all_q = sorted({q for qs in per_cat.values() for q in qs})
    cache = DATA / "query_eligible_emb_jamo.npz"
    emb = None
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        if list(z["queries"]) == all_q:
            emb = z["emb"].astype(np.float64); print("임베딩 캐시 재사용")
    if emb is None:
        from sentence_transformers import SentenceTransformer
        print(f"임베딩 재생성 {len(all_q)}쿼리(mpnet) …")
        emb = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2").encode(
            all_q, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64)
        np.savez_compressed(cache, queries=np.array(all_q), emb=emb.astype(np.float32))
    idx = {q: i for i, q in enumerate(all_q)}

    selections = {}
    for name in sorted(per_cat):
        qs = sorted(per_cat[name], key=okey)     # md5 순
        E = emb[[idx[q] for q in per_cat[name]]]
        pos = {q: i for i, q in enumerate(per_cat[name])}
        Ec = E - E.mean(0, keepdims=True); nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Ec = Ec / nrm; sim = Ec @ Ec.T
        sel = []
        for q in qs:
            if bad(q):
                continue
            if any(sim[pos[q]][pos[s]] >= NEAR for s in sel):   # near-duplicate 건너뜀
                continue
            sel.append(q)
            if len(sel) == K:
                break
        # 혹시 K개 못 채우면(필터 과도) near-dup 조건만 완화해 보충
        if len(sel) < K:
            for q in qs:
                if q in sel or bad(q):
                    continue
                sel.append(q)
                if len(sel) == K:
                    break
        selections[name] = sel

    # 이전 medoid 표본 백업(최초 1회만; 재실행 시 덮어쓰지 않음)
    if (DATA / "queries_frozen.json").exists() and not (DATA / "queries_frozen_v2.json").exists():
        shutil.copy(DATA / "queries_frozen.json", DATA / "queries_frozen_v2.json")
    frozen, i = [], 0
    for name in sorted(selections):
        for q in selections[name]:
            frozen.append({"query_id": f"q{i:02d}", "query": q, "category": name}); i += 1
    out = {"_meta": {"rule": "PREREGISTRATION §0.2 — MD5+content-filter (초성 pool, cap 비구속 재동결 2026-08-24)",
                     "method": f"md5(SALT+query) 순 + skip(META/NAV/PRODUCT/JUNK/near-dup≥{NEAR}), 앞 {K}개",
                     "salt": SALT, "n": len(frozen), "pool_topk": POOL_TOPK, "cap_per_category": 300,
                     "supersedes": "queries_frozen_cap50_backup.json(cap50), _v2(medoid), _v1(md5 음절)"},
           "queries": frozen}
    (DATA / "queries_frozen.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ MD5+filter 표집 {len(frozen)}쿼리 → queries_frozen.json (medoid는 _v2 백업)")
    for name in sorted(selections):
        print(f"  [{name}] {' · '.join(selections[name])}")


if __name__ == "__main__":
    main()
