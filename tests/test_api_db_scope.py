"""요청이 끝나면 그 요청이 연 DB 트랜잭션을 닫는다 (src/api/db_scope.py, 2026-11-11).

라우터를 새로 만들며 `route_class=ReleaseDbRoute`를 빠뜨리면 그 라우터의 요청은 다시
트랜잭션을 연 채 남는다 — 여기서 모든 라우트를 훑어 막는다.
"""

import asyncio
import threading

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api import db_scope
from src.api.main import app


def test_모든_API_라우트가_트랜잭션을_닫는다():
    missing = [f"{sorted(r.methods)} {r.path}" for r in app.routes
               if isinstance(r, APIRoute) and not getattr(r.endpoint, db_scope._MARK, False)]
    assert missing == []


def _app(calls):
    def fake_release(where=""):
        calls.append((threading.get_ident(), where))
        return False

    r = APIRouter(route_class=db_scope.ReleaseDbRoute)

    @r.get("/sync")
    def sync_ep(x: int = 1):
        calls.append((threading.get_ident(), "endpoint"))
        return {"x": x}

    @r.get("/async")
    async def async_ep():
        calls.append((threading.get_ident(), "endpoint"))
        await asyncio.sleep(0)
        return {"ok": True}

    @r.get("/boom")
    def boom():
        calls.append((threading.get_ident(), "endpoint"))
        raise RuntimeError("x")

    a = FastAPI()
    a.include_router(r)
    return a, fake_release


def test_엔드포인트와_같은_스레드에서_닫는다(monkeypatch):
    calls = []
    a, fake = _app(calls)
    monkeypatch.setattr(db_scope, "release_thread_conn", fake)
    c = TestClient(a, raise_server_exceptions=False)
    for path in ("/sync?x=3", "/async", "/boom"):
        calls.clear()
        c.get(path)
        (t_ep, _), (t_rel, where) = calls
        assert t_ep == t_rel, path            # 다른 스레드에서 닫으면 남의 트랜잭션을 되돌린다
        assert where.endswith(("sync_ep", "async_ep", "boom"))
    assert c.get("/sync?x=3").json() == {"x": 3}   # 질의 매개변수(시그니처)가 그대로 살아 있다


def test_include_router가_두_번_감싸지_않는다(monkeypatch):
    calls = []
    a, fake = _app(calls)
    monkeypatch.setattr(db_scope, "release_thread_conn", fake)
    TestClient(a).get("/sync")
    assert len(calls) == 2
