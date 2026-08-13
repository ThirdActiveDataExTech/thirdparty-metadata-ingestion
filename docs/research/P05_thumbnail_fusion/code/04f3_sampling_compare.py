"""P05 04f3 — 표집 전략 3종 비교 (DIAGNOSTIC, 최종 sampling audit. freeze 안 함).

MD5 top-4(현행) / Farthest-first(분산) / Greedy k-medoid(대표+커버) 를 **같은 14 category /
같은 centered mpnet 공간**에서 계산하고 4개 지표로 비교한다. 목표는 spread 단독이 아니라
**representative + diverse**.

지표(카테고리별 → 14개 평균):
  - diversity   : 선택 4개의 평균 쌍유사도(centered). **낮을수록 다양**.
  - coverage    : pool 각 쿼리의 '선택 4개 중 최대 유사도' 평균. **높을수록 pool 대표**.
  - centrality  : 선택 4개의 '중심성'(각자 pool 전체와의 평균 유사도) 평균. **높을수록 대표(비-outlier)**.
  - outlier_rate: 선택 4개 중 중심성이 pool 중앙값 미만인 비율. **낮을수록 좋음**.

Greedy k-medoid = coverage(∑ max-sim) 최대화 그리디(= 대표점으로 pool을 덮음, submodular).
전부 결정적(seed·tie-break = md5). query 생성은 sweep 그대로. 표집 단계만 비교.

출력: 콘솔 비교표 + data/sampling_compare.json (freeze 아님)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f3_sampling_compare.py
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA = Path(__file__).resolve().parent.parent / "data"
MODEL = "paraphrase-multilingual-mpnet-base-v2"
SALT = "P05-query-sample-v1"
N = 4


def okey(q):
    return hashlib.md5((SALT + q).encode("utf-8")).hexdigest()


def md5_top(qs, k):
    return sorted(qs, key=okey)[:k]


def farthest_first(qs, sim, k):
    seed = min(range(len(qs)), key=lambda i: okey(qs[i]))
    sel = [seed]
    while len(sel) < min(k, len(qs)):
        best, bd = None, -2.0
        for j in range(len(qs)):
            if j in sel:
                continue
            mind = 1.0 - max(sim[j][s] for s in sel)
            if mind > bd or (abs(mind - bd) < 1e-12 and (best is None or okey(qs[j]) < okey(qs[best]))):
                bd, best = mind, j
        sel.append(best)
    return [qs[i] for i in sel]


def greedy_medoid(qs, sim, k):
    """coverage(∑_v max_{s∈sel} sim[v][s]) 최대화 그리디 → 대표점으로 pool 커버."""
    n = len(qs)
    sel = []
    cur = np.full(n, -1.0)   # 각 v의 현재 max 유사도
    while len(sel) < min(k, n):
        best, bg = None, -1e9
        for j in range(n):
            if j in sel:
                continue
            gain = float(np.maximum(cur, sim[j]).sum())
            if gain > bg or (abs(gain - bg) < 1e-9 and (best is None or okey(qs[j]) < okey(qs[best]))):
                bg, best = gain, j
        sel.append(best)
        cur = np.maximum(cur, sim[best])
    return [qs[i] for i in sel]


def metrics(qs, sim, sel):
    pos = {q: i for i, q in enumerate(qs)}
    S = [pos[q] for q in sel]
    # diversity
    pv = [sim[a][b] for k, a in enumerate(S) for b in S[k + 1:]]
    diversity = float(np.mean(pv)) if pv else float("nan")
    # coverage
    cov = float(np.mean([max(sim[v][s] for s in S) for v in range(len(qs))]))
    # centrality (각 쿼리: pool 전체와 평균 유사도, self 제외)
    cent = {i: float((sim[i].sum() - sim[i][i]) / (len(qs) - 1)) for i in range(len(qs))} if len(qs) > 1 else {0: 0.0}
    sel_cent = float(np.mean([cent[s] for s in S]))
    med = float(np.median(list(cent.values())))
    outlier = float(np.mean([cent[s] < med for s in S]))
    return {"diversity": round(diversity, 3), "coverage": round(cov, 3),
            "centrality": round(sel_cent, 3), "outlier_rate": round(outlier, 2)}


def main():
    adj = json.loads((DATA / "query_curation_adjudicated.json").read_text(encoding="utf-8"))
    per_cat = {c["name"]: [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
               for c in adj["categories"].values()}
    all_q = sorted({q for qs in per_cat.values() for q in qs})
    print(f"임베딩 {len(all_q)}쿼리 …")
    emb = SentenceTransformer(MODEL).encode(all_q, convert_to_numpy=True,
                                            normalize_embeddings=True).astype(np.float64)
    idx = {q: i for i, q in enumerate(all_q)}

    methods = {"md5": md5_top, "farthest": farthest_first, "medoid": greedy_medoid}
    agg = {m: {"diversity": [], "coverage": [], "centrality": [], "outlier_rate": []} for m in methods}
    out = {"_meta": {"objective": "representative+diverse (not spread-only)"}, "categories": {}}
    reviews_in = {m: False for m in methods}

    for name in sorted(per_cat):
        qs = per_cat[name]
        E = emb[[idx[q] for q in qs]]
        Ec = E - E.mean(0, keepdims=True)
        nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        sim = (Ec / nrm) @ (Ec / nrm).T
        out["categories"][name] = {}
        for m, fn in methods.items():
            sel = fn(qs, sim, N) if m != "md5" else fn(qs, N)
            mt = metrics(qs, sim, sel)
            out["categories"][name][m] = {"selected": sel, **mt}
            for k in agg[m]:
                agg[m][k].append(mt[k])
            if name == "자동차" and "자동차 리뷰" in sel:
                reviews_in[m] = True

    print("\n=== 14 category 평균 (방법별) ===")
    print(f"  {'method':<10} {'diversity↓':>11} {'coverage↑':>10} {'centrality↑':>12} {'outlier↓':>9}")
    for m in methods:
        d = {k: float(np.mean(v)) for k, v in agg[m].items()}
        print(f"  {m:<10} {d['diversity']:>11.3f} {d['coverage']:>10.3f} "
              f"{d['centrality']:>12.3f} {d['outlier_rate']:>9.2f}")

    print("\n=== sanity: '자동차 리뷰'(대표 쿼리)가 선택되는가 ===")
    for m in methods:
        print(f"  {m:<10} {'포함' if reviews_in[m] else '미포함'}  → {', '.join(out['categories']['자동차'][m]['selected'])}")

    print("\n=== 대표 카테고리 3종 선택 비교 ===")
    for name in ["자동차", "동물", "코미디"]:
        print(f"[{name}]")
        for m in methods:
            print(f"   {m:<10} {', '.join(out['categories'][name][m]['selected'])}")

    (DATA / "sampling_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA/'sampling_compare.json'} (freeze 아님)")


if __name__ == "__main__":
    main()
