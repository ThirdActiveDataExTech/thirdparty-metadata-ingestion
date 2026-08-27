"""P05 08 — 탐색적 분석 (리뷰어 요청 5종). **사전등록 primary 결론을 바꾸지 않는 exploratory.**

07의 지표·Δrank 정의를 그대로 재사용한다.
  ① Fusion(α=.7) vs Text의 query-level Δ(MRR/NDCG/Recall) 분포 + pos/neg + Wilcoxon + boot CI
  ② RQ1 between-category vs within-category 분해 (raw −.226 vs centered −.049의 원인)
  ③ 카테고리별 Fusion(α=.5, α=.7) 효과 (query category 기준)
  ④ 카테고리별 RQ1 Spearman(gap↔영상당 median Δrank) + n + p + boot CI (video category)
  ⑤ α=.7 통계 robustness (③①과 함께)
출력: data/exploratory_results.json (+ 콘솔)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/08_exploratory.py
"""

import csv
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"


def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


A = _load("07_analyze.py", "an07")  # _minmax,_ranks,_rr_at_k,_ndcg_at_k,_recall_at_k,_spearman


def boot_ci(vals, rng, n=2000):
    vals = np.asarray(vals, float)
    bs = [rng.choice(vals, size=len(vals), replace=True).mean() for _ in range(n)]
    return round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)


def wilcoxon(a, b):
    try:
        from scipy.stats import wilcoxon as W
        d = np.asarray(a) - np.asarray(b)
        if np.allclose(d, 0):
            return None
        return round(float(W(a, b, zero_method="wilcox").pvalue), 4)
    except Exception:
        return None


def main():
    d = np.load(DATA / "retrieval" / "scores.npz", allow_pickle=True)
    qids = [str(q) for q in d["query_ids"]]; vids = [str(v) for v in d["video_ids"]]
    vidx = {v: i for i, v in enumerate(vids)}
    text_S, vis_S = d["text_scores"].astype(np.float64), d["visual_scores"].astype(np.float64)
    qrels = json.loads((DATA / "qrels.json").read_text(encoding="utf-8"))
    qcat = {q["query_id"]: q["category"] for q in json.loads((DATA / "queries_frozen.json").read_text(encoding="utf-8"))["queries"]}
    gap = {}
    with (DATA / "gap.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            gap[r["video_id"]] = {"cat": r["category"], "raw": float(r["raw_gap"]), "cen": float(r["centered_gap"])}

    qeval = [q for q in qids if q in qrels and any(float(g) >= 1 for g in qrels[q].values())]
    rng = np.random.default_rng(20260827)

    def fscore(qi, a):
        return a * A._minmax(text_S[qi]) + (1 - a) * A._minmax(vis_S[qi])

    def perq(q, a):
        qi = qids.index(q)
        order = A._ranks(fscore(qi, a))[1]
        rel_idx = {vidx[v] for v in qrels[q] if float(qrels[q][v]) >= 1 and v in vidx}
        grade = {vidx[v]: float(qrels[q][v]) for v in qrels[q] if v in vidx}
        return (A._rr_at_k(order, rel_idx, 10), A._ndcg_at_k(order, grade, 10), A._recall_at_k(order, rel_idx, 10))

    T = {q: perq(q, 1.0) for q in qeval}
    F5 = {q: perq(q, 0.5) for q in qeval}
    F7 = {q: perq(q, 0.7) for q in qeval}
    out = {"n_queries": len(qeval), "drank_def": "rank_text - rank_fusion@0.5 (양수=fusion 개선)"}

    # ── ① & ⑤ : Fusion@.7 vs Text query-level (EXPLORATORY) ──
    print("=== ① α=.7 vs Text : query-level Δ (EXPLORATORY) ===")
    q17 = {}
    for mi, mname in enumerate(["MRR", "NDCG", "Recall"]):
        dv = np.array([F7[q][mi] - T[q][mi] for q in qeval])
        pos = int((dv > 1e-9).sum()); neg = int((dv < -1e-9).sum()); zero = int((np.abs(dv) <= 1e-9).sum())
        ci = boot_ci(dv, rng); wp = wilcoxon([F7[q][mi] for q in qeval], [T[q][mi] for q in qeval])
        q17[mname] = {"mean_delta": round(float(dv.mean()), 4), "ci95": list(ci),
                      "pos": pos, "neg": neg, "zero": zero, "wilcoxon_p": wp}
        print(f"  Δ{mname}: mean={dv.mean():+.4f} CI{ci} | +{pos}/-{neg}/={zero} | Wilcoxon p={wp}")
    out["alpha07_vs_text_query_level"] = q17

    # ── ③ : 카테고리별 Fusion 효과 (query category) ──
    print("\n=== ③ 카테고리별 Fusion 효과 (ΔMRR = Fusion - Text) ===")
    catq = defaultdict(list)
    for q in qeval: catq[qcat[q]].append(q)
    cat_fx = {}
    for c in sorted(catq):
        qs = catq[c]
        d5 = np.array([F5[q][0] - T[q][0] for q in qs]); d7 = np.array([F7[q][0] - T[q][0] for q in qs])
        cat_fx[c] = {"n": len(qs), "dMRR_a5": round(float(d5.mean()), 4), "pos_a5": int((d5 > 1e-9).sum()),
                     "dMRR_a7": round(float(d7.mean()), 4), "pos_a7": int((d7 > 1e-9).sum())}
        print(f"  {c:<12} n={len(qs):>2} | α.5 ΔMRR={d5.mean():+.3f}(+{int((d5>1e-9).sum())}) | α.7 ΔMRR={d7.mean():+.3f}(+{int((d7>1e-9).sum())})")
    out["category_fusion_effect"] = cat_fx

    # ── 영상당 median Δrank (Fusion@.5) : RQ1용 ──
    perv = defaultdict(list)
    for q in qeval:
        qi = qids.index(q)
        rt = A._ranks(text_S[qi])[0]; rf = A._ranks(fscore(qi, 0.5))[0]
        for v in qrels[q]:
            if float(qrels[q][v]) >= 1 and v in vidx:
                perv[v].append(rt[vidx[v]] - rf[vidx[v]])  # Δrank
    vlist = [v for v in perv if v in gap]
    mdr = {v: float(np.median(perv[v])) for v in vlist}
    raw = np.array([gap[v]["raw"] for v in vlist]); cen = np.array([gap[v]["cen"] for v in vlist])
    dr = np.array([mdr[v] for v in vlist]); cats = [gap[v]["cat"] for v in vlist]

    # ── ② between vs within category ──
    print("\n=== ② RQ1 between vs within category 분해 (n_videos=%d) ===" % len(vlist))
    rho_raw = A._spearman(raw, dr); rho_cen = A._spearman(cen, dr)
    # between: 카테고리 평균끼리
    cmean_gap = defaultdict(list); cmean_dr = defaultdict(list)
    for i, c in enumerate(cats): cmean_gap[c].append(raw[i]); cmean_dr[c].append(dr[i])
    bc = sorted(cmean_gap)
    bgap = np.array([np.mean(cmean_gap[c]) for c in bc]); bdr = np.array([np.mean(cmean_dr[c]) for c in bc])
    rho_between = A._spearman(bgap, bdr)
    # within: 카테고리 평균 제거 후
    wgap = raw - np.array([np.mean(cmean_gap[c]) for c in cats]); wdr = dr - np.array([np.mean(cmean_dr[c]) for c in cats])
    rho_within = A._spearman(wgap, wdr)
    out["rq1_decomposition"] = {"raw_rho": rho_raw, "centered_rho": rho_cen,
                                "between_category_rho": rho_between, "within_category_rho": rho_within,
                                "n_categories": len(bc)}
    print(f"  raw ρ={rho_raw} | centered ρ={rho_cen}")
    print(f"  BETWEEN-category ρ={rho_between} (카테고리 {len(bc)}개 평균)")
    print(f"  WITHIN-category  ρ={rho_within} (카테고리 평균 제거)")

    # ── ④ 카테고리별 RQ1 Spearman + n + p + boot CI ──
    print("\n=== ④ 카테고리별 RQ1 Spearman (centered gap ↔ median Δrank) ===")
    percat = {}
    byc = defaultdict(list)
    for i, c in enumerate(cats): byc[c].append(i)
    for c in sorted(byc):
        idx = byc[c]; g = cen[idx]; y = dr[idx]
        if len(idx) < 4: r = (None, None); ci = [None, None]
        else:
            r = A._spearman(g, y)
            bs = []
            for _ in range(2000):
                s = rng.choice(len(idx), size=len(idx), replace=True)
                rr = A._spearman(g[s], y[s])[0]
                if rr is not None: bs.append(rr)
            ci = [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)] if bs else [None, None]
        percat[c] = {"n": len(idx), "rho": r[0], "p": r[1], "ci95": ci}
        print(f"  {c:<12} n={len(idx):>2} ρ={r[0]} p={r[1]} CI{ci}")
    out["rq1_per_category"] = percat

    (DATA / "exploratory_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n저장: data/exploratory_results.json")


if __name__ == "__main__":
    main()
