"""P05 04f4 — 초성 pool 3-way 표집 비교 (최종 sampling audit. freeze 안 함).

초성 eligible pool을 고정하고 MD5 / Farthest-first / Medoid를 동일 조건으로 뽑아,
**사전 정의 자동지표**로 비교한다. 사람판단(content-fit·대표성·어색함)은 side-by-side로 별도.
※ '자동차 리뷰가 나왔나'는 판정 기준이 아님(사전 기준 없는 직관). 방어 가능한 지표만 자동집계.

자동지표(방어 가능):
  - diversity  : 선택 4개 평균 쌍 centered-cos (↓ 다양)
  - coverage   : pool 각 쿼리의 선택4개 최대유사도 평균 (↑ 대표)
  - redundant  : 선택 4개 중 centered-cos ≥ 0.5 쌍 수(≈동일 intent, ↓)
  - meta_nav   : 선택 56개 중 META(제작/역할/도구)·NAV(채널) 룰 매칭 수(↓)  ※경계는 사람확인

입력: query_curation_jamo_adjudicated.json, query_eligible_emb_jamo.npz
출력: 콘솔(자동지표표 + 14 side-by-side) + data/jamo_sampling_compare.json
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f4_jamo_sampling_compare.py
"""

import hashlib
import importlib.util
import json
from itertools import combinations
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"
SALT = "P05-query-sample-v1"

_mf = importlib.util.spec_from_file_location("mf", CODE / "04f_final_medoid.py")
mf = importlib.util.module_from_spec(_mf); _mf.loader.exec_module(mf)  # greedy_medoid, okey

# 룰 기반 META(콘텐츠 주제가 아니라 제작/역할/도구/메타)·NAV(채널/프로그램)
META = ["디렉터", "대본", "녹음 프로그램", "만드는 프로그램", "녹화 프로그램", "데스크 셋업", " 셋업",
        "편집 프로그램", "기자 연결", "리뷰 유튜버", " 유튜버", "닉네임", "제작자", "로드맵", "공모전"]
NAV = ["뉴스타파", "뉴스데스크", "뉴스공장", "뉴스하이킥", "뉴스토마토", "뉴스룸", "뉴스바사삭", "음악중심",
       "동물농장", "동물의왕국", "게임오버", "과학드림", "과학쿠키", "과학을보다", "리뷰엉이", "데프콘",
       "노하우톡톡", "노하우플러스", "부산도배", "공부돼지", "스포츠니어스", "코미디빅리그", "취미는과학",
       "라이브 kbs", "라이브 ytn", "라이브 sbs"]


def md5_top(qs, sim, k):
    return sorted(qs, key=mf.okey)[:k]


def farthest(qs, sim, k):
    seed = min(range(len(qs)), key=lambda i: mf.okey(qs[i])); sel = [seed]
    while len(sel) < min(k, len(qs)):
        best, bd = None, -2.0
        for j in range(len(qs)):
            if j in sel:
                continue
            m = 1.0 - max(sim[j][s] for s in sel)
            if m > bd or (abs(m - bd) < 1e-12 and (best is None or mf.okey(qs[j]) < mf.okey(qs[best]))):
                bd, best = m, j
        sel.append(best)
    return [qs[i] for i in sel]


def meta_nav_hit(q):
    return any(m in q for m in META) or any(n in q for n in NAV)


def main():
    adj = json.loads((DATA / "query_curation_jamo_adjudicated.json").read_text(encoding="utf-8"))
    per_cat = {c["name"]: [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
               for c in adj["categories"].values()}
    z = np.load(DATA / "query_eligible_emb_jamo.npz", allow_pickle=True)
    all_q = list(z["queries"]); emb = z["emb"].astype(np.float64)
    idx = {q: i for i, q in enumerate(all_q)}

    methods = {"MD5": md5_top, "Farthest": farthest, "Medoid": mf.greedy_medoid}
    agg = {m: {"div": [], "cov": [], "redund": 0, "metanav": 0} for m in methods}
    sidebyside = {}
    for name in sorted(per_cat):
        qs = per_cat[name]; E = emb[[idx[q] for q in qs]]
        Ec = E - E.mean(0, keepdims=True); nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Ec = Ec / nrm; sim = Ec @ Ec.T
        pos = {q: i for i, q in enumerate(qs)}
        sidebyside[name] = {}
        for m, fn in methods.items():
            sel = fn(qs, sim, 4)
            S = [pos[q] for q in sel]
            pv = [sim[a][b] for k, a in enumerate(S) for b in S[k + 1:]]
            agg[m]["div"].append(float(np.mean(pv)))
            agg[m]["cov"].append(float(np.mean([max(sim[v][s] for s in S) for v in range(len(qs))])))
            agg[m]["redund"] += sum(1 for a, b in combinations(S, 2) if sim[a][b] >= 0.5)
            agg[m]["metanav"] += sum(1 for q in sel if meta_nav_hit(q))
            sidebyside[name][m] = sel

    print("=== 자동지표 (14 category 집계; 방어 가능한 것만) ===")
    print(f"  {'method':<10} {'diversity↓':>11} {'coverage↑':>10} {'redundant쌍↓':>12} {'META/NAV(/56)↓':>15}")
    for m in methods:
        print(f"  {m:<10} {np.mean(agg[m]['div']):>11.3f} {np.mean(agg[m]['cov']):>10.3f} "
              f"{agg[m]['redund']:>12} {agg[m]['metanav']:>15}")
    print("  ※ reproducibility: 세 방법 모두 결정적(✓). META/NAV는 룰 기반 근사(경계는 사람 확인).")

    print("\n=== 14 category side-by-side (사람 평가: content-fit·대표성·어색함) ===")
    for name in sorted(per_cat):
        print(f"\n[{name}]")
        for m in methods:
            print(f"   {m:<9} {' · '.join(sidebyside[name][m])}")

    (DATA / "jamo_sampling_compare.json").write_text(
        json.dumps({"auto": {m: {"diversity": round(float(np.mean(agg[m]["div"])), 3),
                                 "coverage": round(float(np.mean(agg[m]["cov"])), 3),
                                 "redundant_pairs": agg[m]["redund"], "meta_nav": agg[m]["metanav"]}
                             for m in methods}, "side_by_side": sidebyside},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA/'jamo_sampling_compare.json'}")


if __name__ == "__main__":
    main()
