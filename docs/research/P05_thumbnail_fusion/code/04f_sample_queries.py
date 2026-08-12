"""P05 04f단계 — clean eligible pool에서 평가 쿼리 deterministic 표집 (PREREGISTRATION §0.2).

04e에서 확정한 **eligible pool(adjudicated KEEP 373)** 에서 카테고리별 **동일 N**을
**seed-독립 · deterministic**으로 뽑는다(§0.2 sampling 규칙, 2026-08-08 freeze).

핵심(HARKing 방지):
  - **seed-독립**: 코퍼스 SEED 구(phrase)와 무관하게 순서를 정한다 → 쿼리 선택이 코퍼스
    구축 seed에 coupling되지 않음.
  - **deterministic**: 순서 = md5(SALT + query)의 사전식 정렬(고정 SALT). 누가·언제 돌려도
    동일. 삽입 순서·난수 상태에 의존하지 않음.
  - **nested**: N을 4→6으로 늘려도 앞 4개는 불변(순서 고정) → Pilot이 N을 키워도 재선별 아님.
  - **성능/relevance를 보고 고르지 않는다** — retrieval 전에 순서가 이미 고정됨.

산출:
  - query_sample.json: 카테고리별 ordered pool + N_PRIMARY 선정 + Query Pilot 10쿼리(§0.6)
  - N_PRIMARY=4 → 14×4=56 (§0.2·0.6의 1차 목표; 최종 N은 Query Pilot의 pool 크기로 확정)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04f_sample_queries.py
"""

import hashlib
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IN_PATH = DATA_DIR / "query_curation_adjudicated.json"
OUT_PATH = DATA_DIR / "query_sample.json"

# 재현용 고정 상수(변경 금지 — 변경 시 표본이 바뀜). 코퍼스 seed와 무관한 순서 salt.
SALT = "P05-query-sample-v1"
N_PRIMARY = 4          # 카테고리당 1차 표집 수 → 14×4 = 56 (§0.6 1차 목표)
N_PILOT = 10           # Query Pilot 쿼리 수(§0.6, 카테고리 분산)


def order_key(q: str) -> str:
    """deterministic 순서 키 = md5(SALT+query). 코퍼스 seed·삽입순서와 독립."""
    return hashlib.md5((SALT + q).encode("utf-8")).hexdigest()


def main():
    d = json.loads(IN_PATH.read_text(encoding="utf-8"))

    # 카테고리별 eligible(KEEP) 쿼리 수집 → deterministic 정렬
    per_cat = {}   # name -> [ordered queries]
    for cid, c in d["categories"].items():
        keeps = [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
        per_cat[c["name"]] = sorted(keeps, key=order_key)

    cats_sorted = sorted(per_cat)   # 카테고리도 이름순 고정
    min_n = min(len(v) for v in per_cat.values())
    if N_PRIMARY > min_n:
        raise SystemExit(f"N_PRIMARY={N_PRIMARY} > 최소 eligible {min_n}. 표집 불가.")

    out = {"_meta": {
        "rule": "PREREGISTRATION §0.2 sampling (seed-독립 deterministic, freeze 2026-08-08)",
        "salt": SALT, "n_primary_per_category": N_PRIMARY, "n_pilot": N_PILOT,
        "note": "eligible=adjudicated KEEP 373. 순서=md5(SALT+query) 사전식. nested(앞 N 불변). "
                "성능 보고 재선별 금지. 최종 N은 Query Pilot pool 크기로 확정(56부터).",
        "source": "query_curation_adjudicated.json (04e)",
    }, "categories": {}}

    selected_flat = []
    for name in cats_sorted:
        ordered = per_cat[name]
        selected = ordered[:N_PRIMARY]
        out["categories"][name] = {"eligible_n": len(ordered),
                                   "ordered": ordered, "selected": selected}
        for q in selected:
            selected_flat.append({"query": q, "category": name})

    # Query Pilot 10쿼리(§0.6): 카테고리 분산 = 이름순 각 카테고리 1위(rank-0)에서 앞 10개
    pilot = [{"query": per_cat[name][0], "category": name} for name in cats_sorted][:N_PILOT]

    out["selected_flat"] = selected_flat
    out["pilot_queries"] = pilot
    out["total_selected"] = len(selected_flat)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"eligible pool = {sum(len(v) for v in per_cat.values())} (14 카테고리)")
    print(f"최소 eligible category = {min(cats_sorted, key=lambda n: len(per_cat[n]))} "
          f"({min_n}) → N_PRIMARY={N_PRIMARY} 안전")
    print(f"\n=== 1차 표집 {len(selected_flat)}쿼리 (14×{N_PRIMARY}) ===")
    for name in cats_sorted:
        print(f"  [{name}] " + " · ".join(out['categories'][name]['selected']))
    print(f"\n=== Query Pilot {len(pilot)}쿼리(§0.6, 카테고리 분산) ===")
    for p in pilot:
        print(f"  [{p['category']}] {p['query']}")
    print(f"\n저장: {OUT_PATH}")
    print("다음: Query Pilot pooling으로 평균 pool size 실측 → 최종 N 확정 → freeze")


if __name__ == "__main__":
    main()
