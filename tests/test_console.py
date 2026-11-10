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


    def test_참거짓은_등급이_아니다(self, pool):
        """`True == 1`이라 그대로 두면 체크박스 값이 '부분 관련'으로 저장된다."""
        with pytest.raises(HTTPException) as e:
            console.save_label({"query_id": "q1", "doc_id": "d1", "grade": True})
        assert e.value.status_code == 400

    def test_겹친_저장이_서로를_덮지_않는다(self, pool):
        """키보드로 빠르게 누르면 요청이 겹친다. 하나라도 사라지면 사람 시간이 사라진다."""
        import threading
        jobs = [("q1", "d1", 2), ("q1", "d2", 1), ("q2", "d3", 0)] * 5
        ts = [threading.Thread(target=console.save_label,
                               args=({"query_id": q, "doc_id": d, "grade": g},)) for q, d, g in jobs]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        saved = json.loads(pool.read_text(encoding="utf-8"))
        assert [c["grade"] for q in saved for c in q["candidates"]] == [2, 1, 0]
        assert not pool.with_name(pool.name + ".tmp").exists()


class _Cur:
    """`_video_context` 한 번 조회를 흉내 낸다. 받은 SQL·인자를 남긴다."""

    def __init__(self, rows, fail=False):
        self.rows, self.fail, self.calls = rows, fail, []
        self.description = [(n,) for n in (
            "id", "video_id", "channel_title", "published_at", "duration_seconds",
            "description", "thumbnail_url", "has_transcript", "is_removed",
            "ai_summary", "ai_keywords")]

    def execute(self, sql, params=None):
        if self.fail:
            raise RuntimeError("DB 끊김")
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, cur):
        self.cur = cur

    def cursor(self):
        return self.cur


@pytest.fixture
def video_pool(tmp_path, monkeypatch):
    import datetime as dt
    p = tmp_path / "pool.json"
    p.write_text(json.dumps([
        {"query_id": "tp0", "query": "치질 수술",
         "candidates": [{"doc_id": "101", "title": "영상1", "grade": None},
                        {"doc_id": "102", "title": "영상2", "grade": 2},
                        {"doc_id": "999", "title": "지워진 영상", "grade": None}]},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(console, "LABEL_POOL", p)
    cur = _Cur([
        (101, "abc", "청주항문외과", dt.datetime(2024, 5, 1, 9, 0, tzinfo=dt.timezone.utc), 312,
         "설명 " * 200, "https://i.ytimg.com/vi/abc/hq.jpg", True, False,
         "수술 후 회복 기간을   안내합니다.", ["치질", "회복"]),
        (102, "def", "SK하이닉스", None, None, "짧은 설명", None, False, False, None, None),
    ])
    monkeypatch.setattr(console, "get_conn", lambda: _Conn(cur))
    return p, cur


class TestLabelingContext:
    def test_한_번에_묶어_조회한다(self, video_pool):
        _, cur = video_pool
        console.labeling()
        assert len(cur.calls) == 1
        assert cur.calls[0][1] == ([101, 102, 999],)

    def test_맥락을_덧붙이되_기존_필드는_그대로(self, video_pool):
        r = console.labeling()
        c1, c2, c3 = r["queries"][0]["candidates"]
        assert (c1["doc_id"], c1["title"], c1["grade"]) == ("101", "영상1", None)
        assert c1["channel"] == "청주항문외과"
        assert c1["published_at"] == "2024-05-01"
        assert c1["duration_seconds"] == 312
        assert c1["snippet"] == "수술 후 회복 기간을 안내합니다."   # 공백 정리
        assert c1["snippet_source"] == "ai_summary"
        assert c1["url"] == "https://www.youtube.com/watch?v=abc"
        assert c2["grade"] == 2 and c2["snippet"] == "짧은 설명"
        assert c2["snippet_source"] == "description"
        assert "channel" not in c3               # DB에 없는 후보는 맥락 없이 그대로
        assert r["progress"] == {"total": 3, "done": 1}
        assert r["context_error"] is None

    def test_요약은_200자로_자른다(self, video_pool, monkeypatch):
        _, cur = video_pool
        cur.rows = [cur.rows[0][:9] + (None, None)]   # AI 요약 없음 → 긴 설명
        c1 = console.labeling()["queries"][0]["candidates"][0]
        assert c1["snippet_source"] == "description"
        assert len(c1["snippet"]) <= console.CONTEXT_SNIPPET + 1 and c1["snippet"].endswith("…")

    def test_조회는_파일을_바꾸지_않는다(self, video_pool):
        p, _ = video_pool
        before = p.read_text(encoding="utf-8")
        console.labeling()
        assert p.read_text(encoding="utf-8") == before

    def test_DB가_안_돼도_채점은_할_수_있다(self, video_pool, monkeypatch):
        monkeypatch.setattr(console, "get_conn", lambda: _Conn(_Cur([], fail=True)))
        r = console.labeling()
        assert r["context_error"]
        assert [c["doc_id"] for c in r["queries"][0]["candidates"]] == ["101", "102", "999"]

    def test_숫자가_아닌_id는_조회하지_않는다(self, pool, monkeypatch):
        def boom():
            raise AssertionError("조회하면 안 된다")
        monkeypatch.setattr(console, "get_conn", boom)
        assert console._video_context(["d1", "d2"]) == {}

    def test_관리자_전용이다(self):
        from src.api.auth import require_admin
        route = next(r for r in console.router.routes
                     if r.path.endswith("/labeling") and "GET" in r.methods)
        assert any(d.call is require_admin for d in route.dependant.dependencies)


class TestPoolStorage:
    @pytest.mark.parametrize("flag,pod,expected", [
        ("1", True, True), ("0", False, False), ("", True, False), ("", False, True)])
    def test_영구_저장_여부(self, pool, monkeypatch, flag, pod, expected):
        monkeypatch.setenv("LABEL_POOL_PERSISTENT", flag)
        if pod:
            monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
        else:
            monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        s = console._pool_storage()
        assert s["persistent"] is expected
        assert s["writable"] is True and s["path"].endswith("pool.json")

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


class TestSearchItems:
    """아이템 검색 — 공개 범위로 거른 뒤 limit을 채우고, RRF 순서를 지킨다.

    2026-11-10 왕복을 줄이면서(소유 조회·공개 범위·원본·제목 4번 → 원본·공개 범위+제목 2번)
    거르는 규칙이 바뀌지 않았음을 못박는다.
    """

    class _Cur:
        def __init__(self, items, datasets):
            self.items, self.datasets, self.calls = items, datasets, []
            self.description, self._rows = [], []

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            if "FROM meta_" in sql and "meta_video_ai" not in sql:
                ids = params[0]
                self.description = [("id",), ("dataset_id",), ("title",), ("description",),
                                    ("published_at",), ("byline",), ("url",), ("thumbnail_url",)]
                self._rows = [(i, self.items[i], f"t{i}", None, None, None, None, None)
                              for i in ids if i in self.items]
            elif "FROM dcat_dataset" in sql:
                # 공개 범위 조건까지 DB가 거른 결과라고 본다 — 볼 수 있는 것만 둔다
                self._rows = [(d, self.datasets[d]) for d in params["_ids"] if d in self.datasets]
            else:
                self.description, self._rows = [("meta_id",), ("ai_summary",), ("ai_keywords",)], []

        def fetchall(self):
            return list(self._rows)

    def _run(self, monkeypatch, hits, items, visible, limit=2):
        from src.search import hybrid
        cur = self._Cur(items, visible)
        monkeypatch.setattr(hybrid, "search", lambda q, s, top_k=10, **kw: hits[:top_k])
        monkeypatch.setattr(hybrid, "rarest_token_df", lambda q, s: None)
        monkeypatch.setattr(console, "get_conn", lambda: type("C", (), {"cursor": lambda self: cur})())
        return console.search_items(q="반도체", source="blog", limit=limit, user=None), cur

    @staticmethod
    def _hit(i, rrf):
        return {"id": i, "title": f"t{i}", "subtitle": None, "rrf": rrf,
                "vec_rank": 1, "kw_rank": None}

    def test_볼_수_없는_데이터셋의_아이템을_빼고_limit을_채운다(self, monkeypatch):
        hits = [self._hit(1, 0.03), self._hit(2, 0.02), self._hit(3, 0.01), self._hit(4, 0.005)]
        items = {1: "dsA", 2: "dsHidden", 3: "dsB", 4: "dsA"}
        out, _ = self._run(monkeypatch, hits, items, {"dsA": "A", "dsB": "B"}, limit=2)
        assert [r["id"] for r in out["items"]] == [1, 3]           # RRF 순서 유지, 2는 빠짐
        assert [r["dataset_title"] for r in out["items"]] == ["A", "B"]

    def test_원본이_없는_아이템은_뺀다(self, monkeypatch):
        out, _ = self._run(monkeypatch, [self._hit(9, 0.1)], {}, {"dsA": "A"})
        assert out["items"] == []

    def test_DB_왕복은_두_번이다(self, monkeypatch):
        hits = [self._hit(1, 0.03), self._hit(2, 0.02)]
        _, cur = self._run(monkeypatch, hits, {1: "dsA", 2: "dsA"}, {"dsA": "A"})
        assert len(cur.calls) == 2

    def test_결과가_없으면_DB를_부르지_않는다(self, monkeypatch):
        out, cur = self._run(monkeypatch, [], {}, {})
        assert out["items"] == [] and cur.calls == []
