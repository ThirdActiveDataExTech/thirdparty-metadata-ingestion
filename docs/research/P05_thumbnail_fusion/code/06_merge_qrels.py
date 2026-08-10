"""P05 06b단계 — qrels 병합 (PREREGISTRATION.md §0.3·§5.3). **라벨링 완료 후 실행.**

2인 독립 라벨(labeler_A.csv / labeler_B.csv)을 병합해 최종 qrels를 만든다.

사전 고정 규칙:
  - **κ는 원(독립) 라벨로** 계산(신뢰도). unweighted + quadratic-weighted 보고.
  - 불일치 조정: **|차이|=1(0↔1,1↔2) → 평균**(0.5/1.5). **0↔2(심각) → 합의(consensus)**.
    합의값은 reconciliation.csv(query_id,video_id,grade)로 입력받는다. 미제공 0↔2는
    '합의 필요'로 출력하고 fallback=1(+플래그)로 임시 처리한다.
  - **0↔2 비율 보고**(라벨 신뢰성 지표).
  - **쿼리 제거**: 최종 qrels에서 **grade ≥ 1 문서가 0개인 쿼리 제외**(최종 qrels 기준).
    제거 수를 투명 보고.

입력(data/labeling/): labeler_A.csv, labeler_B.csv, (선택) reconciliation.csv
출력(data/):
  - qrels.json         : {query_id: {video_id: final_grade}}  (제거된 쿼리 제외)
  - qrels_report.json  : κ, 0↔2 비율, 합의필요 목록, 제거 쿼리 등

실행(라벨링 후):
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/06_merge_qrels.py
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAB_DIR = DATA_DIR / "labeling"
QRELS_PATH = DATA_DIR / "qrels.json"
REPORT_PATH = DATA_DIR / "qrels_report.json"


def _load(who) -> dict:
    """{(query_id, video_id): grade(int)}."""
    out = {}
    with (LAB_DIR / f"labeler_{who}.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            g = row.get("grade", "").strip()
            if g == "":
                raise ValueError(f"미입력 grade: {row['query_id']}/{row['video_id']} (labeler {who})")
            out[(row["query_id"], row["video_id"])] = int(g)
    return out


def _load_reconciliation() -> dict:
    p = LAB_DIR / "reconciliation.csv"
    if not p.exists():
        return {}
    out = {}
    with p.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[(row["query_id"], row["video_id"])] = float(row["grade"])
    return out


def _cohen_kappa(a, b):
    """unweighted, quadratic-weighted κ. sklearn 있으면 사용, 없으면 수동."""
    try:
        from sklearn.metrics import cohen_kappa_score
        return (round(float(cohen_kappa_score(a, b)), 3),
                round(float(cohen_kappa_score(a, b, weights="quadratic")), 3))
    except Exception:
        cats = [0, 1, 2]
        n = len(a)
        obs = sum(1 for x, y in zip(a, b) if x == y) / n
        from collections import Counter
        ca, cb = Counter(a), Counter(b)
        exp = sum((ca[c] / n) * (cb[c] / n) for c in cats)
        k = (obs - exp) / (1 - exp) if exp < 1 else 1.0
        return (round(k, 3), None)


def main():
    A, B = _load("A"), _load("B")
    recon = _load_reconciliation()
    keys = sorted(set(A) & set(B))
    if set(A) != set(B):
        print(f"⚠️ A·B 키 불일치 {len(set(A)^set(B))}개 — 교집합 {len(keys)}쌍만 사용")

    la = [A[k] for k in keys]
    lb = [B[k] for k in keys]
    kappa, kappa_w = _cohen_kappa(la, lb)

    final = {}          # query_id -> {video_id: grade}
    severe = []         # 0↔2 쌍
    need_recon = []
    for (qid, vid), a in ((k, A[k]) for k in keys):
        b = B[(qid, vid)]
        if a == b:
            g = float(a)
        elif abs(a - b) == 1:
            g = (a + b) / 2.0        # 0.5 / 1.5
        else:                         # 0↔2 심각 불일치
            severe.append((qid, vid))
            if (qid, vid) in recon:
                g = recon[(qid, vid)]
            else:
                need_recon.append({"query_id": qid, "video_id": vid, "A": a, "B": b})
                g = 1.0               # 합의 전 임시 fallback(+플래그)
        final.setdefault(qid, {})[vid] = g

    # 쿼리 제거: 최종 qrels에서 grade>=1 문서 0개
    removed = [qid for qid, docs in final.items() if not any(v >= 1 for v in docs.values())]
    for qid in removed:
        del final[qid]

    QRELS_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pairs = len(keys)
    report = {
        "n_pairs": n_pairs, "n_queries_final": len(final),
        "cohen_kappa": kappa, "cohen_kappa_quadratic": kappa_w,
        "severe_0v2_count": len(severe), "severe_0v2_rate": round(len(severe) / n_pairs, 4) if n_pairs else 0,
        "needs_reconciliation": need_recon,       # 이 목록을 2인이 합의 → reconciliation.csv로 재실행
        "removed_zero_relevance_queries": removed,
        "n_removed": len(removed),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"쌍 {n_pairs} | κ={kappa} (quad {kappa_w}) | 0↔2 {len(severe)}건({report['severe_0v2_rate']})")
    print(f"최종 쿼리 {len(final)}개 (grade0 제거 {len(removed)}개)")
    if need_recon:
        print(f"⚠️ 0↔2 합의 필요 {len(need_recon)}건 → 2인이 합의해 reconciliation.csv 작성 후 재실행")
    print(f"저장: {QRELS_PATH} , {REPORT_PATH}")


if __name__ == "__main__":
    main()
