"""하이브리드 검색의 결합 부분 — DB 없이 확인할 수 있는 범위.

실제 랭킹 품질은 DB가 있어야 재므로 여기서는 **구조적으로 깨지는 경우**만 막는다.
SQL 템플릿의 자리표시자 오타, 알 수 없는 소스, 토크나이저 불일치 통과 같은
것들은 전부 "오류 없이 결과만 비는" 방식으로 나타나서 눈으로는 안 보인다.
"""

import pytest

from src.search import hybrid, tokenize


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
