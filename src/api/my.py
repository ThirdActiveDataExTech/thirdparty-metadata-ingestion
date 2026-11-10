"""사용자 API — 내가 등록한 데이터셋 (NEXT_STEPS 결정 13·14, 2026-11-09 사용자 등록 흐름).

관리자 API(`/v1/console/*`, manage.py)와 다른 점은 **누가 하느냐**뿐이다. 등록 로직은
`manage.register_as`를 그대로 쓴다 — 따로 구현하면 관리자 등록과 사용자 등록의 결과가
조용히 달라진다.

## 흐름

1. 등록 화면: 제목·설명·키워드를 넣으면 `POST /category-suggest`가 추천 상위 5를 준다.
   고르거나 건너뛰고, 공개 범위(PUBLIC/ORG/PRIVATE)를 골라 `POST /datasets`.
   고른 분류와 **그때 보여 준 추천 목록**이 확정 이력에 남는다(ADR-020 §4).
2. 첫 수집 뒤 파이프라인이 추천을 다시 계산한다(`category.sync_category`).
3. "내가 등록한 데이터"(`GET /datasets`): 수집 현황 + 실패 시 쉬운 안내 + 분류 상태
   (`needs_review` 미확정 / `changed` 추천이 바뀜 / `confirmed`).
4. `PUT /datasets/{id}/category`로 유지 또는 변경 — 이것도 이력에 남는다.

## 사용자 식별

시제품 로그인 토큰(`src/api/auth.py`, ADR-021)의 사용자다. 2026-11-10 전에는 `X-User-Id` 헤더를
그대로 믿었다 — 헤더만 바꾸면 남의 데이터셋을 고칠 수 있었다. K4 인증이 오면 auth.py만 바뀐다.

## 사용자에게 보이지 않는 것

- 원문 오류(내부 주소·호스트가 섞인다) → `error_kind.for_user`의 안내 문구만
- 자격증명 값 — 저장 여부(종류 이름)만
- 확정 이력의 다른 사용자 ID — 자기 데이터셋 것만 본다
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api import manage
from src.api.auth import User, current_user as _current_user
from src.common.category_taxonomy import DECISION_FEATURE
from src.common.error_kind import for_user
from src.database.db import get_conn

router = APIRouter(prefix="/v1/my", tags=["내 데이터 (사용자)"])

#: 원천 약관상 외부 반출(HF·외부 LLM 내보내기)이 안 되는 원천(결정 7).
#: 지금 사용자가 등록할 수 있는 원천은 전부 여기에 든다.
NO_EXPORT = {
    "video": "YouTube 약관상 제3자 제공은 Google 사전 승인이 필요합니다",
    "news": "네이버 검색 API 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "blog": "네이버 검색 API 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "shopping_insight": "네이버 데이터랩 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "persona_insight": "네이버 데이터랩 약관상 외부 배포·상업적 재판매가 금지됩니다",
}

#: 예정이 이만큼 지나도 안 돌았으면 '지연'으로 보여 준다(관리자 오류 화면과 같은 기준)
OVERDUE_HOURS = 1


def current_user(user: User = Depends(_current_user)) -> str:
    """로그인한 사용자 ID. 관리자도 '내 데이터'는 자기 것만 본다(owner_id 기준)."""
    return user.id


def _own(cur, dataset_id: str, uid: str) -> List[str]:
    """내 데이터셋인지 확인하고 현재 분류를 돌려준다. 남의 것이면 403, 없으면 404."""
    cur.execute("SELECT owner_id, category FROM dcat_dataset WHERE dataset_id=%s", (dataset_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, f"없는 데이터셋: {dataset_id}")
    if row[0] != uid:
        raise HTTPException(403, "내가 등록한 데이터셋만 바꿀 수 있다")
    return row[1] or []


# ── 등록 ──────────────────────────────────────────────────────────────────

@router.post("/category-suggest")
def category_suggest(body: Dict[str, Any] = Body(...), uid: str = Depends(current_user)):
    """등록 **전** 분류 추천 상위 5. 아무것도 쓰지 않는다.

    ⚠️ 점수가 0.8대에 몰려 순위 차이가 잡음 수준이다(ADR-020). 화면은 점수를 강조하지 않고
    '고르거나 건너뛰기'로 보여 준다.
    """
    title = (body.get("title") or "").strip()
    desc = (body.get("description") or "").strip()
    if not title and not desc:
        raise HTTPException(400, "제목이나 설명을 먼저 넣어야 추천할 수 있다")
    from src.database.category import suggest_for_text
    return {"suggestions": suggest_for_text(title, desc, manage._clean_list(body.get("keywords"))),
            "note": "추천일 뿐입니다. 맞는 것이 없으면 건너뛰세요 — 틀린 분류는 빈 분류보다 나쁩니다"}


@router.post("/datasets/check")
def check(body: Dict[str, Any] = Body(...), uid: str = Depends(current_user)):
    """등록 전 확인(입력 해석·중복). 관리자 화면과 같은 검사지만 **남의 데이터셋 제목은 가린다**
    — 다른 사용자의 PRIVATE 데이터셋 제목이 중복 경고로 새어 나가면 안 된다."""
    out = manage.check_registration(body)
    out["duplicates"] = _mask_duplicates(out["duplicates"], uid)
    return out


def _mask_duplicates(dups: List[Dict[str, Any]], uid: str) -> List[Dict[str, Any]]:
    if not dups:
        return []
    cur = get_conn().cursor()
    cur.execute("SELECT dataset_id, owner_id FROM dcat_dataset WHERE dataset_id = ANY(%s)",
                ([d["dataset_id"] for d in dups],))
    owner = dict(cur.fetchall())
    return [d if owner.get(d["dataset_id"]) == uid
            else {"dataset_id": None, "title": "다른 사용자 또는 관리자가 등록한 데이터셋", "mine": False}
            for d in dups]


@router.post("/datasets")
def register(body: Dict[str, Any] = Body(...), uid: str = Depends(current_user)):
    """사용자 등록 — `dataset_origin='user'`, `owner_id`=나. 공개 범위 기본은 ORG."""
    out = manage.register_as(body, origin="user", owner_id=uid)
    out["export_note"] = NO_EXPORT.get(body.get("source_type"))
    return out


# ── 내가 등록한 데이터 ────────────────────────────────────────────────────

def _collection_state(r: Dict[str, Any]) -> str:
    if r["reg_status"] == "error":
        return "error"
    if r["last_collected_at"] is None:
        return "waiting"            # 등록만 되고 아직 한 번도 안 돌았다
    if r["overdue"]:
        return "overdue"
    return "ok"


def _category_state(current: List[str], suggestions: List[Dict[str, Any]],
                    last: Optional[Dict[str, Any]]) -> str:
    """미확정 / 추천이 바뀜 / 확정.

    '바뀜'은 **마지막으로 확정할 때 보여 준 추천 상위 3**과 지금 추천 상위 3이 다를 때다.
    첫 수집 뒤 수집된 글까지 반영돼 추천이 달라지는 경우가 대표적이다. 순서만 바뀐 것은
    알리지 않는다(점수 차가 잡음 수준이라 순서는 의미가 없다).
    """
    now_top = {s.get("category") for s in suggestions[:3] if isinstance(s, dict)}
    if not current:
        return "needs_review"
    if last and now_top and set((last.get("shown") or [])[:3]) != now_top:
        return "changed"
    return "confirmed"


@router.get("/datasets")
def my_datasets(uid: str = Depends(current_user)):
    """내가 등록한 데이터셋 — 수집 현황·실패 안내·분류 상태."""
    cur = get_conn().cursor()
    cur.execute(
        """SELECT d.dataset_id, d.title, d.source_type, d.visibility, d.category,
                  d.accrual_periodicity, r.registered_at,
                  r.status AS reg_status, r.item_count, r.row_count,
                  r.last_collected_at, r.next_collect_at, r.last_error,
                  (r.status IN ('active','pending') AND r.next_collect_at
                       < now() - make_interval(hours => %s)) AS overdue,
                  sug.value AS suggestions, dec.value AS decisions,
                  lr.status AS last_run_status, lr.ended_at AS last_run_at, lr.rows_affected AS last_run_rows,
                  (SELECT array_agg(credential_type ORDER BY credential_type)
                     FROM dataset_credentials c WHERE c.dataset_id = d.dataset_id) AS own_keys
           FROM dcat_dataset d
           LEFT JOIN data_registry r USING (dataset_id)
           LEFT JOIN meta_feature sug ON sug.dataset_id = d.dataset_id AND sug.scope='dataset'
                AND sug.target='' AND sug.feature_name='suggested_category'
           LEFT JOIN meta_feature dec ON dec.dataset_id = d.dataset_id AND dec.scope='dataset'
                AND dec.target='' AND dec.feature_name=%s
           LEFT JOIN LATERAL (
               SELECT status, ended_at, rows_affected FROM dcat_provenance p
               WHERE p.dataset_id = d.dataset_id ORDER BY started_at DESC LIMIT 1) lr ON true
           WHERE d.owner_id = %s
           ORDER BY r.registered_at DESC NULLS LAST, d.dataset_id""",
        (OVERDUE_HOURS, DECISION_FEATURE, uid))
    names = [c[0] for c in cur.description]
    items = []
    for row in cur.fetchall():
        r = dict(zip(names, row))
        sugg = r.pop("suggestions") or []
        decisions = r.pop("decisions") or []
        last = decisions[-1] if decisions else None
        state = _collection_state(r)
        err = for_user(r.pop("last_error")) if state == "error" else None
        items.append({
            **{k: r[k] for k in ("dataset_id", "title", "source_type", "visibility",
                                 "accrual_periodicity", "registered_at", "item_count", "row_count",
                                 "last_collected_at", "next_collect_at",
                                 "last_run_status", "last_run_at", "last_run_rows")},
            "collection_state": state,
            # 실패면 다음 수집 예정이 곧 자동 재시도 시각이다(실패 시 +1시간, ADR-008)
            "error": {**err, "retry_at": r["next_collect_at"]} if err else None,
            "category": r["category"] or [],
            "category_state": _category_state(r["category"] or [], sugg, last),
            "suggestions": sugg[:5],
            "last_decision": {k: last.get(k) for k in ("at", "chosen", "shown")} if last else None,
            "own_keys": r["own_keys"] or [],
            "export_note": NO_EXPORT.get(r["source_type"]),
        })
    counts = {s: sum(1 for i in items if i["collection_state"] == s)
              for s in ("ok", "waiting", "overdue", "error")}
    counts["needs_category"] = sum(1 for i in items if i["category_state"] != "confirmed")
    return {"user": uid, "total": len(items), "counts": counts, "items": items}


@router.put("/datasets/{dataset_id:path}/category")
def confirm_category(dataset_id: str, body: Dict[str, Any] = Body(...), uid: str = Depends(current_user)):
    """분류 확정 — 추천을 고르거나, 추천 밖 값을 고르거나, 지금 값을 유지한다.

    `{"keep": true}`면 지금 값을 그대로 다시 확정한다("추천이 바뀌었습니다"를 닫는 동작).
    어느 쪽이든 **그때 보여 준 추천과 고른 값**이 이력에 남는다.
    """
    from src.database.category import record_decision
    conn = get_conn()
    cur = conn.cursor()
    prev = _own(cur, dataset_id, uid)
    if body.get("keep"):
        if not prev:
            raise HTTPException(400, "유지할 분류가 없다 — 먼저 골라야 한다")
        chosen = prev
    else:
        chosen = manage.parse_category(body.get("category"))
    try:
        cur.execute("UPDATE dcat_dataset SET category=%s::jsonb, updated_at=now() WHERE dataset_id=%s",
                    (json.dumps(chosen, ensure_ascii=False), dataset_id))
        entry = record_decision(cur, dataset_id, previous=prev, chosen=chosen, shown=None,
                                actor=uid, role="user")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"dataset_id": dataset_id, "category": chosen, "chosen_ranks": entry["chosen_ranks"]}


@router.put("/datasets/{dataset_id:path}/visibility")
def set_visibility(dataset_id: str, body: Dict[str, Any] = Body(...), uid: str = Depends(current_user)):
    """공개 범위 변경. PRIVATE은 나만, ORG는 기관 안, PUBLIC은 전체."""
    v = body.get("visibility")
    if v not in manage.VISIBILITY:
        raise HTTPException(400, f"공개 범위는 {sorted(manage.VISIBILITY)} 중 하나다")
    conn = get_conn()
    cur = conn.cursor()
    _own(cur, dataset_id, uid)
    cur.execute("UPDATE dcat_dataset SET visibility=%s, updated_at=now() WHERE dataset_id=%s", (v, dataset_id))
    conn.commit()
    cur.execute("SELECT source_type FROM dcat_dataset WHERE dataset_id=%s", (dataset_id,))
    st = cur.fetchone()[0]
    return {"dataset_id": dataset_id, "visibility": v,
            "export_note": NO_EXPORT.get(st) if v == "PUBLIC" else None}
