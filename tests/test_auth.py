"""시제품 로그인(ADR-021)과 공개 범위 — DB 없이.

가장 중요한 것은 **관리자 API가 하나도 빠짐없이 막혀 있는가**다. 라우트를 하나씩 손으로 적으면
새 라우트를 추가할 때 빠뜨린다. 그래서 앱의 라우트 전체를 훑어, 공개 목록에 없는 콘솔 라우트는
전부 `require_admin`을 거치는지 본다.
"""

import time

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.routing import Match

from src.api import access, auth
from src.api.auth import User
from src.api.main import app

KEY = "k" * 40


@pytest.fixture(autouse=True)
def accounts(tmp_path, monkeypatch):
    f = tmp_path / "users.yaml"
    f.write_text(yaml.safe_dump({
        "orgs": {"operator": "운영기관", "org-a": "기관 A", "org-b": "기관 B"},
        "users": [
            {"id": "admin", "name": "관리자", "role": "admin", "org": "operator",
             "password_hash": auth.hash_password("admin-pw", iterations=1000)},
            {"id": "u1", "name": "사용자1", "role": "user", "org": "org-a",
             "password_hash": auth.hash_password("u1-pw", iterations=1000)},
            {"id": "u2", "name": "사용자2", "role": "user", "org": "org-a", "password_hash": None},
            {"id": "u4", "name": "사용자4", "role": "user", "org": "org-b",
             "password_hash": auth.hash_password("u4-pw", iterations=1000)},
            {"id": "x", "name": "역할 오류", "role": "root", "org": "org-a"},
        ]}, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("AUTH_USERS_FILE", str(f))
    monkeypatch.setenv("AUTH_SIGNING_KEY", KEY)
    auth._reset_for_tests()
    yield
    auth._reset_for_tests()


def bearer(uid):
    return {"Authorization": "Bearer " + auth.make_token(auth._user(uid))["token"]}


# ── 비밀번호 · 토큰 ────────────────────────────────────────────────────────

def test_비밀번호_해시():
    h = auth.hash_password("pw", iterations=1000)
    assert h.startswith("pbkdf2_sha256$1000$") and "pw" not in h
    assert auth.verify_password("pw", h) and not auth.verify_password("pW", h)
    assert not auth.verify_password("pw", "garbage") and not auth.verify_password("pw", "md5$1$a$b")


def test_같은_비밀번호도_해시가_다르다():
    assert auth.hash_password("pw", iterations=1000) != auth.hash_password("pw", iterations=1000)


def test_토큰_왕복과_변조():
    t = auth.make_token(auth._user("u1"))["token"]
    assert auth._decode(t)["sub"] == "u1"
    h, p, s = t.split(".")
    forged = auth._b64(b'{"sub":"admin","role":"admin","exp":9999999999}')
    assert auth._decode(f"{h}.{forged}.{s}") is None           # 내용을 바꾸면 서명이 안 맞는다
    assert auth._decode(t + "x") is None and auth._decode("a.b") is None


def test_alg_none_토큰은_거절():
    none_h = auth._b64(b'{"alg":"none","typ":"JWT"}')
    body = auth._b64(b'{"sub":"admin","exp":9999999999}')
    assert auth._decode(f"{none_h}.{body}.") is None


def test_만료():
    t = auth.make_token(auth._user("u1"), now=time.time() - auth.TOKEN_TTL_SEC - 5)["token"]
    assert auth._decode(t) is None


def test_서명키가_짧거나_없으면_로그인하지_않는다(monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "short")
    r = TestClient(app).post("/v1/auth/login", json={"username": "u1", "password": "u1-pw"})
    assert r.status_code == 503


def test_잘못된_역할은_계정으로_읽지_않는다():
    assert auth._user("x") is None and "x" not in auth.org_members("org-a")


# ── 로그인 ────────────────────────────────────────────────────────────────

def test_로그인_성공과_me():
    c = TestClient(app)
    r = c.post("/v1/auth/login", json={"username": "u1", "password": "u1-pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == {"id": "u1", "name": "사용자1", "role": "user", "org": "org-a", "org_name": "기관 A"}
    assert "password_hash" not in r.text
    me = c.get("/v1/auth/me", headers={"Authorization": "Bearer " + body["token"]})
    assert me.json()["user"]["id"] == "u1"


def test_없는_아이디와_틀린_비밀번호는_같은_응답():
    c = TestClient(app)
    a = c.post("/v1/auth/login", json={"username": "nobody", "password": "x"})
    b = c.post("/v1/auth/login", json={"username": "u1", "password": "x"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_비밀번호를_안_정한_계정은_로그인_못_한다():
    r = TestClient(app).post("/v1/auth/login", json={"username": "u2", "password": ""})
    assert r.status_code == 400
    r = TestClient(app).post("/v1/auth/login", json={"username": "u2", "password": "anything"})
    assert r.status_code == 401


def test_5번_틀리면_잠근다():
    c = TestClient(app)
    for _ in range(auth.MAX_FAILS):
        assert c.post("/v1/auth/login", json={"username": "u1", "password": "x"}).status_code == 401
    # 잠긴 동안은 맞는 비밀번호도 거절
    assert c.post("/v1/auth/login", json={"username": "u1", "password": "u1-pw"}).status_code == 429


@pytest.mark.parametrize("hdr", ["Bearer nope", "Basic abc", "Bearer "])
def test_틀린_토큰은_비로그인이_아니라_401(hdr):
    """만료를 조용히 비로그인으로 바꾸면 화면이 '데이터가 사라졌다'로 보인다."""
    r = TestClient(app).get("/v1/auth/me", headers={"Authorization": hdr})
    assert r.status_code == 401


def test_계정이_지워지면_토큰이_살아_있어도_막는다(monkeypatch, tmp_path):
    h = bearer("u4")
    f = tmp_path / "empty.yaml"
    f.write_text("users: []\n", encoding="utf-8")
    monkeypatch.setenv("AUTH_USERS_FILE", str(f))
    assert TestClient(app).get("/v1/auth/me", headers=h).status_code == 401


# ── 관리자 API가 빠짐없이 막혀 있는가 ─────────────────────────────────────

#: 로그인 없이도 열리는(공개 범위로 거르는) 콘솔 라우트. 여기 없으면 관리자 전용이어야 한다.
PUBLIC_CONSOLE = {
    ("GET", "/v1/console/overview"), ("GET", "/v1/console/datasets"), ("GET", "/v1/console/facets"),
    ("GET", "/v1/console/stats"), ("GET", "/v1/console/search/items"),
    ("GET", "/v1/console/datasets/{dataset_id:path}"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/items"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/graph"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/status"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/trend"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/package"),
    # 외부 반출(결정 7) — 공개 범위로 거른 뒤, 전체 공개 + 재배포 허용일 때만 내보낸다
    ("GET", "/v1/console/datasets/{dataset_id:path}/export/hf"),
    ("GET", "/v1/console/datasets/{dataset_id:path}/export/hf/check"),
    # 아이템 CSV·묶음 패키지(2026-11-11) — 패키지와 같이 공개 범위로 거른다(묶음은 하나라도 못 보면 거부)
    ("GET", "/v1/console/datasets/{dataset_id:path}/items.csv"),
    ("POST", "/v1/console/bundles/package"),
}


def _calls(dep, target):
    if dep.call is target:
        return True
    return any(_calls(d, target) for d in dep.dependencies)


def _console_routes():
    for r in app.routes:
        if getattr(r, "path", "").startswith("/v1/console"):
            for m in r.methods:
                yield m, r.path, r


def test_공개_목록에_없는_콘솔_라우트는_전부_관리자_전용():
    leaks = [(m, p) for m, p, r in _console_routes()
             if (m, p) not in PUBLIC_CONSOLE and not _calls(r.dependant, auth.require_admin)]
    assert not leaks, f"관리자 보호가 빠진 라우트: {leaks}"


def test_공개_라우트는_공개_범위로_거른다():
    """공개 라우트가 사용자를 아예 안 받으면 PRIVATE이 그대로 나간다."""
    missing = [(m, p) for m, p, r in _console_routes()
               if (m, p) in PUBLIC_CONSOLE and p != "/v1/console/overview"
               and not _calls(r.dependant, auth.optional_user)]
    assert not missing, missing


def test_사용자_API는_전부_로그인_필요():
    for r in app.routes:
        if getattr(r, "path", "").startswith("/v1/my"):
            assert _calls(r.dependant, auth.current_user), r.path


@pytest.mark.parametrize("method,path", [
    ("GET", "/v1/console/registry"), ("GET", "/v1/console/errors"),
    ("POST", "/v1/console/datasets"), ("DELETE", "/v1/console/datasets/urn:x?confirm=urn:x"),
    ("POST", "/v1/console/review/relations"),
])
def test_관리자_API_비로그인_401_사용자_403(method, path):
    c = TestClient(app)
    assert c.request(method, path, json={}).status_code == 401
    assert c.request(method, path, json={}, headers=bearer("u1")).status_code == 403


# ── 공개 범위 ─────────────────────────────────────────────────────────────

def test_비로그인은_PUBLIC만():
    sql, params = access.visible_clause(None, "d.")
    assert sql == "d.visibility = 'PUBLIC'" and params == {}


def test_관리자는_전부():
    assert access.visible_clause(auth._user("admin")) == ("TRUE", {})


def test_사용자는_같은_기관과_본인():
    sql, params = access.visible_clause(auth._user("u1"))
    assert "owner_id = %(_v_uid)s" in sql and "owner_id IS NULL" in sql
    assert params["_v_uid"] == "u1"
    # 같은 기관(org-a)만 — 다른 기관(u4)·잘못된 계정(x)은 빠진다
    assert sorted(params["_v_members"]) == ["u1", "u2"]


def test_볼_수_없으면_404():
    class Cur:
        def execute(self, sql, params): self.params = params
        def fetchone(self): return None
    with pytest.raises(Exception) as e:
        access.ensure_visible(Cur(), "urn:x", None)
    assert e.value.status_code == 404
