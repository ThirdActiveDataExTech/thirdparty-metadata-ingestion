"""하이브리드 검색 — 벡터 채널 + 키워드 채널을 RRF로 결합한다 (ADR-010).

**왜 두 채널인가.** 2026-10-30 실측(ADR-018)에서 벡터 점수만으로는 "이 질의에
답이 있는가"를 판정할 수 없다는 것이 확인됐다. 질의 19건에서 코사인 top1,
top1−top50 간격, 키워드 커버리지, 최희귀어 문서빈도 등 **여섯 지표가 전부**
정답 유무를 가르지 못했다 — 정답 있음 최저 0.8638, 정답 없음 최고 0.8856으로
구간이 겹친다. 고정 임계값(`WHERE 1 - (embedding <=> q) > 0.8x`)은 어떤 값을
골라도 틀린다.

두 채널이 깨지는 방식이 서로 다르다는 점이 결합의 근거다.

    `quantum computing qubit`  — 상위 5건이 전부 정답인데 본문이 한국어라
                                 키워드 커버리지는 0.23. 벡터가 맞힌다.
    `국내 기업 투자 확대 계획`   — 어절이 전부 고빈도(국내 444·기업 782·확대 897)라
                                 모든 지표가 "확신"인데 답이 없다. 키워드가 거른다.

**왜 점수 가중합이 아니라 RRF인가.** 두 채널의 점수는 단위가 다르다(코사인
0.7~1.0 대 ts_rank_cd 0~수십). 정규화하려면 채널별 분포 통계가 필요한데 현
규모에서는 그 통계를 신뢰할 수 없다. RRF는 **순위만** 쓰므로 분포를 몰라도 된다.

    rrf(d) = Σ_channel  1 / (k + rank_channel(d))

k는 통상 60이다. 후보군이 작으면 과도하게 평탄화되므로 ADR-010은
k ∈ {10,20,30,60} 스윕을 평가 항목에 포함하도록 정해 뒀다 — `rrf_k`로 바꾼다.

**집계 단위.** 두 채널 모두 청크 단위로 점수를 낸 뒤 원본 1건으로 묶는다.
묶는 방법은 평균이 아니라 **최대값**이다. 긴 문서에서 질의에 맞는 청크가 하나고
무관한 청크가 여럿일 때 평균은 정답 신호를 희석시킨다(src/embedding/chunker.py).
"""

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.database.db import get_conn
from src.embedding import embedder
from src.search import tokenize

logger = logging.getLogger(__name__)

# (벡터 테이블, 원본 테이블, 벡터쪽 키, 원본쪽 키, 제목 컬럼, 부제 컬럼)
SOURCES = {
    "video":   ("meta_video_vec",   "meta_video",   "meta_id",    "id",         "title", "channel_title"),
    "news":    ("meta_news_vec",    "meta_news",    "meta_id",    "id",         "title", "publisher"),
    "blog":    ("meta_blog_vec",    "meta_blog",    "meta_id",    "id",         "title", "blogger_name"),
    "dataset": ("dcat_dataset_vec", "dcat_dataset", "dataset_id", "dataset_id", "title", "source_type"),
}

#: RRF 상수. 클수록 상위 순위 간 점수 차가 완만해진다.
DEFAULT_RRF_K = 60

#: 각 채널에서 가져올 후보 수. 결합 전에 자르는 깊이 — 너무 얕으면 한쪽 채널에만
#: 잡히는 정답이 결합 단계에 도달하지 못한다.
DEFAULT_CANDIDATES = 200

#: 키워드 채널의 점수 방식.
#:
#:   "cover_density"  PostgreSQL `ts_rank_cd`. 질의어가 얼마나 몰려 있는지를 본다.
#:                    **IDF를 쓰지 않는다** — 이것이 문제의 뿌리다.
#:   "idf_sum"        맞은 질의 토큰의 IDF 합. 드문 말을 맞힌 쪽에 점수를 준다.
#:
#: 왜 바꾸는가 — 2026-11-04 실측(P0-6 known-item 30건):
#:
#:     벡터 단독   recall@1 1.0000
#:     하이브리드  recall@1 0.7333   (RRF k를 60→30→20→10으로 낮춰도 **전부 동일**)
#:
#: k는 깊이만 바꾸고 1위를 뺏기는 것은 못 막는다. 원인은 상수가 아니라 점수 방식이다.
#: `"메모리 대역폭을 늘리는 적층 기술"`에서 고빈도어(`기술`·`메모리`)가 빽빽한 일반
#: 기사가, 희귀어 `적층`(df 23)을 담은 정답을 밀어냈다.
#:
#: `idf_sum`은 BM25에서 term frequency 포화를 뺀 형태다(k1→0). 표준적이고,
#: **known-item 점수에 맞춰 고른 값이 아니다** — 진단에서 바로 나온 처방이다.
DEFAULT_SCORE_MODE = "idf_sum"


def token_idf(cur, table: str, terms: Sequence[str]) -> Dict[str, float]:
    """질의 토큰별 IDF. `ln(N / df)` — 드물수록 크다.

    **한 번의 왕복으로 전부 센다.** 토큰마다 따로 물으면 질의당 왕복이 토큰 수만큼
    늘어나는데, 그 비용이 검색 지연에 그대로 더해진다.

    df는 **청크 단위**로 센다. 랭킹도 청크 단위(최대값 집계)라 기준이 같다.
    문서 단위 df가 더 표준적이지만, 여기서 필요한 것은 토큰 간 **상대적 희소성**이라
    단조 변환 차이에 그친다.

    df가 0인 토큰(코퍼스에 없는 말)은 IDF가 무한대가 되므로 N을 쓴다 —
    "가장 드문 것보다도 드물다"로 두면 된다. 어차피 매칭되지 않아 점수에 안 들어간다.
    """
    terms = list(dict.fromkeys(t for t in terms if t))
    if not terms:
        return {}
    cur.execute(f"SELECT count(*) FROM {table} WHERE tsv <> ''")
    total = cur.fetchone()[0] or 1
    cur.execute(
        f"SELECT t.term, "
        f"       (SELECT count(*) FROM {table} v WHERE v.tsv @@ to_tsquery('simple', t.term)) "
        f"FROM unnest(%s::text[]) AS t(term)",
        (terms,),
    )
    out = {}
    for term, df in cur.fetchall():
        out[term] = math.log(total / df) if df else math.log(total)
    return out


def _score_expr(mode: str) -> Tuple[str, str]:
    """키워드 채널의 점수식과 그 설명을 돌려준다."""
    if mode == "cover_density":
        return ("ts_rank_cd(v.tsv, q.query)",
                "PostgreSQL ts_rank_cd — 질의어 밀집도. IDF를 쓰지 않는다")
    if mode == "idf_sum":
        # 맞은 질의 토큰의 IDF 합. 드문 말을 맞힌 쪽이 이긴다.
        # unnest로 (토큰, idf) 쌍을 펴서 매칭되는 것만 더한다.
        return (
            "(SELECT coalesce(sum(w.idf), 0) "
            " FROM unnest(%(terms)s::text[], %(idfs)s::float8[]) AS w(term, idf) "
            " WHERE v.tsv @@ to_tsquery('simple', w.term))",
            "맞은 질의 토큰의 IDF 합 — 드문 말을 맞힌 쪽에 점수를 준다",
        )
    raise ValueError(f"알 수 없는 score_mode: {mode!r}")


def _assert_tokenizer(cur, table: str) -> None:
    """저장된 토큰이 지금 토크나이저로 만든 것인지 확인한다.

    불일치는 오류를 내지 않고 **리콜만 조용히 0으로 만든다.** ADR-010이
    "불일치 시 기동 실패시킨다"고 정해 둔 이유다.
    """
    cur.execute(
        f"SELECT DISTINCT tokenizer_ver FROM {table} WHERE tokenizer_ver IS NOT NULL"
    )
    tokenize.assert_tokenizer_match(r[0] for r in cur.fetchall())


_SQL = """
WITH vec AS (
    -- 벡터 채널: 청크 최대 코사인으로 원본 1건 점수를 정한다
    SELECT v.{vkey} AS k,
           MAX(1 - (v.embedding <=> %(qvec)s::vector)) AS score
    FROM   {vec} v
    GROUP  BY v.{vkey}
    ORDER  BY score DESC
    LIMIT  %(cand)s
),
vec_rank AS (
    SELECT k, score, ROW_NUMBER() OVER (ORDER BY score DESC) AS rnk FROM vec
),
kw AS (
    -- 키워드 채널: {score_sql_comment}
    -- tsq가 NULL이면(= 질의에 내용어가 없으면) 이 CTE는 0행이 되고
    -- 결합은 자연히 벡터 단독 결과가 된다.
    SELECT v.{vkey} AS k,
           MAX({score_expr}) AS score
    FROM   {vec} v,
           to_tsquery('simple', %(tsq)s) AS q(query)
    WHERE  %(tsq)s IS NOT NULL
      AND  v.tsv @@ q.query
    GROUP  BY v.{vkey}
    ORDER  BY score DESC
    LIMIT  %(cand)s
),
kw_rank AS (
    SELECT k, score, ROW_NUMBER() OVER (ORDER BY score DESC) AS rnk FROM kw
),
merged AS (
    SELECT k FROM vec_rank
    UNION
    SELECT k FROM kw_rank          -- 한쪽에만 잡힌 문서도 후보에 남긴다
)
SELECT b.{bkey}                                           AS id,
       b.{title_col}                                      AS title,
       b.{sub_col}                                        AS subtitle,
       ROUND(vr.score::numeric, 4)                        AS vec_score,
       vr.rnk                                             AS vec_rank,
       ROUND(kr.score::numeric, 4)                        AS kw_score,
       kr.rnk                                             AS kw_rank,
       ROUND((COALESCE(1.0 / (%(rrf_k)s + vr.rnk), 0)
            + COALESCE(1.0 / (%(rrf_k)s + kr.rnk), 0))::numeric, 6) AS rrf
FROM   merged m
LEFT   JOIN vec_rank vr ON vr.k = m.k
LEFT   JOIN kw_rank  kr ON kr.k = m.k
JOIN   {base} b ON b.{bkey} = m.k
ORDER  BY rrf DESC, vr.score DESC NULLS LAST
LIMIT  %(top)s
"""


def search(query: str, source: str = "news", top_k: int = 10,
           rrf_k: int = DEFAULT_RRF_K,
           candidates: int = DEFAULT_CANDIDATES,
           score_mode: str = DEFAULT_SCORE_MODE) -> List[Dict[str, Any]]:
    """질의 하나를 두 채널로 검색해 RRF로 합친 결과를 돌려준다.

    각 행은 두 채널의 점수·순위를 **그대로 달고 나온다**. 어느 채널이 그
    문서를 올렸는지 보이지 않으면 결과를 해석할 수도, 고칠 수도 없다.
    `vec_rank`나 `kw_rank`가 None이면 그 채널에는 안 걸렸다는 뜻이다.

    `score_mode`는 키워드 채널의 점수 방식이다(`DEFAULT_SCORE_MODE` 주석 참조).
    예전 방식(`cover_density`)을 남겨 둔 이유 — **바꿨다고 주장하려면 비교가
    가능해야 한다.** `scripts/eval_search.py`가 둘을 같은 질의로 잰다.
    """
    if source not in SOURCES:
        raise ValueError(f"알 수 없는 소스: {source} (가능: {sorted(SOURCES)})")
    vec, base, vkey, bkey, title_col, sub_col = SOURCES[source]
    score_expr, score_desc = _score_expr(score_mode)

    conn = get_conn()
    cur = conn.cursor()
    _assert_tokenizer(cur, vec)

    terms = tokenize.tokens(query)
    tsq = tokenize.to_tsquery(query, mode="or")
    if tsq is None:
        logger.info("질의에 내용어가 없어 벡터 채널만 사용한다: %r", query)

    params: Dict[str, Any] = {
        "qvec": str(embedder.encode_query(query)),   # ← `query: ` 프리픽스가 붙는다
        "tsq": tsq, "cand": candidates, "rrf_k": rrf_k, "top": top_k,
    }
    if score_mode == "idf_sum":
        # 토큰 순서를 고정해 두 배열이 짝을 이루게 한다 — 어긋나면 엉뚱한
        # 토큰에 엉뚱한 가중치가 붙고, 오류 없이 순위만 조용히 망가진다
        idf = token_idf(cur, vec, terms)
        ordered = [t for t in dict.fromkeys(terms) if t in idf]
        params["terms"] = ordered
        params["idfs"] = [idf[t] for t in ordered]
        if not ordered:
            params["terms"], params["idfs"] = [""], [0.0]

    cur.execute(
        _SQL.format(vec=vec, base=base, vkey=vkey, bkey=bkey,
                    title_col=title_col, sub_col=sub_col,
                    score_expr=score_expr, score_sql_comment=score_desc),
        params,
    )
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    cur.close()
    return rows


def rarest_token_df(query: str, source: str = "news") -> Optional[Dict[str, Any]]:
    """질의에서 가장 드문 토큰과 그 문서빈도를 돌려준다 — "결과 없음" 판정용.

    ADR-018이 질의 19건에서 유일하게 쓸 만하다고 본 규칙이다: **질의의 최희귀어가
    코퍼스에 아예 없으면 답도 없다.** 11건의 "정답 있음" 질의에서 오탐 0,
    "정답 없음" 8건 중 4건을 잡았다(16/19).

    ⚠️ 이건 **임계값이 아니라 존재 여부**다. 문서빈도에 `< 1%` 같은 선을 그으려는
    시도는 ADR-018에서 전부 실패했다 — 정답 있음 최저 0.63%와 정답 없음 최고
    25.3%의 구간이 겹친다. 여기서 쓰는 신호는 `df == 0` 하나뿐이다.

    반환 None은 질의에 내용어가 없다는 뜻이다(판정 불가).
    """
    vec = SOURCES[source][0]
    toks = tokenize.tokens(query)
    if not toks:
        return None

    conn = get_conn()
    cur = conn.cursor()
    _assert_tokenizer(cur, vec)
    cur.execute(f"SELECT count(*) FROM {vec} WHERE tsv <> ''")
    total = cur.fetchone()[0] or 0

    dfs = {}
    for t in dict.fromkeys(toks):                  # 중복 제거, 순서 유지
        cur.execute(
            f"SELECT count(*) FROM {vec} WHERE tsv @@ to_tsquery('simple', %s)", (t,)
        )
        dfs[t] = cur.fetchone()[0]
    cur.close()

    rarest = min(dfs, key=lambda t: dfs[t])
    return {
        "token": rarest,
        "df": dfs[rarest],
        "df_pct": round(100.0 * dfs[rarest] / total, 3) if total else None,
        "absent": dfs[rarest] == 0,                # ← 판정에 쓰는 유일한 신호
        "all_df": dfs,
    }
