"""P05 04(revised) — 초성(jamo) sweep candidate 생성 (PREREGISTRATION §0.2, 2026-08-14 amendment).

기존 음절 sweep(가/나/다…=ㅏ모음만)은 초성 후보공간을 충분히 탐색 못 하는 coverage
limitation이 확인됨(예: '뉴스 가'→강아지/강릉만, '뉴스 경제/기자/교통사고'는 누락). 초성
sweep(ㄱ/ㄴ/ㄷ…)은 동일 trigger에서 **해당 초성으로 시작하는 넓은 후보군**을 탐색한다.

04_gen_queries.py의 수집·정규화·카테고리귀속 로직을 **그대로** 쓰되 sweep만 음절→초성으로
교체. 음절 baseline(query_candidates.json)은 보존. 동일 curation(04b classify) 적용.

출력: query_candidates_jamo.json, query_curation_jamo.json
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04_gen_jamo.py
"""

import importlib.util
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"
JAMO = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
MAX_PER_CATEGORY = 50


def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


gen = _load("04_gen_queries.py", "gen04")
cur = _load("04b_curate_queries.py", "cur04b")


def main():
    trig = json.loads((DATA / "query_triggers.json").read_text(encoding="utf-8"))["categories"]

    # 1) 초성 sweep 수집 (04와 동일 구조, sweep만 JAMO)
    raw = []
    for cid, e in trig.items():
        for t0 in e["triggers"]:
            for t in [t0] + [f"{t0} {j}" for j in JAMO]:
                for sug in gen.fetch_suggest(t):
                    if len(sug.replace(" ", "")) >= gen.MIN_LEN:
                        raw.append({"query": sug, "category": cid, "trigger": t0})
                time.sleep(0.12)
        print(f"  수집 {e['name']:<10} 누적 raw {len(raw)}")

    # 2) canon 그룹 → 단일 카테고리 귀속(교차 drop) → cap
    groups = defaultdict(list)
    for r in raw:
        groups[gen._canon(r["query"])].append(r)
    assigned = defaultdict(list)
    for canon, es in groups.items():
        cats = sorted(set(x["category"] for x in es))
        rep = min((x["query"] for x in es), key=len)
        if len(cats) == 1:
            assigned[cats[0]].append({"query": rep, "source_trigger": next(x["trigger"] for x in es)})
    cand = {"_meta": {"method": "jamo(초성) sweep", "jamo": JAMO, "cap": MAX_PER_CATEGORY,
                      "baseline": "query_candidates.json (음절 sweep 보존)"}, "categories": {}}
    for cid, e in trig.items():
        items = assigned.get(cid, [])[:MAX_PER_CATEGORY]
        cand["categories"][cid] = {"name": e["name"], "candidates": [x["query"] for x in items],
                                   "provenance": {x["query"]: x["source_trigger"] for x in items}}
    (DATA / "query_candidates_jamo.json").write_text(json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) 동일 04b classify
    out = {"_meta": {"base": "query_candidates_jamo.json", "rule": "동일 04b classify(초성에 맞춰 규칙 변경 금지)"},
           "categories": {}}
    print("\n=== 초성 pool 04b 분류 (KEEP+REVIEW=content 후보) ===")
    print(f"  {'category':<12} {'raw':>4} {'KEEP':>5} {'REV':>4} {'EXCL':>5} {'FLAG':>4} {'content(K+R)':>12}")
    tot = Counter()
    preview = {}
    for cid, c in cand["categories"].items():
        name = c["name"]; triggers = trig[cid]["triggers"]
        items, dec = [], Counter()
        content = []
        for q in c["candidates"]:
            d, r = cur.classify(q, name, triggers)
            items.append({"query": q, "category": name, "decision": d, "reason_code": r,
                          "source_trigger": c["provenance"].get(q, "")})
            dec[d] += 1
            if d in ("KEEP", "REVIEW"):
                content.append(q)
        out["categories"][cid] = {"name": name, "items": items}
        preview[name] = content
        tot[name] = len(content)
        print(f"  {name:<12} {len(c['candidates']):>4} {dec['KEEP']:>5} {dec['REVIEW']:>4} "
              f"{dec['EXCLUDE']:>5} {dec['FLAG']:>4} {len(content):>12}")
    (DATA / "query_curation_jamo.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n content 후보 총합: {sum(tot.values())} (음절 baseline은 참고 04l 기록)")
    print("\n=== content 후보 미리보기(자동차/뉴스/과학/노하우) ===")
    for name in ["자동차", "뉴스/정치", "과학기술", "노하우/스타일"]:
        print(f"  [{name}] ({len(preview[name])}) {', '.join(preview[name][:16])}")
    print(f"\n저장: query_candidates_jamo.json, query_curation_jamo.json")


if __name__ == "__main__":
    main()
