"""P05 06c단계 — qrels 병합 (PREREGISTRATION §0.3·§5.3, 3인 median-of-3). **라벨링 후 실행.**

3인 독립 라벨(labeler_A/B/C.csv, C는 부분 가능)을 **median-of-3**로 병합해 최종 qrels를 만든다.

사전 고정 규칙(2026-08-13 재-freeze):
  - **최종 라벨 = median-of-3.** A=B 쌍은 median{A,B,C}=A라 C가 없어도 무방. A≠B 쌍은 C가
    tie-break(0↔2→1, |차이|1→중앙값). → **완전 3인이든 'C=불일치 심판만'이든 최종 라벨 동일.**
  - **백스톱**: C가 못 채운 A≠B 잔여 쌍만 기존 2인 규칙(|차이|1→평균 0.5/1.5, 0↔2→
    reconciliation.csv 있으면 그 값·없으면 1.0+플래그). 이 잔여는 loud하게 보고.
  - **신뢰도**: Cohen κ(A-B) 항상. C가 전 쌍 커버 시 **Fleiss κ(3-way) + pairwise κ(A-C,B-C)**.
  - **0↔2(A-B) 비율 보고**(라벨 신뢰성 지표).
  - **쿼리 제거**: 최종 qrels에서 grade≥1 문서 0개인 쿼리 제외(투명 보고).

입력(data/labeling/): labeler_A/B.csv(필수·전량), labeler_C.csv(+labeler_C_remaining.csv, 부분 가능),
                      (선택) reconciliation.csv
출력(data/): qrels.json {query_id:{video_id:grade}}, qrels_report.json

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/06_merge_qrels.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAB_DIR = DATA_DIR / "labeling"
QRELS_PATH = DATA_DIR / "qrels.json"
REPORT_PATH = DATA_DIR / "qrels_report.json"


def _load_full(who) -> dict:
    """{(qid,vid): int} — 전량(빈 grade 있으면 에러)."""
    out = {}
    with (LAB_DIR / f"labeler_{who}.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            g = (r.get("grade") or "").strip()
            if g == "":
                raise ValueError(f"미입력 grade: {r['query_id']}/{r['video_id']} (labeler {who})")
            out[(r["query_id"], r["video_id"])] = int(g)
    return out


def _load_partial(*files) -> dict:
    """여러 파일에서 grade 채워진 것만 union(뒤 파일이 우선)."""
    out = {}
    for fn in files:
        p = LAB_DIR / fn
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                g = (r.get("grade") or "").strip()
                if g != "":
                    out[(r["query_id"], r["video_id"])] = int(g)
    return out


def _load_recon() -> dict:
    p = LAB_DIR / "reconciliation.csv"
    if not p.exists():
        return {}
    with p.open(encoding="utf-8-sig") as f:
        return {(r["query_id"], r["video_id"]): float(r["grade"]) for r in csv.DictReader(f)}


def _cohen(a, b):
    try:
        from sklearn.metrics import cohen_kappa_score
        return (round(float(cohen_kappa_score(a, b)), 3),
                round(float(cohen_kappa_score(a, b, weights="quadratic")), 3))
    except Exception:
        n = len(a)
        if n == 0:
            return (None, None)
        obs = sum(1 for x, y in zip(a, b) if x == y) / n
        ca, cb = Counter(a), Counter(b)
        exp = sum((ca[c] / n) * (cb[c] / n) for c in (0, 1, 2))
        return (round((obs - exp) / (1 - exp), 3) if exp < 1 else 1.0, None)


def _fleiss(table):
    """table: N×3 카테고리 카운트(행합 = rater 수, 동일). Fleiss κ."""
    t = np.asarray(table, float)
    if t.size == 0:
        return None
    n_items = t.shape[0]
    n_r = t.sum(1)[0]
    if n_r < 2:
        return None
    p_j = t.sum(0) / (n_items * n_r)
    P_i = ((t ** 2).sum(1) - n_r) / (n_r * (n_r - 1))
    P_bar, P_e = P_i.mean(), (p_j ** 2).sum()
    return round(float((P_bar - P_e) / (1 - P_e)), 3) if P_e < 1 else 1.0


def main():
    A, B = _load_full("A"), _load_full("B")
    C = _load_partial("labeler_C.csv", "labeler_C_remaining.csv")
    recon = _load_recon()
    keys = sorted(set(A) & set(B))
    if set(A) != set(B):
        print(f"⚠️ A·B 키 불일치 {len(set(A) ^ set(B))} — 교집합 {len(keys)}쌍만 사용")

    la = [A[k] for k in keys]
    lb = [B[k] for k in keys]
    k_ab, k_ab_q = _cohen(la, lb)

    final = {}
    severe_ab, uncovered, method = [], [], Counter()
    for k in keys:
        a, b = A[k], B[k]
        if a == b:
            g = float(a); method["agree_AB"] += 1
        elif k in C:
            g = float(sorted([a, b, C[k]])[1]); method["median3"] += 1   # median-of-3
        else:                                   # A≠B, C 없음 → 백스톱
            if abs(a - b) == 2:
                severe_ab.append(k)
                g = recon.get(k, 1.0)
                if k not in recon:
                    uncovered.append({"query_id": k[0], "video_id": k[1], "A": a, "B": b, "type": "0v2"})
                    method["backstop_0v2_fallback"] += 1
                else:
                    method["backstop_0v2_recon"] += 1
            else:
                g = (a + b) / 2.0               # |차이|1 → 0.5/1.5
                uncovered.append({"query_id": k[0], "video_id": k[1], "A": a, "B": b, "type": "diff1"})
                method["backstop_diff1_avg"] += 1
        final.setdefault(k[0], {})[k[1]] = g
        if a != b and abs(a - b) == 2:
            if k not in severe_ab:
                severe_ab.append(k)

    # 3인 신뢰도(전 쌍 C 커버 시 Fleiss + pairwise)
    all3 = [k for k in keys if k in C]
    full3 = len(all3) == len(keys)
    fleiss = pair_ac = pair_bc = None
    if all3:
        table = [[sum(1 for g in (A[k], B[k], C[k]) if g == c) for c in (0, 1, 2)] for k in all3]
        fleiss = _fleiss(table)
        pair_ac = _cohen([A[k] for k in all3], [C[k] for k in all3])[0]
        pair_bc = _cohen([B[k] for k in all3], [C[k] for k in all3])[0]

    disagree_ab = sum(1 for k in keys if A[k] != B[k])
    removed = [q for q, docs in final.items() if not any(v >= 1 for v in docs.values())]
    for q in removed:
        del final[q]

    QRELS_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(keys)
    report = {
        "n_pairs": n, "n_queries_final": len(final),
        "aggregation": "median-of-3", "method_counts": dict(method),
        "cohen_kappa_AB": k_ab, "cohen_kappa_AB_quadratic": k_ab_q,
        "disagree_AB": disagree_ab, "disagree_AB_rate": round(disagree_ab / n, 4) if n else 0,
        "severe_0v2_AB": len(severe_ab), "severe_0v2_AB_rate": round(len(severe_ab) / n, 4) if n else 0,
        "C_labeled_pairs": len(C), "C_full_coverage": full3,
        "fleiss_kappa_3way": fleiss, "n_items_all3": len(all3),
        "cohen_kappa_AC": pair_ac, "cohen_kappa_BC": pair_bc,
        "uncovered_disagreements": uncovered, "n_uncovered": len(uncovered),
        "removed_zero_relevance_queries": removed, "n_removed": len(removed),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"쌍 {n} | A-B κ={k_ab}(quad {k_ab_q}) | A≠B {disagree_ab}({report['disagree_AB_rate']}) | 0↔2 {len(severe_ab)}")
    print(f"집계: {dict(method)}")
    print(f"C 라벨 {len(C)}쌍 | 완전3인={full3} | Fleiss κ={fleiss} (all-3 {len(all3)}쌍) | κ(A-C)={pair_ac} κ(B-C)={pair_bc}")
    print(f"최종 쿼리 {len(final)}개 (grade0 제거 {len(removed)})")
    if uncovered:
        print(f"⚠️ 미해결 불일치 {len(uncovered)}건 → 06b로 C 마저 라벨 or reconciliation.csv 후 재실행")
    print(f"저장: {QRELS_PATH} , {REPORT_PATH}")


if __name__ == "__main__":
    main()
