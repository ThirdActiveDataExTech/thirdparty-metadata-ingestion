"""P05 04l단계 — Query Generation 방법 비교 audit (DIAGNOSTIC ONLY).

기존 'trigger + 초성 sweep' 방식 vs '추천 검색어(trigger만)' 방식을, **같은 14 category /
같은 04b 분류기**로 비교한다. 목적: 추천 검색어 방식이 curation 후 **카테고리당 content
쿼리를 충분히(≥4) 확보하는지**(feasibility) + 후보 품질을 측정해 전환 여부를 판단.

⚠️ 이 audit은 아무 쿼리도 확정/제거하지 않는다. frozen 56도 안 건드린다. 방법 비교만.
독립성 원칙 유지: seed 영상에서 역으로 query를 고르지 않는다. 두 방법을 독립 비교.

- 추천 pool: 각 category trigger를 bare로 Suggest 호출(초성 sweep 없음) → 완성어.
- sweep pool: 기존 query_candidates.json(trigger+초성 sweep 결과).
- 두 pool 모두 **동일 04b classify()** 적용 → KEEP/REVIEW(=content 후보) 수 비교.

출력: 콘솔 + data/genmethod_audit.json (변경 없음)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04l_recommended_audit.py
"""

import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"


def _load(mod_file, name):
    spec = importlib.util.spec_from_file_location(name, CODE / mod_file)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


gen = _load("04_gen_queries.py", "gen04")      # fetch_suggest, _canon, _norm
cur = _load("04b_curate_queries.py", "cur04b")  # classify


def collect_recommended(triggers):
    """trigger bare Suggest만(초성 sweep 없음) → canon dedup."""
    seen, out = set(), []
    for t in triggers:
        for sug in gen.fetch_suggest(t):
            if len(sug.replace(" ", "")) < gen.MIN_LEN:
                continue
            c = gen._canon(sug)
            if c not in seen:
                seen.add(c); out.append(sug)
        time.sleep(0.15)
    return out


def classify_pool(cands, cat_name, triggers):
    dec = Counter()
    keep_review = []
    for q in cands:
        d, r = cur.classify(q, cat_name, triggers)
        dec[d] += 1
        if d in ("KEEP", "REVIEW"):
            keep_review.append(q)
    return dec, keep_review


def main():
    trig = json.loads((DATA / "query_triggers.json").read_text(encoding="utf-8"))["categories"]
    sweep = json.loads((DATA / "query_candidates.json").read_text(encoding="utf-8"))["categories"]
    sweep_by_name = {c["name"]: c["candidates"] for c in sweep.values()}

    rows = []
    report = {"_meta": {"note": "DIAGNOSTIC. 추천(trigger bare) vs sweep, 동일 04b 분류. 변경 없음."},
              "categories": {}}
    print("추천 검색어 수집 중(초성 sweep 없이 trigger만) …\n")
    for cid, e in trig.items():
        name, triggers = e["name"], e["triggers"]
        rec = collect_recommended(triggers)
        rec_dec, rec_kr = classify_pool(rec, name, triggers)
        sw = sweep_by_name.get(name, [])
        sw_dec, sw_kr = classify_pool(sw, name, triggers)
        rows.append({"category": name, "triggers": triggers,
                     "rec_raw": len(rec), "rec_content": len(rec_kr),
                     "sweep_raw": len(sw), "sweep_content": len(sw_kr),
                     "rec_feasible(>=4)": len(rec_kr) >= 4})
        report["categories"][name] = {"triggers": triggers,
                                      "recommended_raw": rec, "recommended_content": rec_kr,
                                      "recommended_decisions": dict(rec_dec),
                                      "sweep_content_n": len(sw_kr), "sweep_decisions": dict(sw_dec)}

    print(f"=== 방법 비교 (동일 04b 분류; content = KEEP+REVIEW) ===")
    print(f"  {'category':<12} {'trig':<12} {'rec_raw':>7} {'rec_content':>11} {'sweep_content':>13} {'rec≥4?':>7}")
    n_feasible = 0
    for r in rows:
        n_feasible += r["rec_feasible(>=4)"]
        print(f"  {r['category']:<12} {'/'.join(r['triggers'])[:11]:<12} {r['rec_raw']:>7} "
              f"{r['rec_content']:>11} {r['sweep_content']:>13} {'OK' if r['rec_feasible(>=4)'] else 'FAIL':>7}")
    print(f"\n추천 검색어만으로 content ≥4 확보 category: {n_feasible}/14")
    tot_rec = sum(r["rec_content"] for r in rows)
    tot_sw = sum(r["sweep_content"] for r in rows)
    print(f"content 후보 총합: 추천={tot_rec} vs sweep={tot_sw}")
    print("\n판정 가이드:")
    print("  · 추천만으로 대부분 category가 ≥4 통과 + 후보 자연스러움 → 전환 검토")
    print("  · 다수 category가 <4 → 추천만으로는 14×4 불가 → sweep 유지(+근거 문서화)")

    # 추천 pool 실제 후보 몇 개 미리보기(자연스러움 eyeball)
    print("\n=== 추천 content 후보 미리보기(자동차/음악/동물/과학) ===")
    for name in ["자동차", "음악", "동물", "과학기술"]:
        rc = report["categories"][name]["recommended_content"]
        print(f"  [{name}] ({len(rc)}) {', '.join(rc)}")

    (DATA / "genmethod_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA/'genmethod_audit.json'} (진단 전용)")


if __name__ == "__main__":
    main()
