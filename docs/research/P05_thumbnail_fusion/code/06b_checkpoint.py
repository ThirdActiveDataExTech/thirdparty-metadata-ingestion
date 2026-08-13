"""P05 06b단계 — 라벨링 체크포인트 (PREREGISTRATION §0.3, 3인 median-of-3).

A·B가 (거의) 끝난 시점에 실행한다. median-of-3에서 **A=B 쌍은 C가 값에 영향이 없으므로**,
C가 시간이 부족하면 **불일치(A≠B) 쌍만** 마저 판정하면 최종 라벨이 완전 3인과 동일하다.
이 스크립트는 그 "C가 아직 안 한 불일치 쌍"만 추려 labeler_C_remaining.csv로 만든다.

또한 진행상황(합의율·불일치 수·C 진척)을 보고해 **완전 3인 vs 심판 모드** 판단을 돕는다
(이 판단은 라벨 값이 아니라 완료율 기준 — HARKing 아님).

입력(data/labeling/): labeler_A.csv, labeler_B.csv, labeler_C.csv(부분 가능)
출력(data/labeling/): labeler_C_remaining.csv (C가 마저 할 불일치 쌍, blind 순서 유지)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/06b_checkpoint.py
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAB_DIR = DATA_DIR / "labeling"
COLS = ["query_id", "query", "category", "video_id", "title", "thumbnail_url", "url", "grade"]


def load_grades(who):
    """{(qid,vid): int} — grade 채워진 것만. 파일 없으면 빈 dict."""
    p = LAB_DIR / f"labeler_{who}.csv"
    out = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            g = (r.get("grade") or "").strip()
            if g != "":
                out[(r["query_id"], r["video_id"])] = int(g)
    return out


def main():
    A, B, C = load_grades("A"), load_grades("B"), load_grades("C")
    rows_C = list(csv.DictReader((LAB_DIR / "labeler_C.csv").open(encoding="utf-8-sig")))
    total = len(rows_C)

    both = set(A) & set(B)
    if len(both) < total:
        print(f"⚠️ A·B 아직 미완: A={len(A)} B={len(B)} (전체 {total}) — 완료분 {len(both)}쌍 기준으로 산출")

    disagree = {k for k in both if A[k] != B[k]}
    agree = both - disagree
    c_done_disagree = disagree & set(C)
    c_remaining = disagree - set(C)

    # C가 마저 할 불일치 쌍만 blind 순서로 추출(A/B 값은 노출 안 함)
    rem_rows = [r for r in rows_C if (r["query_id"], r["video_id"]) in c_remaining
                and (r.get("grade") or "").strip() == ""]
    out_path = LAB_DIR / "labeler_C_remaining.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rem_rows:
            w.writerow({k: r.get(k, "") for k in COLS})

    ab_agree_rate = len(agree) / len(both) if both else 0
    print("=== 라벨링 체크포인트 (A·B 기준) ===")
    print(f"  A·B 완료 쌍: {len(both)} / 전체 {total}")
    print(f"  일치(A=B): {len(agree)} ({ab_agree_rate:.1%})  |  불일치(A≠B): {len(disagree)}")
    print(f"  C 진척: 전체 {len(C)}쌍 라벨 | 불일치 중 C 완료 {len(c_done_disagree)} / 잔여 {len(c_remaining)}")
    print(f"\n→ labeler_C_remaining.csv 생성: C가 마저 할 불일치 쌍 {len(rem_rows)}건")
    print("   · C가 페이스 OK면 labeler_C.csv 전량 완주(완전 3인 → Fleiss κ 보고 가능)")
    print(f"   · C 시간 부족하면 이 {len(rem_rows)}건만 채우면 최종 라벨 동일(심판 모드)")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
