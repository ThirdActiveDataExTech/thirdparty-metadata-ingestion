"""하이브리드 검색의 결합 부분 — DB 없이 확인할 수 있는 범위.

실제 랭킹 품질은 DB가 있어야 재므로 여기서는 **구조적으로 깨지는 경우**만 막는다.
SQL 템플릿의 자리표시자 오타, 알 수 없는 소스, 토크나이저 불일치 통과 같은
것들은 전부 "오류 없이 결과만 비는" 방식으로 나타나서 눈으로는 안 보인다.
"""

import pytest

from src.search import hybrid, synonyms, tokenize


@pytest.fixture(autouse=True)
def _no_synonyms(monkeypatch, tmp_path):
    """기존 테스트는 동의어 없이 본다 — 사전 내용이 바뀌어도 흔들리지 않게. 동의어는 test_search_synonyms.py"""
    monkeypatch.setattr(synonyms, "PATH", tmp_path / "none.yaml")
    synonyms.reset()
    yield
    synonyms.reset()


class _FakeCursor:
    """실행된 SQL과 파라미터를 받아 적는다.

    `search()`는 DB를 세 번 부른다 — 토크나이저 버전 확인, (idf_sum이면) IDF 계산,
    본 검색. SQL 모양으로 구분해 각각 알맞은 모양을 돌려준다.
    """

    SEARCH_COLS = [("id",), ("title",), ("subtitle",), ("vec_score",),
                   ("vec_rank",), ("kw_score",), ("kw_rank",), ("rrf",)]

    def __init__(self, versions):
        self._versions = versions
        self.calls = []
        self.description = self.SEARCH_COLS
        self._kind = "search"

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "DISTINCT tokenizer_ver" in sql:
            self._kind = "version"
        elif "count(*)" in sql and "tsv <> ''" in sql:
            self._kind = "total"
        elif "unnest(" in sql and "AS t(term)" in sql:
            self._kind = "df"
        else:
            self._kind = "search"
        self.description = None if self._kind == "total" else self.SEARCH_COLS

    def fetchall(self):
        if self._kind == "version":
            return [(v,) for v in self._versions]
        if self._kind == "df":
            # (토큰, 문서빈도) — 실제 질의 토큰을 그대로 돌려줘야 짝이 맞는다
            terms = self.calls[-1][1][0]
            override = getattr(self, "_df_override", None)
            if override is not None:
                return [(t, override) for t in terms]
            return [(t, i + 1) for i, t in enumerate(terms)]
        return [(1, "제목", "부제", 0.9, 1, 0.5, 2, 0.03)]

    def fetchone(self):
        if self._kind == "total":
            return (1000,)
        return self.fetchall()[0]

    @property
    def search_calls(self):
        """본 검색 호출만. 보조 질의(버전·IDF)를 걸러낸다."""
        return [(s, p) for s, p in self.calls
                if "embedding <=>" in s]

    def close(self):
        pass


class _FakeConn:
    def __init__(self, versions):
        self.cur = _FakeCursor(versions)

    def cursor(self):
        return self.cur


@pytest.fixture(autouse=True)
def _fresh_caches():
    """토크나이저 대조·문서빈도 캐시가 테스트 사이로 새지 않게 한다."""
    hybrid.clear_caches()
    yield
    hybrid.clear_caches()


@pytest.fixture
def patched(monkeypatch):
    def _apply(versions=None):
        conn = _FakeConn(versions if versions is not None else [tokenize.version()])
        monkeypatch.setattr(hybrid, "get_conn", lambda: conn)
        monkeypatch.setattr(hybrid.embedder, "encode_query", lambda q: [0.0] * 768)
        return conn
    return _apply


class TestSqlTemplate:
    @pytest.mark.parametrize("source", sorted(hybrid.SOURCES))
    def test_모든_소스에_대해_SQL이_조립된다(self, source, patched):
        # 자리표시자 이름이 하나라도 틀리면 여기서 KeyError로 잡힌다
        conn = patched()
        hybrid.search("반도체 수출", source)
        sql, params = conn.cur.search_calls[-1]
        assert "{" not in sql and "}" not in sql
        vec, base, vkey, bkey, title_col, sub_col = hybrid.SOURCES[source]
        assert vec in sql and base in sql

    def test_알_수_없는_소스는_거부한다(self):
        with pytest.raises(ValueError):
            hybrid.search("질의", "없는소스")

    def test_두_채널과_RRF가_모두_SQL에_있다(self, patched):
        conn = patched()
        hybrid.search("반도체 수출", "news")
        sql, _ = conn.cur.search_calls[-1]
        assert "embedding <=>" in sql          # 벡터 채널
        assert "to_tsquery" in sql             # 키워드 채널
        assert "1.0 / (" in sql                # RRF

    @pytest.mark.parametrize("mode, marker", [
        ("cover_density", "ts_rank_cd"),
        ("idf_sum", "w.idf"),
    ])
    def test_점수_방식이_SQL에_반영된다(self, mode, marker, patched):
        conn = patched()
        hybrid.search("반도체 수출", "news", score_mode=mode)
        sql, _ = conn.cur.search_calls[-1]
        assert marker in sql

    def test_알_수_없는_점수_방식은_거부한다(self, patched):
        patched()
        with pytest.raises(ValueError):
            hybrid.search("반도체", "news", score_mode="없는모드")


class TestIdfScoring:
    """IDF 가중 — 2026-11-04 회귀(recall@1 1.0→0.73)의 처방.

    `ts_rank_cd`는 IDF를 쓰지 않아 고빈도어가 빽빽한 문서가 희귀어를 담은
    정답을 밀어냈다. k 스윕으로는 못 고쳤다(60/30/20/10 전부 0.7333).
    """

    def test_기본_점수_방식이_IDF다(self):
        assert hybrid.DEFAULT_SCORE_MODE == "idf_sum"

    def test_토큰과_가중치_배열의_길이가_같다(self, patched):
        # 어긋나면 엉뚱한 토큰에 엉뚱한 가중치가 붙고, 오류 없이 순위만 망가진다
        conn = patched()
        hybrid.search("반도체 수출 규제가", "news", score_mode="idf_sum")
        _, params = conn.cur.search_calls[-1]
        assert len(params["terms"]) == len(params["idfs"])
        assert params["terms"] == ["반도체", "수출", "규제"]

    def test_내용어가_없으면_빈_가중치로_넘어간다(self, patched):
        # 키워드 채널이 0점이 되고 벡터 단독으로 수렴한다 — 오류가 아니다
        conn = patched()
        hybrid.search("!!! ???", "news", score_mode="idf_sum")
        _, params = conn.cur.search_calls[-1]
        assert params["tsq"] is None
        assert len(params["terms"]) == len(params["idfs"])

    def test_cover_density는_가중치를_넘기지_않는다(self, patched):
        conn = patched()
        hybrid.search("반도체", "news", score_mode="cover_density")
        _, params = conn.cur.search_calls[-1]
        assert "terms" not in params

    def test_드문_토큰이_더_큰_IDF를_받는다(self, patched):
        # ln(N/df) — df가 작을수록 크다. 이 단조성이 깨지면 처방 전체가 무의미하다
        conn = patched()
        idf = hybrid.token_idf(conn.cur, "meta_news_vec", ["희귀어", "흔한말", "더흔한말"])
        assert idf["희귀어"] > idf["흔한말"] > idf["더흔한말"]

    def test_코퍼스에_없는_토큰도_점수를_받는다(self, patched):
        # df=0이면 IDF가 무한대가 된다. ln(N)으로 막는다
        conn = patched()
        conn.cur._df_override = 0
        idf = hybrid.token_idf(conn.cur, "meta_news_vec", ["없는말"])
        assert idf["없는말"] > 0 and idf["없는말"] != float("inf")


class TestQueryParams:
    def test_질의가_토큰화되어_전달된다(self, patched):
        conn = patched()
        hybrid.search("반도체 수출 규제가", "news")
        _, params = conn.cur.search_calls[-1]
        assert params["tsq"] == "반도체 | 수출 | 규제"   # 조사 '가'가 떨어졌다

    def test_내용어가_없으면_tsq는_None(self, patched):
        # 키워드 채널 CTE가 0행이 되고 벡터 단독 결과로 수렴한다 — 오류가 아니다
        conn = patched()
        hybrid.search("!!! ???", "news")
        _, params = conn.cur.search_calls[-1]
        assert params["tsq"] is None

    def test_rrf_k를_바꿀_수_있다(self, patched):
        # ADR-010이 k ∈ {10,20,30,60} 스윕을 평가 항목으로 정해 뒀다
        conn = patched()
        hybrid.search("반도체", "news", rrf_k=10)
        _, params = conn.cur.search_calls[-1]
        assert params["rrf_k"] == 10

    def test_기본_RRF_상수는_60(self):
        assert hybrid.DEFAULT_RRF_K == 60

    def test_후보_깊이가_top_k보다_넉넉하다(self, patched):
        # 얕으면 한쪽 채널에만 잡히는 정답이 결합 단계에 도달하지 못한다
        conn = patched()
        hybrid.search("반도체", "news", top_k=10)
        _, params = conn.cur.search_calls[-1]
        assert params["cand"] >= 10 * 10


class TestTokenizerGuard:
    def test_불일치하면_검색을_중단한다(self, patched):
        # 통과시키면 오류 없이 리콜만 0이 된다
        patched(versions=["kiwi-0.0.1+model-0+pos0"])
        with pytest.raises(tokenize.TokenizerMismatch):
            hybrid.search("반도체", "news")

    def test_백필_전이면_통과한다(self, patched):
        # tokenizer_ver가 전부 NULL = 아직 토큰이 없다. 결과 0건으로 드러난다
        patched(versions=[])
        hybrid.search("반도체", "news")


class TestResultShape:
    def test_채널별_순위가_결과에_실려_나온다(self, patched):
        # 어느 채널이 올렸는지 안 보이면 결과를 해석할 수도 고칠 수도 없다
        patched()
        row = hybrid.search("반도체", "news")[0]
        assert set(row) >= {"vec_rank", "kw_rank", "vec_score", "kw_score", "rrf"}


class TestVectorChannelUsesIndex:
    """2026-11-10 지연(blog 31초)의 원인 — 벡터 채널이 모든 청크의 거리를 계산했다.

    `GROUP BY 원본 → MAX → ORDER BY`를 먼저 하면 HNSW 색인이 있어도 쓰이지 않는다.
    색인은 `ORDER BY embedding <=> q LIMIT n` 모양일 때만 탄다.
    """

    def _vec_chunks_cte(self, sql):
        start = sql.index("vec_chunks AS (")
        return sql[start:sql.index("),", start)]

    def test_청크_단계가_거리순_LIMIT_모양이다(self, patched):
        conn = patched()
        hybrid.search("반도체", "blog")
        sql, _ = conn.cur.search_calls[-1]
        cte = self._vec_chunks_cte(sql)
        assert "ORDER  BY v.embedding <=> %(qvec)s::vector" in cte
        assert "LIMIT  %(chunk_cand)s" in cte
        assert "GROUP" not in cte                  # 묶기는 색인 탐색 **뒤**에 한다

    def test_원본_점수는_여전히_청크_최대값이다(self, patched):
        # 집계 단위(최대값)가 바뀌면 순위 의미가 바뀐다 — 평균 등으로 새지 않게
        conn = patched()
        hybrid.search("반도체", "blog")
        sql, _ = conn.cur.search_calls[-1]
        assert "MAX(1 - dist) AS score" in sql
        assert "LIMIT  %(cand)s" in sql

    def test_청크_후보가_원본_후보보다_넉넉하다(self, patched):
        # 원본 200건을 채우는 데 실측 221~585 청크가 필요했다
        conn = patched()
        hybrid.search("반도체", "blog", candidates=200)
        _, params = conn.cur.search_calls[-1]
        assert params["chunk_cand"] == 200 * hybrid.VEC_CHUNK_FACTOR
        assert params["chunk_cand"] >= 200 * 3

    def test_HNSW_설정을_같은_트랜잭션에서_보낸다(self, patched):
        # SET LOCAL은 트랜잭션 안에서만 유효하다. 따로 보내면 사이에 커밋/롤백이
        # 끼어 기본값(ef_search 40, 반복 탐색 없음)으로 돌아가 후보가 40개로 줄 수 있다
        conn = patched()
        hybrid.search("반도체", "blog")
        sql, _ = conn.cur.search_calls[-1]
        head = sql[:sql.index("WITH")]
        assert "SET LOCAL hnsw.iterative_scan = relaxed_order" in head
        assert f"SET LOCAL hnsw.ef_search = {hybrid.HNSW_EF_SEARCH}" in head
        assert "SET LOCAL hnsw.max_scan_tuples" in head


class TestRoundTrips:
    """검색 한 번에 DB를 몇 번 오가는가 — 원격 DB라 왕복이 곧 지연이다."""

    def _count(self, conn, marker):
        return sum(1 for sql, _ in conn.cur.calls if marker in sql)

    def test_토크나이저_대조는_한_번만_한다(self, patched):
        # blog에서 1.6초짜리 전체 스캔이었다. 아이템 검색은 검색+최희귀어로 두 번 불렀다
        conn = patched()
        hybrid.search("반도체", "blog")
        hybrid.rarest_token_df("반도체", "blog")
        hybrid.search("메모리", "blog")
        assert self._count(conn, "DISTINCT tokenizer_ver") == 1

    def test_소스가_다르면_따로_대조한다(self, patched):
        conn = patched()
        hybrid.search("반도체", "blog")
        hybrid.search("반도체", "news")
        assert self._count(conn, "DISTINCT tokenizer_ver") == 2

    def test_대조_유효시간이_지나면_다시_확인한다(self, patched, monkeypatch):
        conn = patched()
        monkeypatch.setattr(hybrid, "TOKENIZER_CHECK_TTL", 0.0)
        hybrid.search("반도체", "blog")
        hybrid.search("반도체", "blog")
        assert self._count(conn, "DISTINCT tokenizer_ver") == 2

    def test_불일치는_기억하지_않고_매번_막는다(self, patched):
        patched(versions=["kiwi-0.0.1+model-0+pos0"])
        for _ in range(2):
            with pytest.raises(tokenize.TokenizerMismatch):
                hybrid.search("반도체", "news")

    def test_문서빈도는_한_번에_센다(self, patched):
        # 예전 최희귀어 판정은 토큰마다 한 번씩 왕복했다
        conn = patched()
        hybrid.rarest_token_df("반도체 수출 규제가", "news")
        assert self._count(conn, "AS t(term)") == 1
        assert self._count(conn, "tsv @@ to_tsquery('simple', %s)") == 0

    def test_검색과_최희귀어가_문서빈도를_같이_쓴다(self, patched):
        conn = patched()
        hybrid.search("반도체 수출", "news")
        hybrid.rarest_token_df("반도체 수출", "news")
        assert self._count(conn, "AS t(term)") == 1
        assert self._count(conn, "tsv <> ''") == 1

    def test_최희귀어_판정_결과는_예전과_같은_모양이다(self, patched):
        conn = patched()
        conn.cur._df_override = 0
        r = hybrid.rarest_token_df("반도체 수출", "news")
        assert r["absent"] is True and r["df"] == 0
        assert list(r["all_df"]) == ["반도체", "수출"]
        assert r["df_pct"] == 0.0

    def test_최희귀어는_가장_작은_df를_고른다(self, patched):
        patched()           # 가짜 커서는 토큰 순서대로 df 1, 2, … 를 준다
        r = hybrid.rarest_token_df("반도체 수출", "news")
        assert r["token"] == "반도체" and r["df"] == 1 and r["absent"] is False

    def test_문서빈도_유효시간이_지나면_다시_센다(self, patched, monkeypatch):
        # 수집 중엔 N·df가 바뀐다 — 오래 들고 있으면 IDF가 낡는다
        conn = patched()
        monkeypatch.setattr(hybrid, "TOKEN_STATS_TTL", 0.0)
        hybrid.search("반도체", "news")
        hybrid.search("반도체", "news")
        assert self._count(conn, "AS t(term)") == 2

    def test_벡터_순위의_동점은_키로_가른다(self, patched):
        # 중복 문구 청크로 점수가 정확히 같은 원본이 수십 건 나온다. 키로 가르지 않으면
        # 실행 계획(정확 검색 ↔ 색인)에 따라 vec_rank가 달라지고 RRF 합도 달라진다
        conn = patched()
        hybrid.search("반도체", "video")
        sql, _ = conn.cur.search_calls[-1]
        assert "ORDER  BY score DESC, k" in sql
        assert "ROW_NUMBER() OVER (ORDER BY score DESC, k)" in sql
