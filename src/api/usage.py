"""활용 기록 — 데이터셋 조회·내려받기 이벤트 (NEXT_STEPS 결정 3, 2026-11-11).

모비젠은 사용자 참여·활용 기록 중 **② 활용 기록만** 먼저 만든다. 계정(①)·사용자 참여(③)는
케이웨어 과업이라, 나중에 얹을 수 있게 둔다(`user_id` 비울 수 있음, 이벤트 유형은 열린 값).

기록 경로
  - 조회(view): 포털이 상세 화면을 열 때 `POST /v1/usage/events`로 보낸다. 서버가 상세 API
    호출마다 세면 화면 재조회(react-query 등)까지 조회로 잡힌다.
  - 내려받기(download): 서버가 직접 기록한다(`record_server_event`) — 패키지·JSON-LD·허깅페이스 형식.

개인정보: IP·User-Agent·검색어는 저장하지 않는다. 비로그인 방문은 포털이 탭마다 만드는 임의
세션 식별자(`X-Usage-Session` 헤더)의 해시만 남긴다. 같은 사람(로그인 ID 또는 세션)이 같은
대상에 같은 이벤트를 30분 안에 다시 보내면 한 번으로 친다.

API 직접 호출(2026-11-11 결정 A안): 로그인·세션 정보 없이 포털 밖에서 API로 내려받으면 누구인지
알 수 없어 중복을 걸러낼 수 없다. 이런 건은 `origin='api'`로 호출마다 1건씩 남기되, 화면에
보이는 활용 수(인기 데이터·상세 활용 수·관리자 요약의 사람 기준 수치)에서는 빼고 관리자 요약의
`api` 항목에만 따로 보여 준다. OpenAPI 활용 실적(호출 건수)으로 쓸 수 있다.

기록은 본 기능을 막지 않는다. 테이블이 아직 없거나(마이그레이션 전) DB 쓰기가 실패해도
내려받기는 그대로 성공하고, 집계 API는 `available: false`로 빈 결과를 준다.
"""

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from psycopg2 import errors as pg_errors

from src.api.access import ensure_visible, visible_clause
from src.api.auth import User, optional_user, require_admin
from src.api.db_scope import ReleaseDbRoute
from src.database.db import get_conn

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["활용 기록"], route_class=ReleaseDbRoute)

TABLE = "dataset_usage_event"

#: 포털(화면)이 보낼 수 있는 이벤트. 내려받기는 서버가 직접 기록하므로 화면에서 받지 않는다
#: (화면이 보내면 실패한 내려받기도 세게 된다).
CLIENT_EVENTS = {"view"}
#: 집계에 쓰는 이벤트 유형(열린 값 — 새 유형은 여기와 기록 지점에 추가)
EVENT_TYPES = {"view", "download"}
DOWNLOAD_DETAILS = {"package", "jsonld", "hf"}
DEDUP_MINUTES = 30
#: 기록 출처 — portal: 화면이 보낸 조회 / server: 서버가 기록한 내려받기(사람 식별됨)
#: / api: 서버가 기록했지만 누구인지 모르는 API 직접 호출(따로 집계)
ORIGIN_PORTAL, ORIGIN_SERVER, ORIGIN_API = "portal", "server", "api"
#: 화면에 보이는 활용 수에 넣는 기록만 고르는 조건
_COUNTED = f"origin <> '{ORIGIN_API}'"
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_MAX_ITEM_ID = 300


def session_hash(raw: Optional[str]) -> Optional[str]:
    """세션 식별자 원문은 저장하지 않는다. 형식이 이상하면 없는 것으로 본다."""
    if not raw or not _SESSION_RE.match(raw):
        return None
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _insert(cur, event_type: str, dataset_id: str, user: Optional[User], sess: Optional[str],
            item_id: Optional[str], detail: Optional[str], origin: str) -> bool:
    """30분 안 같은 (사람, 대상, 이벤트)가 없을 때만 넣는다. 넣었으면 True."""
    uid = user.id if user else None
    who = uid or sess
    cur.execute(
        f"""INSERT INTO {TABLE} (event_type, dataset_id, item_id, detail, user_id, session_hash, origin)
            SELECT %(t)s, %(d)s, %(i)s, %(x)s, %(u)s, %(s)s, %(o)s
            WHERE %(who)s::text IS NULL OR NOT EXISTS (
                SELECT 1 FROM {TABLE}
                WHERE dataset_id = %(d)s AND event_type = %(t)s
                  AND item_id IS NOT DISTINCT FROM %(i)s AND detail IS NOT DISTINCT FROM %(x)s
                  AND coalesce(user_id, session_hash) = %(who)s
                  AND occurred_at > now() - make_interval(mins => %(m)s))
            RETURNING id""",
        {"t": event_type, "d": dataset_id, "i": item_id, "x": detail, "u": uid, "s": sess,
         "o": origin, "who": who, "m": DEDUP_MINUTES})
    return cur.fetchone() is not None


def record_server_event(event_type: str, dataset_id: str, user: Optional[User],
                        session_raw: Optional[str] = None, detail: Optional[str] = None) -> None:
    """서버가 직접 남기는 기록(내려받기 등). **실패해도 예외를 내지 않는다** — 본 기능이 우선이다.

    로그인·세션 둘 다 없으면 API 직접 호출로 보고 `origin='api'`로 남긴다(중복 제거 없음, 따로 집계).

    호출 전에 같은 스레드 커넥션에 커밋하지 않은 쓰기가 없어야 한다(여기서 commit한다).
    지금 호출부(패키지·JSON-LD 내려받기)는 읽기만 한다.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        sess = session_hash(session_raw)
        origin = ORIGIN_SERVER if (user is not None or sess is not None) else ORIGIN_API
        _insert(cur, event_type, dataset_id, user, sess, None, detail, origin)
        conn.commit()
    except Exception as e:                                   # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                                    # noqa: BLE001
            pass
        log.warning("활용 기록을 남기지 못했습니다 (%s %s): %s", event_type, dataset_id, type(e).__name__)


@router.post("/usage/events")
def post_event(body: Dict[str, Any] = Body(...),
               user: Optional[User] = Depends(optional_user),
               x_usage_session: Optional[str] = Header(None)):
    """화면에서 일어난 활용 이벤트를 기록합니다. 지금은 상세 조회(`view`)만 받습니다."""
    event_type = body.get("event_type")
    dataset_id = body.get("dataset_id")
    item_id = body.get("item_id")
    if event_type not in CLIENT_EVENTS:
        raise HTTPException(400, f"기록할 수 있는 이벤트는 {sorted(CLIENT_EVENTS)}입니다")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise HTTPException(400, "데이터셋 ID를 보내 주세요")
    if item_id is not None and (not isinstance(item_id, str) or len(item_id) > _MAX_ITEM_ID):
        raise HTTPException(400, "아이템 ID 형식이 올바르지 않습니다")
    sess = session_hash(x_usage_session)
    if user is None and sess is None:
        # 누구인지(로그인·세션) 모르면 중복을 걸러낼 수 없다 — 세지 않는다
        return {"recorded": False, "reason": "세션 정보가 없어 기록하지 않았습니다"}

    conn = get_conn()
    cur = conn.cursor()
    ensure_visible(cur, dataset_id, user)
    try:
        recorded = _insert(cur, event_type, dataset_id, user, sess, item_id, None, ORIGIN_PORTAL)
        conn.commit()
    except pg_errors.UndefinedTable:
        conn.rollback()
        return {"recorded": False, "reason": "활용 기록 기능이 아직 준비되지 않았습니다"}
    except Exception:
        conn.rollback()
        raise
    return {"recorded": recorded}


def _unavailable(extra: Dict[str, Any]) -> Dict[str, Any]:
    return {"available": False, "note": "활용 기록 기능이 아직 준비되지 않았습니다", **extra}


def _query(sql: str, params: Dict[str, Any]) -> Optional[List[tuple]]:
    """테이블이 없으면 None."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    except pg_errors.UndefinedTable:
        conn.rollback()
        return None


@router.get("/usage/popular")
def popular(days: int = Query(30, ge=1, le=365), limit: int = Query(10, ge=1, le=50),
            event_type: str = Query("view"), user: Optional[User] = Depends(optional_user)):
    """많이 본(또는 많이 내려받은) 데이터셋. 볼 수 있는 데이터셋만 나옵니다.

    `users`는 서로 다른 사람 수(로그인 ID 또는 브라우저 세션 기준)입니다.
    누구인지 모르는 API 직접 호출은 넣지 않습니다.
    """
    if event_type not in EVENT_TYPES:
        raise HTTPException(400, f"이벤트 유형은 {sorted(EVENT_TYPES)} 중 하나여야 합니다")
    cond, params = visible_clause(user, "d.")
    rows = _query(
        f"""SELECT d.dataset_id, d.title, d.source_type, d.publisher,
                   count(*) AS events, count(DISTINCT coalesce(e.user_id, e.session_hash)) AS users
            FROM {TABLE} e JOIN dcat_dataset d ON d.dataset_id = e.dataset_id
            WHERE e.event_type = %(t)s AND e.occurred_at > now() - make_interval(days => %(days)s)
              AND e.{_COUNTED} AND {cond}
            GROUP BY d.dataset_id, d.title, d.source_type, d.publisher
            ORDER BY users DESC, events DESC, d.dataset_id
            LIMIT %(limit)s""",
        {**params, "t": event_type, "days": days, "limit": limit})
    if rows is None:
        return _unavailable({"items": [], "days": days, "event_type": event_type})
    items = [{"dataset_id": r[0], "title": r[1], "source_type": r[2], "publisher": r[3],
              "events": r[4], "users": r[5]} for r in rows]
    return {"available": True, "days": days, "event_type": event_type, "items": items}


@router.get("/usage/datasets/{dataset_id:path}")
def dataset_usage(dataset_id: str, days: int = Query(30, ge=1, le=365),
                  user: Optional[User] = Depends(optional_user)):
    """한 데이터셋의 활용 현황 — 전체·최근 기간 조회·내려받기 수와 일별 추이.

    누구인지 모르는 API 직접 호출은 넣지 않습니다.
    """
    ensure_visible(get_conn().cursor(), dataset_id, user)
    totals = _query(
        f"""SELECT event_type, count(*),
                   count(*) FILTER (WHERE occurred_at > now() - make_interval(days => %(days)s))
            FROM {TABLE} WHERE dataset_id = %(d)s AND {_COUNTED} GROUP BY event_type""",
        {"d": dataset_id, "days": days})
    if totals is None:
        return _unavailable({"dataset_id": dataset_id, "days": days,
                             "total": {}, "recent": {}, "daily": []})
    daily = _query(
        f"""SELECT (occurred_at AT TIME ZONE 'Asia/Seoul')::date AS day, event_type, count(*)
            FROM {TABLE}
            WHERE dataset_id = %(d)s AND occurred_at > now() - make_interval(days => %(days)s)
              AND {_COUNTED}
            GROUP BY 1, 2 ORDER BY 1""",
        {"d": dataset_id, "days": days}) or []
    return {
        "available": True, "dataset_id": dataset_id, "days": days,
        "total": {t: n for t, n, _ in totals},
        "recent": {t: r for t, _, r in totals},
        "daily": [{"day": d.isoformat(), "event_type": t, "count": n} for d, t, n in daily],
    }


#: '함께 본 데이터'로 보여 줄 최소 인원. 1명이면 그 사람의 조회 이력이 그대로 드러난다
CO_VIEW_MIN_PEOPLE = 2
CO_VIEW_DAYS = 90


def co_viewed(dataset_id: str, user: Optional[User] = None, days: int = CO_VIEW_DAYS,
              limit: int = 6, min_people: int = CO_VIEW_MIN_PEOPLE) -> Optional[List[Dict[str, Any]]]:
    """이 데이터셋을 본 사람들이 함께 본 데이터셋 — [{dataset_id, title, people}]. 테이블이 없으면 None.

    사람 = 로그인 ID 또는 브라우저 세션. API 직접 호출(누구인지 모름)은 넣지 않는다.
    서로 다른 사람이 `min_people`명 이상일 때만 — 한 사람의 이력이 추천으로 드러나지 않게 한다.
    """
    cond, params = visible_clause(user, "d.")
    sql = f"""WITH viewers AS (
                SELECT DISTINCT coalesce(user_id, session_hash) AS who FROM {TABLE}
                WHERE dataset_id = %(d)s AND event_type = 'view' AND {_COUNTED}
                  AND occurred_at > now() - make_interval(days => %(days)s))
              SELECT e.dataset_id, d.title, count(DISTINCT coalesce(e.user_id, e.session_hash)) AS people
              FROM {TABLE} e
              JOIN viewers v ON coalesce(e.user_id, e.session_hash) = v.who
              JOIN dcat_dataset d ON d.dataset_id = e.dataset_id
              WHERE e.dataset_id <> %(d)s AND e.event_type = 'view' AND e.{_COUNTED}
                AND e.occurred_at > now() - make_interval(days => %(days)s) AND {cond}
              GROUP BY e.dataset_id, d.title
              HAVING count(DISTINCT coalesce(e.user_id, e.session_hash)) >= %(minp)s
              ORDER BY people DESC, e.dataset_id
              LIMIT %(lim)s"""
    args = {**params, "d": dataset_id, "days": days, "minp": min_people, "lim": limit}
    rows = _query(sql, args)
    if rows is None:
        return None
    return [{"dataset_id": i, "title": t, "people": n} for i, t, n in rows]


@router.get("/usage/also-viewed/{dataset_id:path}")
def also_viewed(dataset_id: str, days: int = Query(CO_VIEW_DAYS, ge=7, le=365),
                limit: int = Query(6, ge=1, le=20), user: Optional[User] = Depends(optional_user)):
    """이 데이터셋을 본 사람들이 함께 본 데이터셋(서로 다른 사람 2명 이상일 때만). 볼 수 있는 것만 나옵니다."""
    ensure_visible(get_conn().cursor(), dataset_id, user)
    items = co_viewed(dataset_id, user, days, limit)
    if items is None:
        return _unavailable({"dataset_id": dataset_id, "items": []})
    return {"available": True, "dataset_id": dataset_id, "days": days,
            "min_people": CO_VIEW_MIN_PEOPLE, "items": items}


@router.get("/console/usage/summary", dependencies=[Depends(require_admin)])
def summary(days: int = Query(30, ge=1, le=365)):
    """관리자용 활용 현황 — 유형별 합계, 일별 추이, 상위 데이터셋, 로그인·비로그인 비율.

    위 수치는 사람이 식별된 기록만 셉니다. 누구인지 모르는 API 직접 호출은 `api`에 따로
    호출 건수(중복 제거 없음)로 보여 줍니다.
    """
    p = {"days": days}
    w = f"occurred_at > now() - make_interval(days => %(days)s) AND {_COUNTED}"
    by_type = _query(
        f"""SELECT event_type, coalesce(detail, ''), count(*),
                   count(DISTINCT coalesce(user_id, session_hash))
            FROM {TABLE} WHERE {w}
            GROUP BY 1, 2 ORDER BY 1, 2""", p)
    if by_type is None:
        return _unavailable({"days": days, "by_type": [], "daily": [], "top": [], "visitors": {},
                             "api": {"events": 0, "datasets": 0, "by_detail": []}})
    daily = _query(
        f"""SELECT (occurred_at AT TIME ZONE 'Asia/Seoul')::date, event_type, count(*)
            FROM {TABLE} WHERE {w}
            GROUP BY 1, 2 ORDER BY 1""", p) or []
    top = _query(
        f"""SELECT e.dataset_id, d.title, d.visibility,
                   count(*) FILTER (WHERE e.event_type = 'view'),
                   count(*) FILTER (WHERE e.event_type = 'download')
            FROM {TABLE} e JOIN dcat_dataset d ON d.dataset_id = e.dataset_id
            WHERE e.occurred_at > now() - make_interval(days => %(days)s) AND e.{_COUNTED}
            GROUP BY 1, 2, 3 ORDER BY 4 DESC, 5 DESC, 1 LIMIT 20""", p) or []
    visitors = _query(
        f"""SELECT count(DISTINCT user_id), count(DISTINCT session_hash) FILTER (WHERE user_id IS NULL)
            FROM {TABLE} WHERE {w}""", p) or [(0, 0)]
    api = _query(
        f"""SELECT coalesce(detail, ''), count(*) FROM {TABLE}
            WHERE occurred_at > now() - make_interval(days => %(days)s) AND origin = '{ORIGIN_API}'
            GROUP BY 1 ORDER BY 2 DESC, 1""", p) or []
    return {
        "available": True, "days": days,
        "by_type": [{"event_type": t, "detail": x or None, "events": n, "users": u} for t, x, n, u in by_type],
        "daily": [{"day": d.isoformat(), "event_type": t, "count": n} for d, t, n in daily],
        "top": [{"dataset_id": i, "title": t, "visibility": v, "views": a, "downloads": b}
                for i, t, v, a, b in top],
        "visitors": {"logged_in": visitors[0][0], "anonymous_sessions": visitors[0][1]},
        "api": {
            "events": sum(n for _, n in api),
            "datasets": _api_datasets(p),
            "by_detail": [{"detail": x or None, "events": n} for x, n in api],
        },
    }


def _api_datasets(p: Dict[str, Any]) -> int:
    """API 직접 호출로 내려받은 서로 다른 데이터셋 수(형식별로 나누면 겹쳐 세므로 따로 센다)."""
    rows = _query(
        f"""SELECT count(DISTINCT dataset_id) FROM {TABLE}
            WHERE occurred_at > now() - make_interval(days => %(days)s) AND origin = '{ORIGIN_API}'""", p)
    return rows[0][0] if rows else 0
