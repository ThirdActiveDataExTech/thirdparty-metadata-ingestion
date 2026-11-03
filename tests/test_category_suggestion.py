"""공통 분류 — 추천만 하고 확정하지 않는다 (ADR-020).

여기서 막으려는 회귀는 하나다: **수집이 사람이 고른 분류를 덮어쓰는 것.**
덮어써도 오류가 나지 않고, 다음 수집까지는 값이 맞아 보이기 때문에
사람이 고친 지 하루 뒤에 조용히 되돌아간다.
"""

import json

import pytest

from src.database import category as C


class _Cur:
    def __init__(self, row):
        self.row = row
        self.sql = []
        self.description = [("dataset_id",), ("title",), ("description",),
                            ("keywords",), ("theme",)]

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row

    def close(self):
        pass


class _Conn:
    def __init__(self, row):
        self.cur = _Cur(row)
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def patched(monkeypatch):
    def _apply(row=("ds1", "HBM 뉴스", "고대역폭 메모리 뉴스", None, None), scored=None):
        conn = _Conn(row)
        monkeypatch.setattr(C, "get_conn", lambda: conn)
        if scored is None:
            scored = [("기술 > 정보·통신", 0.81), ("문화 > 스포츠", 0.80)]
        monkeypatch.setattr(C, "classify", lambda *a, **k: scored)
        return conn
    return _apply


class TestNeverOverwritesCategory:
    def test_dcat_dataset_category를_건드리지_않는다(self, patched):
        # ADR-020의 핵심. 이게 깨지면 사람이 고른 값이 다음 수집에 사라진다
        conn = patched()
        C.sync_category("ds1")
        writes = [s for s, _ in conn.cur.sql if s.startswith("UPDATE dcat_dataset")]
        assert writes == [], f"category를 덮어썼다: {writes}"

    def test_추천은_meta_feature에_쌓는다(self, patched):
        conn = patched()
        C.sync_category("ds1")
        ins = [(s, p) for s, p in conn.cur.sql if "meta_feature" in s]
        assert len(ins) == 1
        sql, params = ins[0]
        assert "suggested_category" in sql
        assert "ON CONFLICT" in sql and "DO UPDATE" in sql   # 재계산이 자유로워야 한다

    def test_추천에_순위와_점수가_들어간다(self, patched):
        # 사람이 몇 위를 골랐는지 비교해야 분류기를 개선할 수 있다
        conn = patched()
        C.sync_category("ds1")
        _, params = next((s, p) for s, p in conn.cur.sql if "meta_feature" in s)
        value = json.loads(params[1])
        assert [v["rank"] for v in value] == [1, 2]
        assert set(value[0]) == {"category", "score", "rank"}
        assert value[0]["category"] == "기술 > 정보·통신"


class TestEmptyIsAllowed:
    def test_분류표에_없는_값은_버린다(self, patched):
        conn = patched(scored=[("있을 리 없는 > 분류", 0.9)])
        assert C.sync_category("ds1") == []
        assert not any("meta_feature" in s for s, _ in conn.cur.sql)

    def test_추천이_하나도_없으면_아무것도_쓰지_않는다(self, patched):
        # 억지로 채우지 않는다 — 틀린 분류는 빈 분류보다 나쁘다
        conn = patched(scored=[])
        assert C.sync_category("ds1") == []
        assert conn.committed is False

    def test_없는_데이터셋은_빈_결과(self, patched):
        conn = patched(row=None)
        assert C.sync_category("없는id") == []


class TestSuggestCount:
    def test_추천은_5개다(self):
        # HBM 뉴스의 적합한 분류가 3위였고 1~5위 점수 차가 잡음 수준이라
        # 3개로 자르면 밀려난다
        assert C.SUGGEST_N == 5

    def test_classify에_추천_개수를_넘긴다(self, patched, monkeypatch):
        patched()                       # ← 먼저. 이 픽스처도 classify를 패치한다
        seen = {}

        def _spy(text, top_n=None):
            seen["n"] = top_n
            return [("기술 > 정보·통신", 0.8)]

        monkeypatch.setattr(C, "classify", _spy)
        C.sync_category("ds1")
        assert seen["n"] == C.SUGGEST_N
