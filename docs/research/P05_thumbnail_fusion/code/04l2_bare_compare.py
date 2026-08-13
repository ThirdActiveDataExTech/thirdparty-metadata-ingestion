"""P05 04l2 — bare 추천검색어(sweep 없음) vs 초성-MD5 최종 비교 (DIAGNOSTIC).

generation 방법 최종 결정을 위해, category trigger의 **bare 추천검색어만**(초성/음절 sweep 없이)
수집 → 동일 curation → 동일 MD5+content-filter 표집 → 초성-MD5(현 frozen)와 side-by-side.
지표: 카테고리별 eligible(≥4?), META/NAV(/56), diversity, coverage.

출력: 콘솔 + data/bare_compare.json
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04l2_bare_compare.py
"""

import importlib.util
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CODE = Path(__file__).resolve().parent
DATA = CODE.parent / "data"


def _load(f, n):
    s = importlib.util.spec_from_file_location(n, CODE / f); m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m); return m


gen = _load("04_gen_queries.py", "g"); cur = _load("04b_curate_queries.py", "c")
cj = _load("04_curate_jamo.py", "cj"); mf = _load("04f_final_md5.py", "mf")


def main():
    trig = json.loads((DATA / "query_triggers.json").read_text(encoding="utf-8"))["categories"]
    adj = json.loads((DATA / "query_curation_adjudicated.json").read_text(encoding="utf-8"))
    prior_excl = {it["query"] for cid, c in adj["categories"].items() for it in c["items"]
                  if it["adjudicated_decision"] == "EXCLUDE"}
    frozen = json.loads((DATA / "queries_frozen.json").read_text(encoding="utf-8"))["queries"]
    jamo_sel = defaultdict(list)
    for q in frozen:
        jamo_sel[q["category"]].append(q["query"])

    # bare 추천검색어 수집 → canon dedup → 카테고리 귀속
    raw = []
    for cid, e in trig.items():
        for t in e["triggers"]:
            for sug in gen.fetch_suggest(t):
                if len(sug.replace(" ", "")) >= gen.MIN_LEN:
                    raw.append({"query": sug, "category": cid, "trigger": t})
            time.sleep(0.12)
    groups = defaultdict(list)
    for r in raw:
        groups[gen._canon(r["query"])].append(r)
    assigned = defaultdict(list)
    for canon, es in groups.items():
        cats = sorted(set(x["category"] for x in es))
        if len(cats) == 1:
            assigned[cats[0]].append(min((x["query"] for x in es), key=len))

    # 동일 curation: 04b + jamo 렉시콘 + prior EXCLUDE
    def keep(q, cat_name, triggers):
        d, r = cur.classify(q, cat_name, triggers)
        if d in ("EXCLUDE", "FLAG"):
            return False
        if q in prior_excl:
            return False
        if any(s in q for s in cj.NAV) or q in cj.PERSON or any(s in q for s in cj.PRODUCT) or q in cj.CROSS:
            return False
        return True

    per_cat = {}
    for cid, e in trig.items():
        name = e["name"]
        elig = [q for q in assigned.get(cid, []) if keep(q, name, e["triggers"])]
        per_cat[name] = elig

    # 임베딩 + MD5+filter 표집
    all_q = sorted({q for qs in per_cat.values() for q in qs})
    emb = SentenceTransformer(mf_model()).encode(all_q, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64) \
        if False else None
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    emb = model.encode(all_q, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64)
    idx = {q: i for i, q in enumerate(all_q)}

    def md5_filter(qs, E, pos):
        Ec = E - E.mean(0, keepdims=True); nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Ec = Ec / nrm; sim = Ec @ Ec.T
        sel = []
        for q in sorted(qs, key=mf.okey):
            if mf.bad(q):
                continue
            if any(sim[pos[q]][pos[s]] >= mf.NEAR for s in sel):
                continue
            sel.append(q)
            if len(sel) == 4:
                break
        while len(sel) < 4:
            for q in sorted(qs, key=mf.okey):
                if q not in sel and not mf.bad(q):
                    sel.append(q); break
            else:
                break
        return sel

    bare_sel = {}
    metanav = 0
    print("=== bare 추천검색어 pipeline ===")
    print(f"  {'category':<12} {'eligible':>8} {'≥4?':>4}")
    for name in sorted(per_cat):
        qs = per_cat[name]
        pos = {q: i for i, q in enumerate(qs)}
        E = emb[[idx[q] for q in qs]]
        sel = md5_filter(qs, E, pos) if len(qs) >= 1 else []
        bare_sel[name] = sel
        metanav += sum(1 for q in sel if mf.bad(q))
        print(f"  {name:<12} {len(qs):>8} {'OK' if len(qs) >= 4 else 'FAIL':>4}")

    print(f"\n  bare 표집 META/NAV(/56): {metanav}")
    print("\n=== side-by-side: 초성-MD5(현 frozen) vs bare-MD5 ===")
    for name in sorted(per_cat):
        print(f"\n[{name}]")
        print(f"   초성  {' · '.join(jamo_sel[name])}")
        print(f"   bare  {' · '.join(bare_sel[name])}")

    (DATA / "bare_compare.json").write_text(json.dumps(
        {"bare_selected": bare_sel, "jamo_selected": dict(jamo_sel),
         "bare_eligible": {k: len(v) for k, v in per_cat.items()}}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA/'bare_compare.json'}")


def mf_model():
    return "paraphrase-multilingual-mpnet-base-v2"


if __name__ == "__main__":
    main()
