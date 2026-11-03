"""하이브리드 검색의 결합 부분 — DB 없이 확인할 수 있는 범위.

실제 랭킹 품질은 DB가 있어야 재므로 여기서는 **구조적으로 깨지는 경우**만 막는다.
SQL 템플릿의 자리표시자 오타, 알 수 없는 소스, 토크나이저 불일치 통과 같은
것들은 전부 "오류 없이 결과만 비는" 방식으로 나타나서 눈으로는 안 보인다.
"""

import pytest

from src.search import hybrid, tokenize


class _FakeCursor:
    """실행된 SQL과 파라미터를 받아 적는다."""

    def __init__(self, versions):
        self._versions = versions
        self.calls = []
        self.description = [("id",), ("title",), ("subtitle",), ("vec_score",),
                            ("vec_rank",), ("kw_score",), ("kw_rank",), ("rrf",)]
        self._last_is_version_probe = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._last_is_version_probe = "DISTINCT tokenizer_ver" in sql

    def fetchall(self):
        if self._last_is_version_probe:
            return [(v,) for v in self._versions]
        return [(1, "제목", "부제", 0.9, 1, 0.5, 2, 0.03)]

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
        sql, params = conn.cur.calls[-1]
        assert "{" not in sql and "}" not in sql
        vec, base, vkey, bkey, title_col, sub_col = hybrid.SOURCES[source]
        assert vec in sql and base in sql

    def test_알_수_없는_소스는_거부한다(self):
        with pytest.raises(ValueError):
            hybrid.search("질의", "없는소스")

    def test_두_채널과_RRF가_모두_SQL에_있다(self, patched):
        conn = patched()
        hybrid.search("반도체 수출", "news")
        sql, _ = conn.cur.calls[-1]
        assert "embedding <=>" in sql          # 벡터 채널
        assert "ts_rank_cd" in sql             # 키워드 채널
        assert "to_tsquery" in sql
        assert "1.0 / (" in sql                # RRF


class TestQueryParams:
    def test_질의가_토큰화되어_전달된다(self, patched):
        conn = patched()
        hybrid.search("반도체 수출 규제가", "news")
        _, params = conn.cur.calls[-1]
        assert params["tsq"] == "반도체 | 수출 | 규제"   # 조사 '가'가 떨어졌다

    def test_내용어가_없으면_tsq는_None(self, patched):
        # 키워드 채널 CTE가 0행이 되고 벡터 단독 결과로 수렴한다 — 오류가 아니다
        conn = patched()
        hybrid.search("!!! ???", "news")
        _, params = conn.cur.calls[-1]
        assert params["tsq"] is None

    def test_rrf_k를_바꿀_수_있다(self, patched):
        # ADR-010이 k ∈ {10,20,30,60} 스윕을 평가 항목으로 정해 뒀다
        conn = patched()
        hybrid.search("반도체", "news", rrf_k=10)
        _, params = conn.cur.calls[-1]
        assert params["rrf_k"] == 10

    def test_기본_RRF_상수는_60(self):
        assert hybrid.DEFAULT_RRF_K == 60

    def test_후보_깊이가_top_k보다_넉넉하다(self, patched):
        # 얕으면 한쪽 채널에만 잡히는 정답이 결합 단계에 도달하지 못한다
        conn = patched()
        hybrid.search("반도체", "news", top_k=10)
        _, params = conn.cur.calls[-1]
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
