"""P05 07단계 — 분석 (PREREGISTRATION.md §0.5·§2·§6). **골격: qrels 완성 후 실행.**

사전 등록된 분석을 '그대로' 구현한다(결과 보고 방법 선택 금지). 입력:
  - retrieval/scores.npz : query_ids, video_ids, text_scores(Q×N), visual_scores(Q×N), alpha_grid
  - qrels.json           : {query_id: {video_id: grade(0/0.5/1/1.5/2)}}  (제거 쿼리 제외됨)
  - gap.csv              : video_id, category, raw_gap, centered_gap

분석(전부 사전 고정):
  H1  : Fusion(α=0.5) vs Text — 쿼리별 RR@10 paired Wilcoxon(p<.05) + MRR@10 차>+0.05.
  지표: 시스템별 MRR@10 / NDCG@10(graded) / Recall@10.
  α sensitivity: α∈{0.0..1.0} 곡선(‘최적 α’ 주장 금지).
  H2 primary   : 영상당 median Δrank(=rank_text−rank_fusion@0.5) vs centered_gap Spearman.
  H2 secondary : (1) query-video Δrank ~ gap + category (video 클러스터-robust),
                 (2) 카테고리별(stratified) Spearman.
  H2 descriptive: 양(+) 상관 카테고리 비율.
  H2 sensitivity: raw_gap vs centered_gap로 primary 재실행.
  강건성: H1 MRR차·H2 ρ에 bootstrap 95% CI.

실행(qrels 후):
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/07_analyze.py
"""

import csv
import json
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCORES_PATH = DATA_DIR / "retrieval" / "scores.npz"
QRELS_PATH = DATA_DIR / "qrels.json"
GAP_PATH = DATA_DIR / "gap.csv"
OUT_PATH = DATA_DIR / "analysis_results.json"

ALPHA_PRIMARY = 0.5
K = 10
MRR_THRESHOLD = 0.05
N_BOOT = 1000
BOOT_SEED = 20260807


def _minmax(v):
    lo, hi = float(v.min()), float(v.max())
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v)


def _ranks(scores):
    """video index -> 1-based rank(내림차순 점수)."""
    order = np.argsort(-scores)
    r = np.empty(len(scores), dtype=int)
    r[order] = np.arange(1, len(scores) + 1)
    return r, order


def _rr_at_k(order, rel_idx, k):
    for pos, i in enumerate(order[:k], 1):
        if i in rel_idx:
            return 1.0 / pos
    return 0.0


def _ndcg_at_k(order, grade_by_idx, k):
    dcg = sum(grade_by_idx.get(i, 0.0) / np.log2(pos + 1) for pos, i in enumerate(order[:k], 1))
    ideal = sorted(grade_by_idx.values(), reverse=True)[:k]
    idcg = sum(g / np.log2(pos + 1) for pos, g in enumerate(ideal, 1))
    return dcg / idcg if idcg > 0 else 0.0


def _recall_at_k(order, rel_idx, k):
    if not rel_idx:
        return 0.0
    return len(set(order[:k]) & rel_idx) / len(rel_idx)


def _spearman(x, y):
    try:
        from scipy.stats import spearmanr
        r = spearmanr(x, y)
        return round(float(r.correlation), 4), round(float(r.pvalue), 4)
    except Exception:
        x = np.argsort(np.argsort(x)); y = np.argsort(np.argsort(y))
        return round(float(np.corrcoef(x, y)[0, 1]), 4), None


def main():
    d = np.load(SCORES_PATH, allow_pickle=True)
    qids = [str(q) for q in d["query_ids"]]
    vids = [str(v) for v in d["video_ids"]]
    vidx = {v: i for i, v in enumerate(vids)}
    text_S, vis_S = d["text_scores"].astype(np.float64), d["visual_scores"].astype(np.float64)
    alpha_grid = [float(a) for a in d["alpha_grid"]]

    qrels = json.loads(QRELS_PATH.read_text(encoding="utf-8"))
    gap = {}
    with GAP_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gap[row["video_id"]] = {"category": row["category"],
                                    "raw": float(row["raw_gap"]), "centered": float(row["centered_gap"])}

    def fusion_scores(qi, a):
        return a * _minmax(text_S[qi]) + (1 - a) * _minmax(vis_S[qi])

    # ── 시스템별 지표 + α sensitivity ──────────────────────────────
    def eval_system(score_fn):
        mrr = ndcg = rec = 0.0
        rr_per_q = []
        nq = 0
        for qi, qid in enumerate(qids):
            if qid not in qrels:
                continue
            grade_by_idx = {vidx[v]: g for v, g in qrels[qid].items() if v in vidx}
            rel_idx = {i for i, g in grade_by_idx.items() if g >= 1}
            _, order = _ranks(score_fn(qi))
            rr = _rr_at_k(order, rel_idx, K)
            rr_per_q.append(rr)
            mrr += rr
            ndcg += _ndcg_at_k(order, grade_by_idx, K)
            rec += _recall_at_k(order, rel_idx, K)
            nq += 1
        return {"MRR@10": mrr / nq, "NDCG@10": ndcg / nq, "Recall@10": rec / nq,
                "rr_per_query": rr_per_q, "n_queries": nq}

    text_eval = eval_system(lambda qi: text_S[qi])
    visual_eval = eval_system(lambda qi: vis_S[qi])
    alpha_curve = {f"{a:.1f}": eval_system(lambda qi, a=a: fusion_scores(qi, a)) for a in alpha_grid}
    fusion_primary = alpha_curve[f"{ALPHA_PRIMARY:.1f}"]

    # ── H1: Fusion(0.5) vs Text ──────────────────────────────────
    rr_t = np.array(text_eval["rr_per_query"])
    rr_f = np.array(fusion_primary["rr_per_query"])
    mrr_diff = float(rr_f.mean() - rr_t.mean())
    try:
        from scipy.stats import wilcoxon
        wp = float(wilcoxon(rr_f, rr_t, zero_method="wilcox").pvalue) if np.any(rr_f - rr_t) else 1.0
    except Exception:
        wp = None
    rng = np.random.RandomState(BOOT_SEED)
    boot = [(rr_f[s] - rr_t[s]).mean() for s in (rng.randint(0, len(rr_t), len(rr_t)) for _ in range(N_BOOT))]
    h1 = {"alpha": ALPHA_PRIMARY, "mrr_diff": round(mrr_diff, 4),
          "mrr_diff_ci95": [float(round(np.percentile(boot, 2.5), 4)), float(round(np.percentile(boot, 97.5), 4))],
          "wilcoxon_p": wp, "threshold": MRR_THRESHOLD,
          "H1_success": bool(mrr_diff > MRR_THRESHOLD and (wp is not None and wp < 0.05))}

    # ── Δrank(α=0.5): 관련영상(grade>=1)의 rank_text − rank_fusion ──
    drank = {}   # video_id -> [Δrank ...]
    for qi, qid in enumerate(qids):
        if qid not in qrels:
            continue
        rt, _ = _ranks(text_S[qi])
        rf, _ = _ranks(fusion_scores(qi, ALPHA_PRIMARY))
        for v, g in qrels[qid].items():
            if g >= 1 and v in vidx:
                drank.setdefault(v, []).append(int(rt[vidx[v]] - rf[vidx[v]]))

    # ── H2 primary: 영상당 median Δrank vs gap ───────────────────
    def h2_primary(gap_key):
        xs, ys = [], []
        for v, ds in drank.items():
            if v in gap:
                xs.append(gap[v][gap_key]); ys.append(float(np.median(ds)))
        rho, p = _spearman(xs, ys)
        # bootstrap CI
        xs, ys = np.array(xs), np.array(ys)
        brho = []
        for _ in range(N_BOOT):
            s = rng.randint(0, len(xs), len(xs))
            brho.append(_spearman(xs[s], ys[s])[0])
        return {"n_videos": len(xs), "spearman_rho": rho, "p": p,
                "rho_ci95": [float(round(np.percentile(brho, 2.5), 4)), float(round(np.percentile(brho, 97.5), 4))]}

    h2_centered = h2_primary("centered")   # primary
    h2_raw = h2_primary("raw")             # sensitivity

    # ── H2 secondary: 카테고리별 stratified Spearman + 양상관 비율 ──
    by_cat = {}
    for v, ds in drank.items():
        if v in gap:
            by_cat.setdefault(gap[v]["category"], []).append((gap[v]["centered"], float(np.median(ds))))
    strat = {}
    for c, pairs in by_cat.items():
        if len(pairs) >= 5:
            xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
            strat[c] = {"n": len(pairs), "rho": _spearman(xs, ys)[0]}
    pos_ratio = (sum(1 for s in strat.values() if s["rho"] is not None and s["rho"] > 0) / len(strat)
                 if strat else None)

    # ── H2 secondary(2): query-video 회귀 (video 클러스터-robust) ──
    reg = _cluster_robust_regression(qids, qrels, vidx, gap, text_S, fusion_scores)

    results = {
        "params": {"alpha_primary": ALPHA_PRIMARY, "alpha_grid": alpha_grid, "K": K,
                   "mrr_threshold": MRR_THRESHOLD, "n_boot": N_BOOT},
        "systems": {"Text": _strip(text_eval), "Visual": _strip(visual_eval),
                    f"Fusion@{ALPHA_PRIMARY}": _strip(fusion_primary)},
        "alpha_sensitivity": {a: _strip(e) for a, e in alpha_curve.items()},
        "H1": h1,
        "H2_primary_centered": h2_centered,
        "H2_sensitivity_raw": h2_raw,
        "H2_secondary_stratified": strat,
        "H2_descriptive_positive_category_ratio": pos_ratio,
        "H2_secondary_regression": reg,
    }
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== 요약 ===")
    print(f"Text MRR@10 {text_eval['MRR@10']:.3f} | Fusion@0.5 {fusion_primary['MRR@10']:.3f} "
          f"| ΔMRR {h1['mrr_diff']:+.3f} CI{h1['mrr_diff_ci95']} Wilcoxon p={h1['wilcoxon_p']} "
          f"→ H1 {'성공' if h1['H1_success'] else '실패/부분'}")
    print(f"H2 centered ρ={h2_centered['spearman_rho']} CI{h2_centered['rho_ci95']} (raw ρ={h2_raw['spearman_rho']})")
    print(f"카테고리 stratified 양상관 비율 {pos_ratio}")
    print(f"저장: {OUT_PATH}")


def _strip(e):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items() if k != "rr_per_query"}


def _cluster_robust_regression(qids, qrels, vidx, gap, text_S, fusion_scores):
    """query-video Δrank ~ centered_gap + C(category), video 클러스터-robust SE.
    statsmodels 있으면 수행, 없으면 스킵(사전 지정 모델식만 기록)."""
    rows = []
    for qi, qid in enumerate(qids):
        if qid not in qrels:
            continue
        rt, _ = _ranks(text_S[qi])
        rf, _ = _ranks(fusion_scores(qi, ALPHA_PRIMARY))
        for v, g in qrels[qid].items():
            if g >= 1 and v in vidx:
                rows.append({"drank": int(rt[vidx[v]] - rf[vidx[v]]),
                             "gap": gap[v]["centered"], "category": gap[v]["category"], "video": v})
    spec = "drank ~ centered_gap + C(category), cluster-robust SE by video"
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
        df = pd.DataFrame(rows).rename(columns={"gap": "centered_gap"})
        m = smf.ols("drank ~ centered_gap + C(category)", data=df).fit(
            cov_type="cluster", cov_kwds={"groups": df["video"]})
        return {"spec": spec, "n_obs": int(m.nobs),
                "gap_coef": round(float(m.params.get("centered_gap", float("nan"))), 4),
                "gap_p": round(float(m.pvalues.get("centered_gap", float("nan"))), 4)}
    except Exception as e:
        return {"spec": spec, "note": f"statsmodels 미실행({type(e).__name__}) — 사전 지정 모델식만 기록", "n_obs": len(rows)}


if __name__ == "__main__":
    main()
