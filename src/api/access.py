"""공개 범위(visibility) 판정 — 누가 어떤 데이터셋을 보는가. 한 곳에서만 정한다.

| 공개 범위 | 비로그인 | 사용자 | 관리자 |
|---|---|---|---|
| PUBLIC  | 본다 | 본다 | 본다 |
| ORG     | 못 본다 | 등록자와 **같은 기관**이면 본다. 등록자가 없는(관리자 등록) ORG는 로그인한 사용자 모두 | 본다 |
| PRIVATE | 못 본다 | **등록자 본인만** | 본다 |

- 관리자 등록분(owner 없음)의 ORG는 "운영기관이 참여기관에 공유하는 데이터"로 본다.
  참여기관별로 나눌 근거(publisher ↔ 기관 매핑)가 아직 없다.
- 볼 수 없는 데이터셋을 직접 열면 **404** — 403이면 "있긴 하다"가 드러난다.
- 검색 결과처럼 여러 건을 돌려줄 때는 걸러서 뺀다.

SQL은 이름 붙은 파라미터(`%(…)s`)로 만든다. 붙일 쿼리도 같은 방식이어야 한다.
"""

from typing import Any, Dict, Iterable, Optional, Set, Tuple

from fastapi import HTTPException

from src.api.auth import User, org_members


def visible_clause(user: Optional[User], alias: str = "") -> Tuple[str, Dict[str, Any]]:
    """WHERE에 넣을 조건과 파라미터. `alias`는 'd.'처럼 점까지."""
    a = alias
    if user is not None and user.is_admin:
        return "TRUE", {}
    if user is None:
        return f"{a}visibility = 'PUBLIC'", {}
    sql = (f"({a}visibility = 'PUBLIC' OR {a}owner_id = %(_v_uid)s "
           f"OR ({a}visibility = 'ORG' AND ({a}owner_id IS NULL OR {a}owner_id = ANY(%(_v_members)s))))")
    return sql, {"_v_uid": user.id, "_v_members": org_members(user.org) or [user.id]}


def ensure_visible(cur, dataset_id: str, user: Optional[User]) -> None:
    """볼 수 없으면 404(없는 것과 같은 응답)."""
    cond, params = visible_clause(user)
    cur.execute(f"SELECT 1 FROM dcat_dataset WHERE dataset_id = %(_id)s AND {cond}",
                {**params, "_id": dataset_id})
    if cur.fetchone() is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")


def visible_ids(cur, ids: Iterable[str], user: Optional[User]) -> Set[str]:
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return set()
    if user is not None and user.is_admin:
        return set(ids)
    cond, params = visible_clause(user)
    cur.execute(f"SELECT dataset_id FROM dcat_dataset WHERE dataset_id = ANY(%(_ids)s) AND {cond}",
                {**params, "_ids": ids})
    return {r[0] for r in cur.fetchall()}


#: 아이템 검색 결과 → 데이터셋. hybrid.SOURCES의 원본 테이블과 같다
_ITEM_TABLE = {"video": "meta_video", "news": "meta_news", "blog": "meta_blog"}


def item_dataset_map(cur, source: str, item_ids: Iterable[Any]) -> Dict[Any, str]:
    """아이템 id → dataset_id. source='dataset'이면 id가 곧 dataset_id다."""
    item_ids = list(item_ids)
    if source == "dataset":
        return {i: i for i in item_ids}
    table = _ITEM_TABLE.get(source)
    if not table or not item_ids:
        return {}
    cur.execute(f"SELECT id, dataset_id FROM {table} WHERE id = ANY(%(_ids)s)", {"_ids": item_ids})
    return dict(cur.fetchall())
