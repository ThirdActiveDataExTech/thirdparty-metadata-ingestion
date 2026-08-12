"""P05 04g단계 — Query Pilot: pool size 실측으로 최종 N 확정 (PREREGISTRATION §0.6).

04f에서 뽑은 표본 쿼리에 대해 §0.3 pooling(Text∪Visual∪Fusion α-agnostic Top-K)을 돌려
**후보 pool 크기만** 실측한다. 이를 라벨링 총량으로 역산해 최종 쿼리 수(56/70/84)와 pool
depth(10 vs 7)를 **숫자로** 정한다.

⚠️ freeze discipline (HARKing 방지):
  - **측정 대상은 pool size(라벨링 부담)뿐.** MRR/relevance/성능은 계산·보고하지 않는다.
  - 표본은 04f에서 **이미 deterministic 고정**됨 — Pilot 결과로 쿼리를 고르거나 빼지 않는다.
  - retrieval 점수는 raw cosine(§0.5), 융합 전 쿼리별 min-max, α-agnostic 합집합(05와 동일 규칙).

입력: data/embeddings/embeddings.npz, data/query_sample.json (04f)
출력: 콘솔 리포트(+ data/query_pilot_report.json) — pool size 분포·라벨링 부담 역산

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04g_query_pilot.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EMB_PATH = DATA_DIR / "embeddings" / "embeddings.npz"
SAMPLE_PATH = DATA_DIR / "query_sample.json"
OUT_PATH = DATA_DIR / "query_pilot_report.json"

RET_TXT_MODEL = "paraphrase-multilingual-mpnet-base-v2"
CLIP_TXT_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]   # 0.0 … 1.0 (05와 동일)
TOPK_OPTS = [10, 7]                                    # pool depth 후보(§0.6)


def _norm(A):
    n = np.linalg.norm(A, axis=1, keepdims=True); n[n < 1e-9] = 1
    return A / n


def _minmax(v):
    lo, hi = float(v.min()), float(v.max())
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v)


def pool_for_query(t_scores, v_scores, video_ids, k):
    """α-agnostic 합집합 pool(Text∪Visual∪∪_α Fusion), Top-k."""
    def topk(s):
        return set(np.argsort(-s)[:k].tolist())
    idx = topk(t_scores) | topk(v_scores)
    tn, vn = _minmax(t_scores), _minmax(v_scores)
    for a in ALPHA_GRID:
        idx |= topk(a * tn + (1 - a) * vn)
    return idx


def main():
    emb = np.load(EMB_PATH, allow_pickle=True)
    video_ids = emb["video_ids"]
    ret_txt = _norm(emb["ret_txt"].astype(np.float32))   # 768
    img = _norm(emb["img"].astype(np.float32))           # 512

    s = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    all56 = s["selected_flat"]
    pilot10 = {(p["query"], p["category"]) for p in s["pilot_queries"]}
    queries = [it["query"] for it in all56]

    print(f"쿼리 임베딩 중 (mpnet 768 + clip-multilingual 512) … {len(queries)}개")
    q_txt = _norm(SentenceTransformer(RET_TXT_MODEL).encode(queries, convert_to_numpy=True).astype(np.float32))
    q_img = _norm(SentenceTransformer(CLIP_TXT_MODEL).encode(queries, convert_to_numpy=True).astype(np.float32))

    # 쿼리별 pool size (Text=cos(mpnet), Visual=cos(clip↔img))
    rows = []
    for i, it in enumerate(all56):
        t_scores = q_txt[i] @ ret_txt.T
        v_scores = q_img[i] @ img.T
        sizes = {k: len(pool_for_query(t_scores, v_scores, video_ids, k)) for k in TOPK_OPTS}
        rows.append({"query": it["query"], "category": it["category"], "pool": sizes,
                     "is_pilot": (it["query"], it["category"]) in pilot10})

    def stats(vals):
        a = np.array(vals, dtype=float)
        return {"mean": round(float(a.mean()), 1), "min": int(a.min()),
                "max": int(a.max()), "median": float(np.median(a))}

    report = {"_meta": {"rule": "PREREGISTRATION §0.6 Query Pilot — pool size only (성능 미측정)",
                        "n_sample": len(all56), "alpha_grid": ALPHA_GRID, "topk_opts": TOPK_OPTS},
              "per_query": rows, "summary": {}, "labeling_projection": {}}

    print("\n=== pool size 요약 (라벨링 부담 측정용) ===")
    for k in TOPK_OPTS:
        allv = [r["pool"][k] for r in rows]
        pilv = [r["pool"][k] for r in rows if r["is_pilot"]]
        st_all, st_pil = stats(allv), stats(pilv)
        report["summary"][f"topk_{k}"] = {"all56": st_all, "pilot10": st_pil}
        print(f"  Top-{k}: 전체56 평균 {st_all['mean']} (min {st_all['min']} / max {st_all['max']} / median {st_all['median']}) | "
              f"pilot10 평균 {st_pil['mean']}")

    # 라벨링 총량 역산 = N쿼리 × 평균 pool × 2인 독립
    print("\n=== 라벨링 총량 역산 (판정 건수 = N × 평균 pool × 2인) ===")
    print(f"  {'N':>4} | " + " | ".join(f"Top-{k}" for k in TOPK_OPTS))
    for N in [56, 70, 84]:
        cells = []
        for k in TOPK_OPTS:
            avg = report["summary"][f"topk_{k}"]["all56"]["mean"]
            total = int(round(N * avg * 2))
            report["labeling_projection"][f"N{N}_top{k}"] = total
            cells.append(f"{total:>6}")
        print(f"  {N:>4} | " + " | ".join(cells))

    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT_PATH}")
    print("→ 이 pool size로 최종 N·depth 결정(성능 아닌 라벨링 부담 기준). 결정 후 queries_frozen.json freeze.")


if __name__ == "__main__":
    main()
