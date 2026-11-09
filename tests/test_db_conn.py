"""DB 커넥션 — 스레드마다 하나 (NEXT_STEPS §6.2 결정 8-A).

2026-11-04 포털을 붙이다 실측했다. API는 동기 엔드포인트를 스레드풀에서 동시에 돌리는데
커넥션은 프로세스에 하나라, **한 요청의 실패한 SELECT가 같은 순간 다른 요청을
`InFailedSqlTransaction`으로 죽였다.** `commit()`도 남의 쓰기를 함께 확정할 수 있었다.

여기서는 실제 DB 없이 그 두 가지가 다시 생기지 않는 것만 못박는다.
"""

import threading

import psycopg2.extensions as ext
import pytest

import src.database.db as db


class _FakeConn:
    def __init__(self):
        self.closed = 0
        self.status = ext.TRANSACTION_STATUS_IDLE
        self.rollbacks = 0

    def get_transaction_status(self):
        return self.status

    def rollback(self):
        self.rollbacks += 1
        self.status = ext.TRANSACTION_STATUS_IDLE

    def cursor(self):
        conn = self

        class _Cur:
            def execute(self, _sql):
                if conn.status == ext.TRANSACTION_STATUS_INERROR:
                    raise RuntimeError("current transaction is aborted")

            def fetchone(self):
                return (1,)

            def close(self):
                pass

        return _Cur()

    def close(self):
        self.closed = 1


@pytest.fixture
def made(monkeypatch):
    """`_connect`가 만든 가짜 커넥션 목록. 스레드 로컬은 테스트마다 새로 둔다."""
    out = []

    def _connect():
        out.append(_FakeConn())
        return out[-1]

    monkeypatch.setattr(db, "_connect", _connect)
    monkeypatch.setattr(db, "_local", threading.local())
    return out


def _raw(wrapper):
    return object.__getattribute__(wrapper, "_conn")


def _in_thread(fn):
    box = {}
    t = threading.Thread(target=lambda: box.update(v=fn()))
    t.start()
    t.join()
    return box["v"]


def test_같은_스레드는_재사용한다(made):
    assert _raw(db.get_conn()) is _raw(db.get_conn())
    assert len(made) == 1


def test_다른_스레드는_자기_커넥션을_쓴다(made):
    main = _raw(db.get_conn())
    other = _in_thread(lambda: _raw(db.get_conn()))
    assert main is not other and len(made) == 2


def test_한_스레드의_실패가_다른_스레드로_번지지_않는다(made):
    """2026-11-04 사고 그대로 — A가 실패한 트랜잭션을 남긴 채 B가 질의한다."""
    a = _raw(db.get_conn())
    a.status = ext.TRANSACTION_STATUS_INERROR
    b = _in_thread(lambda: _raw(db.get_conn()))
    assert b is not a and b.status == ext.TRANSACTION_STATUS_IDLE
    assert a.status == ext.TRANSACTION_STATUS_INERROR   # 남의 것을 건드리지도 않는다


def test_남은_실패_트랜잭션은_다음_사용_전에_되돌린다(made):
    """재연결 대신 rollback — 같은 스레드의 다음 요청이 앞 요청의 실패를 떠안지 않는다."""
    c = _raw(db.get_conn())
    c.status = ext.TRANSACTION_STATUS_INERROR
    assert _raw(db.get_conn()) is c
    assert c.rollbacks == 1 and len(made) == 1


def test_진행_중_트랜잭션은_건드리지_않는다(made):
    """파이프라인은 한 스레드에서 get_conn()을 여러 번 부르며 쓰기를 모아 커밋한다."""
    c = _raw(db.get_conn())
    c.status = ext.TRANSACTION_STATUS_INTRANS
    db.get_conn()
    assert c.rollbacks == 0 and c.status == ext.TRANSACTION_STATUS_INTRANS


def test_닫힌_커넥션은_다시_연다(made):
    c = _raw(db.get_conn())
    c.closed = 1
    assert _raw(db.get_conn()) is not c and len(made) == 2


def test_API_스레드_수를_제한한다(monkeypatch):
    """스레드 수가 곧 API의 커넥션 상한이다."""
    import anyio
    import anyio.to_thread

    from src.api import main

    monkeypatch.setattr(main, "API_THREADS", 7)

    async def _check():
        async with main._lifespan(main.app):
            return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert anyio.run(_check) == 7
