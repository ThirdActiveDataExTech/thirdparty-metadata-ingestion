"""검색 평가셋을 만들고 설정을 비교한다 (P0-6).

C1 완료 기준("단일 방식 대비 상위 결과 품질 개선을 **수치로 제시**")과
ADR-010의 RRF k 스윕이 전부 이것 없이는 추측이다.

실행:
    PYTHONPATH=. python scripts/eval_search.py build --source video --n 30
    PYTHONPATH=. python scripts/eval_search.py run   --source video
    PYTHONPATH=. python scripts/eval_search.py pool  --source video   # 사람 판정용 후보
    #   → eval/search/video/pool_for_labeling.json 의 grade 를 0/1/2로 채운 뒤
    PYTHONPATH=. python scripts/eval_search.py merge --source video   # qrels로 합치기
    PYTHONPATH=. python scripts/eval_search.py drift --source video   # 평가셋이 썩었나

⚠️ `build`는 **known-item** 질의만 만든다(문서 원문에서 구절을 뽑아 그 문서를
   정답으로 둔다 — 검색 시스템을 쓰지 않으므로 순환이 아니다).
   **주제 관련성(topical) 라벨은 사람만 만들 수 있다.** `pool`로 후보를 뽑아
   판정한 뒤 eval/search/<source>/qrels.json에 넣는다.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from src.database.db import get_conn
from src.eval import build as B, dataset as D, metrics, runner
from src.search import hybrid

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

#: 원천 → (본문을 읽을 테이블, 문서 식별자 컬럼, 본문 컬럼들)
SOURCES = {
    "video": ("meta_video", "id", ["title", "description"]),
    "news":  ("meta_news", "id", ["title", "description", "content"]),
    "blog":  ("meta_blog", "id", ["title", "description", "content"]),
}


def _corpus(source: str, limit: int = 2000):
    table, idcol, cols = SOURCES[source]
    cur = get_conn().cursor()
    cur.execute(f"SELECT {idcol}, {', '.join(cols)} FROM {table} LIMIT %s", (limit,))
    docs = [(str(r[0]), ". ".join(x for x in r[1:] if x)) for r in cur.fetchall()]
    cur.execute(f"SELECT {idcol} FROM {table}")
    all_ids = {str(r[0]) for r in cur.fetchall()}
    cur.close()
    return docs, all_ids


def cmd_build(args) -> int:
    docs, all_ids = _corpus(args.source)
    queries, qrels = B.known_item_queries(docs, n=args.n)
    es = D.EvalSet.load(args.source)
    existing = {q["query_id"] for q in es.queries}
    es.queries = [q for q in es.queries if q.get("kind") != "known_item"] + queries
    es.qrels = {k: v for k, v in es.qrels.items() if not k.startswith("ki")}
    es.qrels.update(qrels)
    es.pin_corpus(all_ids)
    es.meta = {**es.meta, "known_item_built_at": datetime.now(timezone.utc).isoformat(),
               "known_item_note": "문서 원문에서 뽑은 구절. 정답은 그 문서 1건(등급 2)",
               "topical_note": "주제 관련성은 사람 판정이 필요하다 — pool 명령 참조"}
    path = es.save()
    print(f"\n{path}")
    print(f"  known-item 질의 {len(queries)}건 · 코퍼스 {len(all_ids)}건 고정")
    print(f"  (이전 질의 {len(existing)}건 중 topical은 보존)")
    return 0


def cmd_drift(args) -> int:
    es = D.EvalSet.load(args.source)
    if not es.queries:
        print("평가셋이 없다 — build를 먼저 실행하라.")
        return 1
    _, all_ids = _corpus(args.source)
    d = es.drift(all_ids)
    print(f"\n[{args.source}] 평가셋 상태  (고정 시각 {es.corpus_captured_at})")
    print(f"  코퍼스  고정 {d['corpus_pinned']} → 현재 {d['corpus_now']} "
          f"(겹침 {d['corpus_overlap']})")
    print(f"  판정 문서 {d['judged_docs']}건 중 생존 {d['judged_alive']}")
    print(f"  정답 문서 {d['gold_docs']}건 중 생존 {d['gold_alive']}")
    print(f"\n  {'✅ 쓸 수 있다' if d['usable'] else '❌ 썩었다 — 재구축이 필요하다'}")
    if not d["usable"]:
        print("  (정답 문서의 80% 미만이 남았다. 지표가 알고리즘이 아니라 "
              "문서 소실을 재게 된다)")
    return 0


def cmd_run(args) -> int:
    es = D.EvalSet.load(args.source)
    labeled = [q for q in es.queries if es.qrels.get(q["query_id"])]
    if not labeled:
        print("라벨된 질의가 없다 — build 또는 사람 판정이 필요하다.")
        return 1
    _, all_ids = _corpus(args.source)
    d = es.drift(all_ids)
    if not d["usable"]:
        print(f"⚠️ 평가셋이 썩었다 (정답 {d['gold_docs']}건 중 {d['gold_alive']}건 생존). "
              f"결과를 믿지 말 것.\n")

    kinds = sorted({q.get("kind", "?") for q in labeled})
    print(f"\n[{args.source}] 질의 {len(labeled)}건 ({', '.join(kinds)})\n")
    results = runner.compare(labeled, es.qrels, args.source,
                             configs=args.configs, top_k=args.top_k)

    cols = ["recall@1", "recall@5", "recall@10", "mrr", "ndcg@10"]
    print(f"\n{'설정':<14}" + "".join(f"{c:>11}" for c in cols))
    print("─" * (14 + 11 * len(cols)))
    base = results.get("vector", {})
    for name, r in results.items():
        line = f"{name:<14}" + "".join(f"{r.get(c, float('nan')):>11.4f}" for c in cols)
        if name != "vector" and base:
            delta = r.get("recall@10", 0) - base.get("recall@10", 0)
            line += f"   (기준선 대비 recall@10 {delta:+.4f})"
        print(line)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {args.out}")
    return 0


def cmd_pool(args) -> int:
    es = D.EvalSet.load(args.source)
    targets = [q for q in es.queries if q.get("kind") == "topical"] or es.queries
    if not targets:
        print("질의가 없다.")
        return 1
    runs = {name: runner.run_config(name, targets, args.source, args.depth)
            for name in (args.configs or ["vector", "hybrid"])}
    pooled = B.pool(runs, depth=args.depth)

    cur = get_conn().cursor()
    table, idcol, _ = SOURCES[args.source]
    out = []
    for q in targets:
        docs = pooled.get(q["query_id"], [])
        cur.execute(f"SELECT {idcol}, title FROM {table} WHERE {idcol}::text = ANY(%s)",
                    (docs,))
        titles = {str(a): b for a, b in cur.fetchall()}
        out.append({"query_id": q["query_id"], "query": q["query"],
                    "candidates": [{"doc_id": d, "title": titles.get(d, "?"),
                                    "grade": None} for d in docs]})
    path = D.EVAL_ROOT / args.source / "pool_for_labeling.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(o["candidates"]) for o in out)
    print(f"\n{path}")
    print(f"  질의 {len(out)}건 · 판정 후보 {total}건")
    print(f"  각 candidates[].grade 를 0(무관)/1(관련)/2(매우 관련)로 채운 뒤")
    print(f"  qrels.json에 합치면 평가에 쓰인다.")
    return 0


def cmd_merge(args) -> int:
    """사람이 채운 pool_for_labeling.json을 qrels.json에 합친다."""
    path = D.EVAL_ROOT / args.source / "pool_for_labeling.json"
    if not path.is_file():
        print(f"{path}가 없다 — pool을 먼저 실행하라.")
        return 1
    pool = json.loads(path.read_text(encoding="utf-8"))

    es = D.EvalSet.load(args.source)
    merged = graded = skipped = 0
    for q in pool:
        judged = {c["doc_id"]: int(c["grade"])
                  for c in q["candidates"] if c.get("grade") is not None}
        if not judged:
            skipped += 1
            continue
        # 판정 안 된 후보는 0으로 둔다 — 풀링 방식의 표준 가정이다.
        # 빠뜨린 것과 "무관"을 구분할 수 없으므로 과소평가 쪽으로 기운다.
        for c in q["candidates"]:
            judged.setdefault(c["doc_id"], 0)
        es.qrels[q["query_id"]] = judged
        merged += 1
        graded += len([g for g in judged.values() if g >= D.RELEVANT_GRADE])
    es.meta["labeled_at"] = datetime.now(timezone.utc).isoformat()
    es.save()
    print(f"\n질의 {merged}건 병합 (관련 판정 {graded}건) · 미판정 {skipped}건 건너뜀")
    if skipped:
        print("  (grade가 하나도 채워지지 않은 질의는 넘어갔다)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=sorted(SOURCES), default="video")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="known-item 질의 자동 생성")
    b.add_argument("--n", type=int, default=30)
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run", help="설정별 지표 비교")
    r.add_argument("--configs", nargs="*")
    r.add_argument("--top-k", type=int, default=20)
    r.add_argument("--out")
    r.set_defaults(func=cmd_run)

    p = sub.add_parser("pool", help="사람 판정용 후보 모으기")
    p.add_argument("--configs", nargs="*")
    p.add_argument("--depth", type=int, default=15)
    p.set_defaults(func=cmd_pool)

    m = sub.add_parser("merge", help="사람이 채운 판정을 qrels에 합친다")
    m.set_defaults(func=cmd_merge)

    d = sub.add_parser("drift", help="평가셋이 썩었는지 확인")
    d.set_defaults(func=cmd_drift)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
