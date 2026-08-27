"""P05 08c — 정답지(qrels) 집계 방식 민감도 (테스트용, 논문 반영 X).

라벨 집계를 median-of-3 대신 여러 방식으로 바꿔 RQ2(H1)·RQ1 primary가 얼마나 흔들리는지 본다.
집계: AB평균, BC평균, AC평균 (요청) + median3, mean3 (참고).
relevant = grade >= 1. NDCG는 graded(평균값 그대로) 사용.
Δrank = rank_text - rank_fusion@0.5. RQ1 = centered gap ↔ 영상당 median Δrank Spearman.

출력: 콘솔 비교표만 (파일 저장 안 함).
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/08c_qrels_sensitivity.py
"""

import csv
import importlib.util
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"
L = DATA / "labeling"


def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


A7 = _load("07_analyze.py", "an07")


def read(f):
    with open(L / f, newline="", encoding="utf-8-sig") as fh:
        return {(r["query_id"], r["video_id"]): int(r["grade"]) for r in csv.DictReader(fh)}


def main():
    gA, gB, gC = read("labeler_A.csv"), read("labeler_B.csv"), read("labeler_C.csv")
    pairs = list(gA)
    AGG = {
        "median3": lambda k: st.median([gA[k], gB[k], gC[k]]),
        "mean3":   lambda k: (gA[k] + gB[k] + gC[k]) / 3,
        "AB평균":   lambda k: (gA[k] + gB[k]) / 2,
        "BC평균":   lambda k: (gB[k] + gC[k]) / 2,
        "AC평균":   lambda k: (gA[k] + gC[k]) / 2,
    }

    d = np.load(DATA / "retrieval" / "scores.npz", allow_pickle=True)
    qids = [str(q) for q in d["query_ids"]]; vids = [str(v) for v in d["video_ids"]]
    vidx = {v: i for i, v in enumerate(vids)}
    text_S, vis_S = d["text_scores"].astype(np.float64), d["visual_scores"].astype(np.float64)
    gap = {}
    with (DATA / "gap.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            gap[r["video_id"]] = float(r["centered_gap"])

    def fscore(qi, a):
        return a * A7._minmax(text_S[qi]) + (1 - a) * A7._minmax(vis_S[qi])

    print(f"{'집계':<8}{'#쿼리':>6}{'Text MRR':>10}{'Fus.5 MRR':>11}{'ΔMRR':>8}{'Wilcox p':>10}"
          f"{'Fus.7 MRR':>11}{'Text Rec':>10}{'Fus.7 Rec':>11}{'RQ1 ρ(cen)':>12}{'p':>8}")
    for name, fn in AGG.items():
        qr = defaultdict(dict)
        for k in pairs:
            qr[k[0]][k[1]] = fn(k)
        qeval = [q for q in qids if q in qr and any(v >= 1 for v in qr[q].values())]

        def perq(q, a):
            qi = qids.index(q)
            order = A7._ranks(fscore(qi, a))[1]
            rel = {vidx[v] for v in qr[q] if qr[q][v] >= 1 and v in vidx}
            grade = {vidx[v]: qr[q][v] for v in qr[q] if v in vidx}
            return A7._rr_at_k(order, rel, 10), A7._recall_at_k(order, rel, 10)

        tmrr = [perq(q, 1.0)[0] for q in qeval]
        f5mrr = [perq(q, 0.5)[0] for q in qeval]
        f7mrr = [perq(q, 0.7)[0] for q in qeval]
        trec = [perq(q, 1.0)[1] for q in qeval]
        f7rec = [perq(q, 0.7)[1] for q in qeval]
        try:
            from scipy.stats import wilcoxon
            wp = wilcoxon(f5mrr, tmrr, zero_method="wilcox").pvalue if not np.allclose(np.array(f5mrr) - np.array(tmrr), 0) else 1.0
        except Exception:
            wp = None
        # RQ1
        perv = defaultdict(list)
        for q in qeval:
            qi = qids.index(q)
            rt = A7._ranks(text_S[qi])[0]; rf = A7._ranks(fscore(qi, 0.5))[0]
            for v in qr[q]:
                if qr[q][v] >= 1 and v in vidx:
                    perv[v].append(rt[vidx[v]] - rf[vidx[v]])
        vl = [v for v in perv if v in gap]
        rho, p = A7._spearman(np.array([gap[v] for v in vl]), np.array([np.median(perv[v]) for v in vl]))
        print(f"{name:<8}{len(qeval):>6}{np.mean(tmrr):>10.3f}{np.mean(f5mrr):>11.3f}"
              f"{np.mean(f5mrr)-np.mean(tmrr):>+8.3f}{(round(wp,3) if wp is not None else '-'):>10}"
              f"{np.mean(f7mrr):>11.3f}{np.mean(trec):>10.3f}{np.mean(f7rec):>11.3f}{rho:>12}{(p if p is not None else '-'):>8}")


if __name__ == "__main__":
    main()
