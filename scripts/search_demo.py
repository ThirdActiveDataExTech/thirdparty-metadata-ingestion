"""자연어 질의로 수집·임베딩된 비정형 데이터를 검색한다.

실행 방법:
    PYTHONPATH=. python scripts/search_demo.py "위암 조기 진단"
    PYTHONPATH=. python scripts/search_demo.py "HBM 고대역폭 메모리" --source video
    PYTHONPATH=. python scripts/search_demo.py "전기차 보조금" --mode vector  # 예전 단일 채널
    PYTHONPATH=. python scripts/search_demo.py "국내 기업 투자 확대 계획" --why

기본은 **하이브리드**다(ADR-010). 벡터 채널과 키워드 채널을 각각 랭크한 뒤
RRF로 합친다. 왜 두 채널이 필요한지는 src/search/hybrid.py 머리말 참조 —
요약하면 벡터 점수만으로는 "답이 있는가"를 판정할 수 없다는 것이 질의 19건
실측으로 확인됐다(ADR-018).

`--mode vector`는 비교용으로 남겨 둔 예전 경로다. 두 가지가 핵심이었다.

1. **질의 프리픽스** — 모델(multilingual-e5-base)은 문서에 `passage: `,
   질의에 `query: `를 붙여 학습됐다. 빠뜨려도 오류가 나지 않고 검색 품질만
   조용히 떨어진다(docs/adr/016_Embedding_Model_And_Conventions.md).

2. **청크 최대 유사도 집계** — 문서 1건은 여러 청크로 나뉘어 저장된다.
   점수는 평균이 아니라 **최대값**을 쓴다. 긴 문서에서 질의와 맞는 청크가
   하나이고 무관한 청크가 여럿일 때, 평균은 정답 신호를 희석시킨다.

둘 다 하이브리드에서도 그대로 유지된다.
"""

import argparse
import sys

from src.database.db import get_conn
from src.embedding import embedder
from src.search import hybrid, tokenize

SOURCES = hybrid.SOURCES


def search_vector_only(query: str, source: str, top_k: int):
    """예전 단일 채널 경로 — 하이브리드와 비교할 때 쓴다."""
    vec, base, vkey, bkey, title_col, sub_col = SOURCES[source]
    q = str(embedder.encode_query(query))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT b.{bkey}, b.{title_col}, b.{sub_col},
               ROUND(MAX(1 - (v.embedding <=> %s::vector))::numeric, 4) AS score
        FROM   {vec} v
        JOIN   {base} b ON b.{bkey} = v.{vkey}
        GROUP  BY b.{bkey}, b.{title_col}, b.{sub_col}   -- 청크를 원본 1건으로 묶는다
        ORDER  BY score DESC
        LIMIT  %s
        """,
        (q, top_k),
    )
    rows = [{"id": r[0], "title": r[1], "subtitle": r[2], "vec_score": r[3]}
            for r in cur.fetchall()]
    cur.close()
    return rows


def _fmt_channel(row) -> str:
    """어느 채널이 이 문서를 올렸는지 한눈에 보이게 한다."""
    v = f"V{row['vec_rank']}" if row.get("vec_rank") else "V-"
    k = f"K{row['kw_rank']}" if row.get("kw_rank") else "K-"
    return f"{v:>5} {k:>5}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", help="검색할 자연어 질의")
    ap.add_argument("--source", choices=sorted(SOURCES), default="news")
    ap.add_argument("--top", type=int, default=10, help="결과 개수 (기본 10)")
    ap.add_argument("--mode", choices=["hybrid", "vector"], default="hybrid")
    ap.add_argument("--rrf-k", type=int, default=hybrid.DEFAULT_RRF_K,
                    help=f"RRF 상수 (기본 {hybrid.DEFAULT_RRF_K}). "
                         "ADR-010이 10/20/30/60 스윕을 평가 항목으로 정해 뒀다")
    ap.add_argument("--why", action="store_true",
                    help="질의 토큰·문서빈도·최희귀어 판정을 같이 보여준다")
    args = ap.parse_args()

    print(f'\n[{args.source}/{args.mode}] "{args.query}"')

    if args.mode == "vector":
        rows = search_vector_only(args.query, args.source, args.top)
        print()
        for i, r in enumerate(rows, 1):
            print(f"  {i:>2}. {r['vec_score']}  {r['title']}")
            print(f"           {r['subtitle']}")
        print()
        return 0

    if args.why:
        print(f"      토큰: {tokenize.token_text(args.query) or '(없음)'}")
        df = hybrid.rarest_token_df(args.query, args.source)
        if df:
            print(f"      최희귀어: {df['token']!r}  문서빈도 {df['df']}건 ({df['df_pct']}%)")
            if df["absent"]:
                # ADR-018의 유일한 판정 규칙. 임계값이 아니라 존재 여부다.
                print("      ⚠️ 최희귀어가 코퍼스에 없다 — 답이 없을 가능성이 높다")

    rows = hybrid.search(args.query, args.source, args.top, rrf_k=args.rrf_k)
    if not rows:
        print("\n  결과 없음 — 수집·임베딩과 scripts/backfill_tokens.py 실행 여부를 확인하세요.\n")
        return 0

    print(f"\n  {'#':>2}  {'순위(V=벡터 K=키워드)':<14} {'RRF':<9} 제목")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2}. {_fmt_channel(r):<14} {r['rrf']}  {r['title']}")
        print(f"      {'':<14} {'':<9}  {r['subtitle']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
