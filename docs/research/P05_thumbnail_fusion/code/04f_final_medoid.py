"""P05 04f(final) — 최종 표집: greedy k-medoid (PREREGISTRATION §0.2, 2026-08-14 amendment).

04f(md5 hash) → 04f3 sampling audit 결과, 사전 정의 기준(representative + diverse)에서
**greedy k-medoid**가 coverage·diversity 최고, centrality는 md5와 동률 → 최종 채택.
이 스크립트가 md5 04f + 04h(freeze)를 대체해 queries_frozen.json을 생성한다.

■ 결정적(deterministic) 규칙 — 모두 고정, 자유 파라미터 최소:
  - 방법 = **greedy max-coverage k-medoid**(facility-location). clustering 단계·threshold **없음**.
    각 스텝에서 coverage(∑_v max_{s∈sel} sim[v][s]) 최대화하는 실제 쿼리 1개 선택.
  - k = **4**(= 카테고리별 표본 수). eligible<4면 전부(모든 카테고리 ≥18이라 항상 4).
  - 유사도 = category별 mean-centering(공유어 제거) 후 cos. 인코더 = mpnet(고정)+normalize.
  - **RNG 없음**(greedy는 random init 없음). 동점 tie-break = **md5(SALT+query) 최소**.
  - 재현성 보강: eligible 임베딩을 npz로 **캐시** → 이후 라이브러리 drift와 무관하게 표본 재현.

query_id = (카테고리 이름순, 카테고리 내 medoid 선택순) q00..q55.
이전 md5 표본은 queries_frozen_v1.json으로 보존됨.

입력: query_curation_adjudicated.json
출력: queries_frozen.json, query_eligible_emb.npz(임베딩 캐시)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f_final_medoid.py
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA = Path(__file__).resolve().parent.parent / "data"
ADJ = DATA / "query_curation_adjudicated.json"
OUT = DATA / "queries_frozen.json"
EMB_CACHE = DATA / "query_eligible_emb.npz"
MODEL = "paraphrase-multilingual-mpnet-base-v2"
SALT = "P05-query-sample-v1"     # tie-break 전용 고정값
N = 4
POOL_TOPK = 10                    # §0.6 확정(불변)


def okey(q):
    return hashlib.md5((SALT + q).encode("utf-8")).hexdigest()


def greedy_medoid(qs, sim, k):
    """coverage 최대화 greedy. 첫 선택=global medoid(행합 최대), 이후 marginal coverage 최대. md5 tie-break."""
    n = len(qs)
    sel, cur = [], np.full(n, -1.0)
    while len(sel) < min(k, n):
        best, bg = None, -1e18
        for j in range(n):
            if j in sel:
                continue
            gain = float(np.maximum(cur, sim[j]).sum())
            if gain > bg or (abs(gain - bg) < 1e-9 and (best is None or okey(qs[j]) < okey(qs[best]))):
                bg, best = gain, j
        sel.append(best); cur = np.maximum(cur, sim[best])
    return [qs[i] for i in sel]


def main():
    adj = json.loads(ADJ.read_text(encoding="utf-8"))
    per_cat = {c["name"]: [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
               for c in adj["categories"].values()}
    all_q = sorted({q for qs in per_cat.values() for q in qs})

    # 임베딩(캐시 있으면 재사용 → 완전 재현)
    if EMB_CACHE.exists():
        z = np.load(EMB_CACHE, allow_pickle=True)
        if list(z["queries"]) == all_q:
            emb = z["emb"].astype(np.float64)
            print("임베딩 캐시 재사용")
        else:
            emb = None
    else:
        emb = None
    if emb is None:
        print(f"임베딩 {len(all_q)}쿼리(mpnet) …")
        emb = SentenceTransformer(MODEL).encode(all_q, convert_to_numpy=True,
                                                normalize_embeddings=True).astype(np.float64)
        np.savez_compressed(EMB_CACHE, queries=np.array(all_q), emb=emb.astype(np.float32))
    idx = {q: i for i, q in enumerate(all_q)}

    selections = {}
    for name in sorted(per_cat):
        qs = per_cat[name]
        E = emb[[idx[q] for q in qs]]
        Ec = E - E.mean(0, keepdims=True)
        nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        sim = (Ec / nrm) @ (Ec / nrm).T
        selections[name] = greedy_medoid(qs, sim, N)

    # query_id 부여
    frozen, i = [], 0
    for name in sorted(selections):
        for q in selections[name]:
            frozen.append({"query_id": f"q{i:02d}", "query": q, "category": name}); i += 1

    out = {"_meta": {
        "rule": "PREREGISTRATION §0.2 FREEZE — greedy k-medoid (2026-08-14 sampling amendment)",
        "method": "greedy max-coverage k-medoid (facility-location); no clustering/threshold/RNG",
        "params": {"k_per_category": N, "encoder": MODEL, "normalize": True,
                   "similarity": "per-category mean-centered cosine", "tiebreak": f"md5('{SALT}'+query)",
                   "embedding_cache": EMB_CACHE.name},
        "n": len(frozen), "pool_topk": POOL_TOPK,
        "supersedes": "queries_frozen_v1.json (md5-hash 04f)",
        "note": "retrieval 이후 변경 금지. 자동차 등 detailing 편중은 eligible pool(=generation) 특성이며 표집으로 제거 불가 → limitation.",
    }, "queries": frozen}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ FREEZE(medoid): {len(frozen)}쿼리 → {OUT}")
    for name in sorted(selections):
        print(f"  [{name}] {', '.join(selections[name])}")


if __name__ == "__main__":
    main()
