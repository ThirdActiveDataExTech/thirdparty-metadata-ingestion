"""내부 개발 콘솔 (프로토타입).

DB에 붙는 부분은 콘솔을 띄워 실제 데이터로 확인한다. 여기서는 **틀리면 사람 작업이
날아가거나 내보내면 안 될 것이 나가는** 두 곳만 못박는다.

1. **라벨 저장** — 393건은 사람이 한 건씩 누른 결과다. 저장이 어긋나면
   그 시간이 사라진다.
2. **동적 테이블 조회** — 미리보기는 테이블명을 DB에서 읽어 SQL에 넣는다.
   모양 검사와 비밀값 컬럼 차단이 풀리면 곧장 사고가 된다.
"""

import json

import pytest
from fastapi import HTTPException

from src.api import console


@pytest.fixture
def pool(tmp_path, monkeypatch):
    p = tmp_path / "pool.json"
    p.write_text(json.dumps([
        {"query_id": "q1", "query": "질의1",
         "candidates": [{"doc_id": "d1", "title": "문서1", "grade": None},
                        {"doc_id": "d2", "title": "문서2", "grade": None}]},
        {"query_id": "q2", "query": "질의2",
         "candidates": [{"doc_id": "d3", "title": "문서3", "grade": 1}]},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(console, "LABEL_POOL", p)
    return p


class TestLabeling:
    def test_진행률을_센다(self, pool):
        assert console._label_progress() == {"total": 3, "done": 1}

    def test_채점이_파일에_남는다(self, pool):
        """브라우저를 닫아도 남아야 한다 — 메모리에만 두면 그 시간이 사라진다."""
        console.save_label({"query_id": "q1", "doc_id": "d1", "grade": 2})
        saved = json.loads(pool.read_text(encoding="utf-8"))
        assert saved[0]["candidates"][0]["grade"] == 2
        assert console._label_progress()["done"] == 2

    def test_다른_후보를_건드리지_않는다(self, pool):
        console.save_label({"query_id": "q1", "doc_id": "d1", "grade": 0})
        saved = json.loads(pool.read_text(encoding="utf-8"))
        assert saved[0]["candidates"][1]["grade"] is None   # d2는 그대로
        assert saved[1]["candidates"][0]["grade"] == 1      # q2도 그대로

    def test_채점을_되돌릴_수_있다(self, pool):
        console.save_label({"query_id": "q2", "doc_id": "d3", "grade": None})
        assert console._label_progress()["done"] == 0

    def test_이상한_등급을_거부한다(self, pool):
        with pytest.raises(HTTPException) as e:
            console.save_label({"query_id": "q1", "doc_id": "d1", "grade": 5})
        assert e.value.status_code == 400

    def test_없는_조합이면_404(self, pool):
        with pytest.raises(HTTPException) as e:
            console.save_label({"query_id": "q1", "doc_id": "없음", "grade": 1})
        assert e.value.status_code == 404

    def test_파일이_없어도_죽지_않는다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(console, "LABEL_POOL", tmp_path / "없는파일.json")
        assert console._label_progress() == {"total": 0, "done": 0}


class TestDynamicTableGuards:
    """미리보기는 `data_registry.pg_meta_table`을 읽어 SQL에 넣는다."""

    def test_테이블명_모양을_검사한다(self):
        assert console._IDENT.match("meta_news")
        for bad in ("meta_news; DROP TABLE x", "Meta_News", "", "1table", "meta news"):
            assert not console._IDENT.match(bad), bad

    def test_자격증명_성격_컬럼을_거른다(self):
        for col in ("api_key", "accessToken", "secret_value", "password", "credential_type"):
            assert console.is_secret_column(col), col

    def test_평범한_컬럼은_통과한다(self):
        """`keywords`가 'key'에 걸려 사라지면 미리보기가 거짓말을 한다."""
        for col in ("title", "description", "published_at", "video_id",
                    "keywords", "search_keyword", "monkey"):
            assert not console.is_secret_column(col), col


class TestDecideGuard:
    def test_알_수_없는_처리를_거부한다(self):
        with pytest.raises(HTTPException) as e:
            console.decide_relation({"id": 1, "action": "지워버리기"})
        assert e.value.status_code == 400


class TestCatalogExclude:
    """홈 신규데이터는 외부 포털 연합분을 뺀다 — 쿼리에 실제로 걸리는지 본다(DB 없이)."""

    def test_제외_유형이_WHERE와_인자로_들어간다(self, monkeypatch):
        from src.api import console
        seen = {}

        class Cur:
            def execute(self, sql, params=None):
                seen.setdefault("calls", []).append((sql, params))
            def fetchall(self):
                return []
            def fetchone(self):
                return [0]
            description = []

        class Conn:
            def cursor(self):
                return Cur()

        monkeypatch.setattr(console, "get_conn", lambda: Conn())
        try:
            console.catalog(exclude_source_type="external_catalog, ", sort="created_at", limit=6, offset=0,
                            q=None, source_type=None, publisher=None, category=None, origin=None,
                            party=None, date_from=None, date_to=None, ids=None, user=None)
        except Exception:
            pass  # 결과 가공은 이 테스트의 관심이 아니다
        sql, params = seen["calls"][0]
        assert "NOT (source_type = ANY(%(xst)s))" in sql
        assert params["xst"] == ["external_catalog"]
