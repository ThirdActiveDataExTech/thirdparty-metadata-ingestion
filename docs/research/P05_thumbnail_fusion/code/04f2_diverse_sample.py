"""P05 04f2 — diversity-aware 결정적 표집 (before/after 비교, DIAGNOSTIC. freeze 안 함).

기존 04f는 카테고리 eligible을 md5 순으로 정렬해 앞 4개를 뽑았다(uniform). 문제: 한
하위주제가 pool을 지배하면(예: 자동차 디테일링 11/18) 상위 4개가 그 하위주제에 몰려
대표성이 떨어진다(자동차 리뷰/배터리/가격이 4위 밖으로 밀림).

개선: **farthest-first(k-center greedy)** — centered mpnet 공간에서 서로 **가장 먼** 4개를
뽑아 하위주제로 분산. 완전 결정적(seed=md5-1위, 동점은 md5 순 tie-break), 14개 동일 규칙.
query 생성은 sweep 그대로(변경 아님) — **표집 단계만** 개선.

⚠️ freeze 안 함. queries_sample_v2.json(제안) + before/after 비교표만 산출. 성능 무관(HARKing X).

입력: query_curation_adjudicated.json, query_sample.json(기존 04f 선정)
출력: 콘솔 비교 + data/query_sample_v2.json
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f2_diverse_sample.py
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA = Path(__file__).resolve().parent.parent / "data"
MODEL = "paraphrase-multilingual-mpnet-base-v2"
SALT = "P05-query-sample-v1"   # 04f와 동일(시드 재현)
N = 4


def order_key(q):
    return hashlib.md5((SALT + q).encode("utf-8")).hexdigest()


def farthest_first(qs, sim, k):
    """centered cos 유사도 sim에서 서로 가장 먼 k개. seed=md5-1위, 동점 md5 tie-break."""
    seed = min(range(len(qs)), key=lambda i: order_key(qs[i]))
    sel = [seed]
    while len(sel) < min(k, len(qs)):
        best, bestd = None, -2.0
        for j in range(len(qs)):
            if j in sel:
                continue
            mind = 1.0 - max(sim[j][s] for s in sel)   # 선정집합까지의 최소거리
            if mind > bestd or (abs(mind - bestd) < 1e-12 and
                                (best is None or order_key(qs[j]) < order_key(qs[best]))):
                bestd, best = mind, j
        sel.append(best)
    return [qs[i] for i in sel]


def spread(sim, idxs):
    """4개의 평균 쌍 centered-cos (낮을수록 분산 좋음)."""
    if len(idxs) < 2:
        return float("nan")
    v = [sim[a][b] for k, a in enumerate(idxs) for b in idxs[k + 1:]]
    return float(np.mean(v))


def main():
    adj = json.loads((DATA / "query_curation_adjudicated.json").read_text(encoding="utf-8"))
    old = json.loads((DATA / "query_sample.json").read_text(encoding="utf-8"))
    per_cat = {}
    for cid, c in adj["categories"].items():
        per_cat[c["name"]] = [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]

    all_q = sorted({q for qs in per_cat.values() for q in qs})
    print(f"임베딩 {len(all_q)}쿼리 …")
    emb = SentenceTransformer(MODEL).encode(all_q, convert_to_numpy=True,
                                            normalize_embeddings=True).astype(np.float64)
    idx = {q: i for i, q in enumerate(all_q)}

    out = {"_meta": {"method": "farthest-first (centered mpnet), seed=md5-1위",
                     "salt": SALT, "n": N, "note": "제안본. freeze 아님."}, "categories": {}}
    print(f"\n{'category':<12} {'spread(old→new, 낮을수록 분산↑)':<28} 선정 변화")
    tot_old = tot_new = 0.0
    for name in sorted(per_cat):
        qs = per_cat[name]
        E = emb[[idx[q] for q in qs]]
        Ec = E - E.mean(0, keepdims=True)
        nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Ec = Ec / nrm
        sim = Ec @ Ec.T
        pos = {q: i for i, q in enumerate(qs)}

        new_sel = farthest_first(qs, sim, N)
        old_sel = old["categories"][name]["selected"]
        s_old = spread(sim, [pos[q] for q in old_sel])
        s_new = spread(sim, [pos[q] for q in new_sel])
        tot_old += s_old; tot_new += s_new
        changed = set(new_sel) != set(old_sel)
        out["categories"][name] = {"selected": new_sel, "old_selected": old_sel,
                                   "spread_old": round(s_old, 3), "spread_new": round(s_new, 3)}
        print(f"{name:<12} {s_old:+.3f} → {s_new:+.3f}{'  ✔개선' if s_new < s_old - 1e-9 else ('  =' if abs(s_new-s_old)<1e-9 else '  ↑') :<12} {'CHANGED' if changed else 'same'}")

    print(f"\n평균 spread: old {tot_old/14:.3f} → new {tot_new/14:.3f} (낮을수록 하위주제 분산 좋음)")
    print("\n=== before / after 선정 (변경된 카테고리) ===")
    for name in sorted(per_cat):
        o = out["categories"][name]
        if set(o["selected"]) != set(o["old_selected"]):
            print(f"[{name}]")
            print(f"   old: {', '.join(o['old_selected'])}")
            print(f"   new: {', '.join(o['selected'])}")

    (DATA / "query_sample_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA/'query_sample_v2.json'} (제안본, freeze 아님)")


if __name__ == "__main__":
    main()
