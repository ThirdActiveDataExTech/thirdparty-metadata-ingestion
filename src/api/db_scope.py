"""요청이 끝나면 그 요청이 연 DB 트랜잭션을 닫는다 (2026-11-11).

왜: DB 커넥션은 작업 스레드마다 하나를 재사용한다(src/database/db.py). autocommit이
아니어서 SELECT만 한 요청도 트랜잭션을 열고 끝나는데, 아무도 닫지 않아 커넥션이
`idle in transaction`으로 남았다. 그 결과
  - 새로 만든 색인을 API 재시작 전까지 못 썼고(2026-11-11 HNSW 적용 때 실측),
  - VACUUM이 오래된 행을 못 치우고, `CREATE INDEX CONCURRENTLY`가 막힌다.

어떻게: 라우트 클래스가 엔드포인트 함수를 감싸, 함수가 끝나면 **같은 스레드에서**
`release_thread_conn()`을 부른다. 동기 엔드포인트는 스레드풀 작업 스레드에서, async
엔드포인트는 이벤트 루프 스레드에서 돈다 — 어느 쪽이든 그 스레드의 커넥션을 닫는다.
미들웨어로 하지 않는 이유: 미들웨어는 이벤트 루프 스레드에서 돌아, 그 사이 같은 작업
스레드가 다음 요청의 쓰기를 진행 중일 수 있다(남의 트랜잭션을 되돌리게 된다).

쓰기 경로는 지금처럼 엔드포인트 안에서 commit/rollback한다 — 여러 쿼리를 한 묶음으로
확정하는 곳(삭제, 분류 확정 + 이력)의 동작은 바뀌지 않는다.

모든 라우터는 `APIRouter(..., route_class=ReleaseDbRoute)`로 만든다.
"""

import functools
import inspect

from fastapi.routing import APIRoute

from src.database.db import release_thread_conn

_MARK = "__releases_db__"


def _wrap(fn):
    if getattr(fn, _MARK, False):          # include_router가 같은 함수로 라우트를 다시 만든다
        return fn
    where = f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', '?')}"

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            finally:
                release_thread_conn(where)
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            finally:
                release_thread_conn(where)

    setattr(wrapper, _MARK, True)
    return wrapper


class ReleaseDbRoute(APIRoute):
    """엔드포인트가 끝나면 그 스레드의 열린 DB 트랜잭션을 닫는 라우트."""

    def __init__(self, path, endpoint, **kwargs):
        super().__init__(path, _wrap(endpoint), **kwargs)
