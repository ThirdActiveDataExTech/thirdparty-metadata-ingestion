"""사용자 API(/v1/my) — DB 없이 라우팅·권한·상태 판정·확정 기록을 본다.

실DB 왕복은 scratchpad 스모크(전부 ROLLBACK)로 따로 확인한다.
"""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from src.api import manage, my
from src.api.main import app
from src.database import category

URN = "urn:naver:blog_dataset_256a67"


def _endpoint(path: str, method: str):
    scope = {"type": "http", "path": path, "method": method, "root_path": ""}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.endpoint.__name__
    return None


@pytest.mark.parametrize("path,method,expected", [
    ("/v1/my/datasets", "GET", "my_datasets"),
    ("/v1/my/datasets", "POST", "register"),
    ("/v1/my/category-suggest", "POST", "category_suggest"),
    (f"/v1/my/datasets/{URN}/category", "PUT", "confirm_category"),
    (f"/v1/my/datasets/{URN}/visibility", "PUT", "set_visibility"),
    # 관리자 상세가 여전히 닿는다
    (f"/v1/console/datasets/{URN}/status", "GET", "dataset_status"),
])
def test_라우팅(path, method, expected):
    assert _endpoint(path, method) == expected


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": ""}, {"X-User-Id": "a b"}, {"X-User-Id": "x" * 80}])
def test_사용자_식별이_없으면_401(headers):
    r = TestClient(app).get("/v1/my/datasets", headers=headers)
    assert r.status_code == 401


def test_사용자_등록은_origin_user와_내_ID로(monkeypatch):
    seen = {}

    def fake(body, origin, owner_id):
        seen.update(origin=origin, owner_id=owner_id)
        return {"dataset_id": "urn:x", "status": "pending"}

    monkeypatch.setattr(manage, "register_as", fake)
    r = TestClient(app).post("/v1/my/datasets", json={"source_type": "blog", "origin": "admin"},
                             headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 200
    # 요청 본문의 origin은 무시한다 — 사용자가 관리자 등록을 할 수 없다
    assert seen == {"origin": "user", "owner_id": "demo-user-0001"}
    assert "네이버" in r.json()["export_note"]


# ── 상태 판정 ──────────────────────────────────────────────────────────────

S = lambda *cs: [{"category": c, "rank": i, "score": 0.8} for i, c in enumerate(cs, 1)]  # noqa: E731


def test_분류_미확정():
    assert my._category_state([], S("a", "b", "c"), None) == "needs_review"


def test_확정_후_추천_상위3이_바뀌면_알린다():
    last = {"shown": ["a", "b", "c", "d"]}
    assert my._category_state(["a"], S("a", "b", "x"), last) == "changed"


def test_순서만_바뀐_것은_알리지_않는다():
    last = {"shown": ["a", "b", "c"]}
    assert my._category_state(["a"], S("c", "a", "b", "z"), last) == "confirmed"


def test_이력이_없는_확정값은_확정으로_본다():
    """관리자가 13-A 이전에 확정한 경우 등 — 비교할 근거가 없으면 알리지 않는다."""
    assert my._category_state(["a"], S("x", "y", "z"), None) == "confirmed"


@pytest.mark.parametrize("reg,last,overdue,expected", [
    ("error", "2026-11-09", False, "error"),
    ("pending", None, False, "waiting"),
    ("active", "2026-11-09", True, "overdue"),
    ("active", "2026-11-09", False, "ok"),
])
def test_수집_상태(reg, last, overdue, expected):
    assert my._collection_state({"reg_status": reg, "last_collected_at": last, "overdue": overdue}) == expected


# ── 소유권 · 확정 기록 ─────────────────────────────────────────────────────

class FakeCur:
    def __init__(self, owner, category=None, suggestions=None):
        self.owner, self.category, self.suggestions = owner, category or [], suggestions or []
        self.sql, self._next = [], None

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if "SELECT owner_id, category" in sql:
            self._next = None if self.owner is None else (self.owner, self.category)
        elif "feature_name='suggested_category'" in sql:
            self._next = (self.suggestions,)
        else:
            self._next = None

    def fetchone(self):
        return self._next


class FakeConn:
    def __init__(self, cur):
        self.cur, self.committed, self.rolled = cur, False, False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled = True


def _client(monkeypatch, cur):
    conn = FakeConn(cur)
    monkeypatch.setattr(my, "get_conn", lambda: conn)
    return TestClient(app), conn


def test_남의_데이터셋은_403이고_아무것도_안_바꾼다(monkeypatch):
    cur = FakeCur(owner="demo-user-0002")
    c, conn = _client(monkeypatch, cur)
    r = c.put(f"/v1/my/datasets/{URN}/category", json={"category": ["기술 > 전기·전자"]},
              headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 403
    assert not any(s.startswith("UPDATE") for s, _ in cur.sql) and not conn.committed


def test_없는_데이터셋은_404(monkeypatch):
    c, _ = _client(monkeypatch, FakeCur(owner=None))
    r = c.put(f"/v1/my/datasets/{URN}/visibility", json={"visibility": "PUBLIC"},
              headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 404


def test_확정하면_보여준_추천과_고른_순위가_남는다(monkeypatch):
    cur = FakeCur(owner="demo-user-0001", category=[],
                  suggestions=S("기술 > 원자력", "기술 > 전기·전자", "과학 > 대기과학"))
    c, conn = _client(monkeypatch, cur)
    r = c.put(f"/v1/my/datasets/{URN}/category",
              json={"category": ["기술 > 전기·전자", "기술 > 에너지·자원"]},
              headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 200, r.text
    # 2위를 골랐고, 두 번째 값은 추천 밖이다
    assert r.json()["chosen_ranks"] == [2, None]
    ins = [p for s, p in cur.sql if "INSERT INTO meta_feature" in s][0]
    entry = json.loads(ins[2])[0]
    assert entry["actor"] == "demo-user-0001" and entry["role"] == "user"
    assert entry["previous"] == [] and entry["shown"][0] == "기술 > 원자력"
    assert conn.committed


def test_분류표에_없는_값은_거절(monkeypatch):
    c, conn = _client(monkeypatch, FakeCur(owner="demo-user-0001"))
    r = c.put(f"/v1/my/datasets/{URN}/category", json={"category": ["아무거나"]},
              headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 400 and not conn.committed


def test_유지는_지금_값이_있어야_한다(monkeypatch):
    c, _ = _client(monkeypatch, FakeCur(owner="demo-user-0001", category=[]))
    r = c.put(f"/v1/my/datasets/{URN}/category", json={"keep": True},
              headers={"X-User-Id": "demo-user-0001"})
    assert r.status_code == 400


def test_확정_이력은_공개_특징에서_빠진다():
    from src.common.category_taxonomy import PRIVATE_FEATURES
    assert category.DECISION_FEATURE in PRIVATE_FEATURES


def test_중복_경고에_남의_제목을_내지_않는다(monkeypatch):
    class Cur:
        def execute(self, *a): pass
        def fetchall(self): return [("urn:a", "demo-user-0001"), ("urn:b", "demo-user-0002")]

    class Conn:
        def cursor(self): return Cur()

    monkeypatch.setattr(my, "get_conn", lambda: Conn())
    out = my._mask_duplicates([{"dataset_id": "urn:a", "title": "내 것"},
                               {"dataset_id": "urn:b", "title": "남의 비공개 제목"}], "demo-user-0001")
    assert out[0]["title"] == "내 것"
    assert "남의 비공개 제목" not in str(out) and out[1]["dataset_id"] is None
