"""활용 기록 API (src/api/usage.py, 결정 3 — 2026-11-11).

실제 DB 없이 못박는 것
  - 화면은 조회(view)만 보낼 수 있다(내려받기는 서버가 성공했을 때만 기록)
  - 누구인지 모르면(로그인·세션 둘 다 없음) 세지 않는다 — 중복을 걸러낼 수 없다
  - 세션 식별자 원문은 저장하지 않는다(해시만)
  - 볼 수 없는 데이터셋엔 기록하지 않는다(404)
  - 테이블이 아직 없어도 본 기능(내려받기)은 성공하고, 집계는 available=false
"""

import hashlib

import pytest
from fastapi.testclient import TestClient
from psycopg2 import errors as pg_errors

from src.api import auth, main, usage
from src.api.main import app

URN = "urn:test:dataset:1"
SID = "abcDEF12-3456-7890"


class FakeCur:
    def __init__(self, visible=True, missing_table=False, insert_hits=True, rows=None):
        self.visible, self.missing_table, self.insert_hits = visible, missing_table, insert_hits
        self.rows = rows or []
        self.sql = []
        self._last = ""

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        self._last = sql
        if usage.TABLE in sql and self.missing_table:
            raise pg_errors.UndefinedTable("relation does not exist")

    def fetchone(self):
        if "FROM dcat_dataset WHERE dataset_id" in self._last:
            return (1,) if self.visible else None
        if "INSERT INTO" in self._last:
            return (7,) if self.insert_hits else None
        return None

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, cur):
        self.cur, self.commits, self.rollbacks = cur, 0, 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def db(monkeypatch):
    def make(**kw):
        conn = FakeConn(FakeCur(**kw))
        monkeypatch.setattr(usage, "get_conn", lambda: conn)
        monkeypatch.setattr(main, "get_conn", lambda: conn)
        return conn
    return make


def _inserts(conn):
    return [p for s, p in conn.cur.sql if s.startswith("INSERT INTO")]


def test_세션_식별자는_해시만_남기고_이상한_값은_버린다():
    assert usage.session_hash(SID) == hashlib.sha256(SID.encode()).hexdigest()[:32]
    for bad in (None, "", "short", "has space here!!", "x" * 65, "<script>alert(1)</script>"):
        assert usage.session_hash(bad) is None


def test_조회를_기록하고_세션_원문은_보내지_않는다(db):
    conn = db()
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN},
                             headers={"X-Usage-Session": SID})
    assert r.status_code == 200 and r.json() == {"recorded": True}
    (p,) = _inserts(conn)
    assert p["t"] == "view" and p["d"] == URN and p["o"] == "portal" and p["u"] is None
    assert p["s"] == usage.session_hash(SID) and SID not in str(conn.cur.sql)
    assert conn.commits == 1


def test_30분_안_같은_조회는_한_번으로_친다(db):
    conn = db(insert_hits=False)          # NOT EXISTS 조건에 걸려 아무 행도 안 들어감
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN},
                             headers={"X-Usage-Session": SID})
    assert r.json() == {"recorded": False}
    sql = next(s for s in (x for x, _ in conn.cur.sql) if s.startswith("INSERT"))
    assert "NOT EXISTS" in sql and "make_interval(mins" in sql


def test_화면은_내려받기를_보낼_수_없다(db):
    conn = db()
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "download", "dataset_id": URN},
                             headers={"X-Usage-Session": SID})
    assert r.status_code == 400 and _inserts(conn) == []


def test_누구인지_모르면_세지_않는다(db):
    conn = db()
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN})
    assert r.status_code == 200 and r.json()["recorded"] is False
    assert conn.cur.sql == []


def test_로그인_사용자는_ID로_기록한다(db, monkeypatch):
    conn = db()
    u = auth.User(id="org-a-user", name="A", role="user", org="org-a", org_name="A기관")
    monkeypatch.setitem(app.dependency_overrides, auth.optional_user, lambda: u)
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN})
    assert r.json() == {"recorded": True}
    assert _inserts(conn)[0]["u"] == "org-a-user" and _inserts(conn)[0]["who"] == "org-a-user"


def test_볼_수_없는_데이터셋은_404이고_기록하지_않는다(db):
    conn = db(visible=False)
    r = TestClient(app).post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN},
                             headers={"X-Usage-Session": SID})
    assert r.status_code == 404 and _inserts(conn) == []


def test_잘못된_입력(db):
    db()
    c = TestClient(app)
    h = {"X-Usage-Session": SID}
    assert c.post("/v1/usage/events", json={"event_type": "view"}, headers=h).status_code == 400
    assert c.post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN, "item_id": "x" * 400},
                  headers=h).status_code == 400
    assert c.get("/v1/usage/popular", params={"event_type": "like"}).status_code == 400


def test_테이블이_없으면_기록은_건너뛰고_집계는_비어_있다(db):
    conn = db(missing_table=True)
    c = TestClient(app)
    r = c.post("/v1/usage/events", json={"event_type": "view", "dataset_id": URN},
               headers={"X-Usage-Session": SID})
    assert r.status_code == 200 and r.json()["recorded"] is False and conn.rollbacks >= 1
    p = c.get("/v1/usage/popular").json()
    assert p["available"] is False and p["items"] == []
    d = c.get(f"/v1/usage/datasets/{URN}").json()
    assert d["available"] is False


def test_인기_데이터는_비로그인에게_공개_데이터만_보여_준다(db):
    conn = db(rows=[(URN, "제목", "video", "기관", 5, 3)])
    r = TestClient(app).get("/v1/usage/popular", params={"days": 7}).json()
    assert r["available"] and r["items"][0] == {"dataset_id": URN, "title": "제목", "source_type": "video",
                                                "publisher": "기관", "events": 5, "users": 3}
    sql = conn.cur.sql[-1][0]
    assert "d.visibility = 'PUBLIC'" in sql


def test_관리자_요약은_관리자만(db):
    db()
    assert TestClient(app).get("/v1/console/usage/summary").status_code == 401


def test_서버_기록은_실패해도_예외를_내지_않는다(db):
    conn = db(missing_table=True)
    usage.record_server_event("download", URN, None, SID, detail="package")
    assert conn.rollbacks == 1 and conn.commits == 0


def test_JSON_LD_내려받기를_기록한다(db, monkeypatch):
    conn = db()
    import src.storage.jsonld_export as je
    monkeypatch.setattr(je, "build_dataset_jsonld", lambda _id: {"@id": _id})
    r = TestClient(app).get(f"/v1/datasets/{URN}/jsonld", headers={"X-Usage-Session": SID})
    assert r.status_code == 200
    (p,) = _inserts(conn)
    assert p["t"] == "download" and p["x"] == "jsonld" and p["o"] == "server"


# ── API 직접 호출(2026-11-11 결정 A안): 따로 기록하고 화면 수치에서는 뺀다 ──

def test_누구인지_모르는_서버_내려받기는_api로_따로_남긴다(db):
    conn = db()
    usage.record_server_event("download", URN, None, None, detail="package")
    (p,) = _inserts(conn)
    assert p["o"] == "api" and p["u"] is None and p["s"] is None
    assert conn.commits == 1


def test_세션이_있으면_server로_남긴다(db):
    conn = db()
    usage.record_server_event("download", URN, None, SID, detail="hf")
    (p,) = _inserts(conn)
    assert p["o"] == "server" and p["s"] == usage.session_hash(SID)


def test_세션_형식이_이상하면_api로_본다(db):
    conn = db()
    usage.record_server_event("download", URN, None, "bad!", detail="jsonld")
    (p,) = _inserts(conn)
    assert p["o"] == "api"


def _selects(conn):
    return [s for s, _ in conn.cur.sql if s.startswith("SELECT") and usage.TABLE in s]


def test_인기_데이터와_상세_활용수는_api_호출을_빼고_센다(db):
    conn = db()
    TestClient(app).get("/v1/usage/popular")
    TestClient(app).get(f"/v1/usage/datasets/{URN}")
    sqls = _selects(conn)
    assert len(sqls) == 3
    assert all("origin <> 'api'" in s for s in sqls)


def test_관리자_요약은_api_호출을_따로_보여_준다(db, monkeypatch):
    conn = db()
    app.dependency_overrides[auth.require_admin] = lambda: None
    try:
        r = TestClient(app).get("/v1/console/usage/summary")
    finally:
        app.dependency_overrides.pop(auth.require_admin, None)
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == {"events": 0, "datasets": 0, "by_detail": []}
    sqls = _selects(conn)
    counted = [s for s in sqls if "origin <> 'api'" in s]
    api_only = [s for s in sqls if "origin = 'api'" in s]
    assert len(counted) == 4 and len(api_only) == 2


# ── 함께 본 데이터(C2 목표선, 2026-11-11) ──

def test_함께_본_데이터는_2명_이상이고_API_호출을_뺀다(db):
    conn = db(rows=[("urn:b", "B", 3)])
    r = TestClient(app).get(f"/v1/usage/also-viewed/{URN}")
    assert r.status_code == 200
    assert r.json()["items"] == [{"dataset_id": "urn:b", "title": "B", "people": 3}]
    sql, params = [x for x in conn.cur.sql if "viewers AS" in x[0]][0]
    assert "HAVING count(DISTINCT coalesce(e.user_id, e.session_hash)) >= %(minp)s" in sql
    assert params["minp"] == usage.CO_VIEW_MIN_PEOPLE >= 2
    assert sql.count("origin <> 'api'") == 2
    assert "d.visibility = 'PUBLIC'" in sql            # 비로그인 — 볼 수 있는 것만


def test_함께_본_데이터_테이블이_없으면_available_false(db):
    db(missing_table=True)
    r = TestClient(app).get(f"/v1/usage/also-viewed/{URN}")
    assert r.status_code == 200 and r.json()["available"] is False


def test_볼_수_없는_데이터셋은_404(db):
    db(visible=False)
    assert TestClient(app).get(f"/v1/usage/also-viewed/{URN}").status_code == 404


def test_내려받기_내역은_관리자만_내_내역은_로그인만(db):
    db()
    c = TestClient(app)
    assert c.get("/v1/console/usage/downloads").status_code == 401
    assert c.get("/v1/my/downloads").status_code == 401
