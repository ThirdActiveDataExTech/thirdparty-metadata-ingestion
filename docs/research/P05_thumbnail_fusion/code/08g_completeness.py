"""P05 08g — 완전성 보강: 사전등록/§4에서 약속했으나 미보고였던 지표 산출.
  (1) rank-biserial correlation (H1 Wilcoxon 짝지음 효과크기)
  (2) MDES (H1 paired dz, H2 Spearman |ρ|) — 귀무 결과 해석 보강
  (3) self-matching validation (§3.2 주장의 실측: 각 제목이 자기 썸네일과 더 정합한지)
  (4) 참고: NDCG/Recall 부트스트랩 CI, 양(+)상관 카테고리 비율(이미 계산된 값 재확인)
출력: 콘솔.
"""
import csv, importlib.util, json
from pathlib import Path
import numpy as np

CODE = Path(__file__).resolve().parent; DATA = CODE.parent / "data"
def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
A7 = _load("07_analyze.py", "an07")
RNG = np.random.default_rng(20260827)


def _perq_metrics():
    """Text-only(α=1)와 Fusion(α=0.5)의 쿼리별 (RR,NDCG,Recall)@10."""
    d = np.load(DATA / "retrieval" / "scores.npz", allow_pickle=True)
    qids = [str(q) for q in d["query_ids"]]; vids = [str(v) for v in d["video_ids"]]
    text_S = d["text_scores"].astype(np.float64); vis_S = d["visual_scores"].astype(np.float64)
    vidx = {v: i for i, v in enumerate(vids)}
    qrels = json.loads((DATA / "qrels.json").read_text())
    qeval = [q for q in qids if q in qrels and any(float(g) >= 1 for g in qrels[q].values())]

    def fs(qi, a): return a * A7._minmax(text_S[qi]) + (1 - a) * A7._minmax(vis_S[qi])
    def order(vec):
        o = np.argsort(-vec); return o
    def perq(q, a):
        qi = qids.index(q); o = order(fs(qi, a))
        rel = {vidx[v] for v in qrels[q] if float(qrels[q][v]) >= 1}
        grade = {vidx[v]: float(qrels[q][v]) for v in qrels[q]}
        return (A7._rr_at_k(o, rel, 10), A7._ndcg_at_k(o, grade, 10), A7._recall_at_k(o, rel, 10))
    T = np.array([perq(q, 1.0) for q in qeval]); F = np.array([perq(q, 0.5) for q in qeval])
    return T, F, len(qeval)


def rank_biserial(diff):
    """Kerby 짝지음 rank-biserial: (양의 순위합 - 음의 순위합)/전체 순위합. 0 제외."""
    d = diff[diff != 0]
    if len(d) == 0: return 0.0
    from scipy.stats import rankdata
    r = rankdata(np.abs(d))
    Rp = r[d > 0].sum(); Rn = r[d < 0].sum()
    return (Rp - Rn) / (Rp + Rn)


def main():
    from scipy.stats import norm, wilcoxon
    T, F, n = _perq_metrics()
    diff_rr = F[:, 0] - T[:, 0]

    print("=" * 60)
    print("(1) rank-biserial correlation — H1 (Fusion@0.5 vs Text, RR@10)")
    rb = rank_biserial(diff_rr)
    w = wilcoxon(F[:, 0], T[:, 0], zero_method="wilcox") if not np.allclose(diff_rr, 0) else None
    print(f"    n={n} | rank-biserial r_rb = {rb:+.3f} | Wilcoxon p={w.pvalue:.3f}")
    print(f"    (부호: 음수=융합이 Text보다 낮음. 크기 |r|<0.1 무시할 수준)")

    print("\n(2) NDCG/Recall 부트스트랩 95% CI (Δ = Fusion - Text)")
    for j, name in [(1, "NDCG@10"), (2, "Recall@10")]:
        d = F[:, j] - T[:, j]
        boot = [RNG.choice(d, len(d), replace=True).mean() for _ in range(2000)]
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"    Δ{name:<9} = {d.mean():+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")

    print("\n(3) MDES — 표본이 탐지 가능한 최소 효과 (α=.05 양측, power=.80)")
    z = norm.ppf(0.975) + norm.ppf(0.80)  # 2.802
    dz = z / np.sqrt(n)
    sd_rr = diff_rr.std(ddof=1)
    print(f"    H1(paired, n={n}): 최소탐지 dz = {dz:.3f}  (= RR@10 {dz*sd_rr:+.3f} 단위)")
    n_h2 = 270
    r_h2 = np.tanh(z / np.sqrt(n_h2 - 3))
    print(f"    H2(Spearman, n={n_h2}): 최소탐지 |ρ| = {r_h2:.3f}  (관측 ρ=-0.049는 이 이하)")

    print("\n(4) self-matching validation — §3.2 주장 실측")
    d = np.load(DATA / "embeddings" / "embeddings.npz", allow_pickle=True)
    img = d["img"].astype(np.float64); gtxt = d["gap_txt"].astype(np.float64)
    def _norm(A):
        nn = np.linalg.norm(A, axis=1, keepdims=True); nn[nn < 1e-9] = 1; return A / nn
    Ic = _norm(img - img.mean(0)); Gc = _norm(gtxt - gtxt.mean(0))  # centered(primary 표현)
    with np.errstate(all="ignore"):  # OpenBLAS matmul 허위 경고 억제(값은 유한 검증됨)
        S = Ic @ Gc.T  # S[i,j] = cos(img_i, title_j)
    N = S.shape[0]
    own = np.diag(S)
    # (a) 각 제목이 자기 썸네일과, 무작위 다른 썸네일보다 더 정합한 비율(전체 쌍 평균)
    off = S.copy(); np.fill_diagonal(off, -np.inf)
    better = (own[:, None] > S).sum() - N  # own>own 제외
    pair_acc = better / (N * (N - 1))
    # (b) Recall@1: 제목의 최근접 썸네일이 자기 것인 비율
    r1 = np.mean(np.argmax(S, axis=0) == np.arange(N))
    print(f"    N={N} | own cos 평균 {own.mean():.3f} vs 무작위 쌍 평균 {S[~np.eye(N,dtype=bool)].mean():.3f}")
    print(f"    (a) 무작위 대비 자기매칭 우위 비율 = {pair_acc*100:.1f}%")
    print(f"    (b) 제목→썸네일 Recall@1 = {r1*100:.1f}%")


if __name__ == "__main__":
    main()
