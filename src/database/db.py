"""PostgreSQL 커넥션 — 스레드당 1개 재사용 (2026-07-28 프로세스당 → 2026-11-09 스레드당).

기존엔 호출부(`database/*.py`, 파이프라인)가 함수 호출마다 `get_conn()`으로 새
커넥션을 열고 즉시 닫아서, 원격 DB(TCP+인증 왕복)에 쿼리 수만큼 반복 접속하는
비용이 컸다(예: YouTube 1400개+ 채널 재실행 ~5분). 그래서 커넥션을
지연 생성해 재사용한다.

- `get_conn()` 호출마다 가볍게 살아있는지 확인(`SELECT 1`) 후, 죽어있으면
  재연결한다 — STT 처리처럼 쿼리 사이 유휴 시간이 길 때(수십 초~몇 분) 네트워크나
  DB 서버가 유휴 커넥션을 끊을 수 있어서 필요. `.closed` 속성만으로는 이런
  서버 쪽 끊김을 못 잡는다(로컬에서 직접 닫은 경우만 반영됨).
- 호출부 코드(`conn = get_conn(); ...; conn.close()`)는 전혀 안 바뀐다 — `close()`는
  실제로 커넥션을 닫지 않고, 트랜잭션이 남아있으면 rollback만 해서 다음 재사용을
  위해 정리한다.

**스레드마다 커넥션 1개** (2026-11-09, NEXT_STEPS §6.2 결정 8-A). 예전엔 프로세스
전체가 커넥션 1개를 나눠 썼는데, API(FastAPI)는 동기 엔드포인트를 스레드풀에서
동시에 돌려서 **요청들이 한 트랜잭션을 공유**했다 — 한 요청의 실패한 SELECT가 다른
요청을 `InFailedSqlTransaction`으로 죽였고(2026-11-04 실측), `commit()`은 남의 쓰기까지
함께 확정할 수 있었다. psycopg2 커넥션은 스레드 세이프하지 않다.

- 같은 스레드 안에서는 지금처럼 하나를 재사용한다 → 파이프라인(단일 스레드)은 동작이 같다.
- 요청 단위 풀(`ThreadedConnectionPool`)이 아닌 이유: API 호출부 35곳이 `close()`로
  반납하지 않는다. 풀로 바꾸면 그 35곳을 다 고쳐야 하고, 하나라도 빠지면 연결이 샌다.
- 커넥션 수 = 동시에 DB를 쓰는 스레드 수. API는 스레드 수를 제한한다(`main.py` API_THREADS).
  스레드가 사라지면 그 스레드의 커넥션도 GC로 닫힌다(anyio는 다음 요청이 올 때 10초 넘게 쉰
  작업 스레드를 정리한다 — 2026-11-09 실측: 동시 40·540요청 내내 API 커넥션 ≤ 10, 정리 후 1).
- Airflow가 한 프로세스 안에서 태스크를 스레드로 동시 실행해도 같은 이유로 안전하다.
"""

import logging
import threading

import psycopg2
import psycopg2.extensions
from src.common import config

_local = threading.local()
log = logging.getLogger(__name__)


class _ReusableConnection:
    """get_conn()이 반환하는 래퍼 — close()가 실제로 닫지 않고 트랜잭션만 정리한다."""

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def close(self):
        conn = object.__getattribute__(self, "_conn")
        try:
            if conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                conn.rollback()
        except Exception:
            pass


def _connect():
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )


def _is_alive(conn) -> bool:
    """살아 있는지 `SELECT 1`로 확인한다. 확인 때문에 트랜잭션을 새로 열어 두지 않는다.

    autocommit이 아니라 `SELECT 1`도 트랜잭션을 연다. 예전엔 그대로 둬서, 이후 아무도
    커밋·롤백하지 않으면 커넥션이 `idle in transaction`으로 남았다(2026-11-11 실측 —
    새 색인을 못 보고, VACUUM·`CREATE INDEX CONCURRENTLY`를 막는다). 확인 전에 쉬고
    있던(IDLE) 커넥션만 되돌린다 — 진행 중 트랜잭션은 바깥 호출부의 것이다.
    """
    try:
        was_idle = conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_IDLE
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        if was_idle and conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            conn.rollback()
        return True
    except Exception:
        return False


def _discard_failed(conn) -> None:
    """앞선 작업이 실패한 트랜잭션을 남겼으면 되돌린다.

    실패한 트랜잭션은 rollback 전까지 모든 질의를 거부한다 — 그대로 두면 이 스레드의
    다음 요청이 남의 실패를 떠안는다. 진행 중(INTRANS) 트랜잭션은 건드리지 않는다:
    같은 스레드의 바깥 호출부가 아직 커밋 전인 쓰기를 들고 있을 수 있다.
    """
    try:
        if conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
            conn.rollback()
    except Exception:
        pass


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is not None and not conn.closed:
        _discard_failed(conn)
    if conn is None or conn.closed or not _is_alive(conn):
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn = _local.conn = _connect()
    return _ReusableConnection(conn)


def release_thread_conn(where: str = "") -> bool:
    """이 스레드의 커넥션에 열린 트랜잭션이 남아 있으면 롤백해 닫는다.

    API는 요청(엔드포인트) 하나가 끝날 때마다 **같은 작업 스레드에서** 이걸 부른다
    (`src/api/db_scope.py`). 읽기만 한 요청은 트랜잭션을 연 채 끝나는데, 다음 요청이
    올 때까지 `idle in transaction`으로 남아 새 색인을 못 보고 VACUUM을 막았다.
    쓰기 경로는 엔드포인트 안에서 직접 commit하므로 여기 올 때는 이미 IDLE이다.

    커밋하지 않은 쓰기가 남아 있으면 버그다 — 경고를 남기고 되돌린다(예전엔 같은
    스레드의 다음 요청 commit에 섞여 확정될 수 있었다). 그런 경우 True를 돌려준다.
    """
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        return False
    try:
        status = conn.get_transaction_status()
        if status == psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            return False
        dirty = False
        if status == psycopg2.extensions.TRANSACTION_STATUS_INTRANS:
            cur = conn.cursor()
            cur.execute("SELECT txid_current_if_assigned()")   # 쓰기를 했으면 xid가 붙어 있다
            dirty = cur.fetchone()[0] is not None
            cur.close()
        conn.rollback()
        if dirty:
            log.warning("커밋하지 않은 쓰기를 되돌렸습니다 (%s) — 호출부에서 commit이 빠졌습니다", where or "?")
        return dirty
    except Exception:                                  # noqa: BLE001 — 끊긴 커넥션은 다음 get_conn이 다시 연다
        try:
            conn.rollback()
        except Exception:                              # noqa: BLE001
            pass
        return False
