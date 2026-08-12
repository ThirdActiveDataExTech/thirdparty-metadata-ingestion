"""P05 04h단계 — 평가 쿼리 FREEZE (PREREGISTRATION §0.2·0.6, 2026-08-12).

Query Pilot(§0.6) 결과로 **N=56 / pool Top-10** 확정 → 04f의 deterministic 표본(56)을
**queries_frozen.json**으로 동결한다. 이 파일이 05 retrieval의 유일한 쿼리 입력이며,
**retrieval 이후 절대 변경하지 않는다**(§0.2 Freeze 순서: 생성→Freeze→Retrieval→Evaluation).

query_id는 (카테고리 이름순, 카테고리 내 04f 표집순)으로 q00..q55 부여 — 결정적·안정.

입력: query_sample.json (04f, selected_flat 56)
출력: queries_frozen.json  [{query_id, query, category}] × 56

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04h_freeze_queries.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_PATH = DATA_DIR / "query_sample.json"
OUT_PATH = DATA_DIR / "queries_frozen.json"

N_FINAL = 56       # Query Pilot(§0.6)로 확정
POOL_TOPK = 10     # Query Pilot(§0.6)로 확정(§0.3 frozen depth 유지)


def main():
    s = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    flat = s["selected_flat"]
    assert len(flat) == N_FINAL, f"selected_flat {len(flat)} != N_FINAL {N_FINAL}"

    # (카테고리 이름순, 표집순) 결정적 정렬 → query_id 부여
    cats = sorted({it["category"] for it in flat})
    ordered = []
    for cat in cats:
        for it in flat:
            if it["category"] == cat:
                ordered.append(it)
    frozen = [{"query_id": f"q{i:02d}", "query": it["query"], "category": it["category"]}
              for i, it in enumerate(ordered)]

    out = {"_meta": {
        "rule": "PREREGISTRATION §0.2·0.6 FREEZE (2026-08-12)",
        "n": N_FINAL, "pool_topk": POOL_TOPK,
        "source": "query_sample.json (04f, deterministic 표집)",
        "note": "retrieval 이후 변경 금지(HARKing). query_id = (카테고리 이름순, 표집순) 결정적 부여.",
    }, "queries": frozen}
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ FREEZE: {len(frozen)}쿼리 (N={N_FINAL}, pool Top-{POOL_TOPK}) → {OUT_PATH}")
    from collections import Counter
    cc = Counter(f["category"] for f in frozen)
    print("카테고리별:", {k: cc[k] for k in cats})
    print("예시:", frozen[0], "…", frozen[-1])
    print("다음: 05 retrieval 실행 가능(queries_frozen.json 존재).")


if __name__ == "__main__":
    main()
