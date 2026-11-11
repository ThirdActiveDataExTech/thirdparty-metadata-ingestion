"""내부 개발 콘솔 API — 프로토타입 (D1 최소선 확장).

**이건 포털이 아니다.** 실제 사용자 화면·디자인·배포는 케이웨어 과업이고
(NEXT_STEPS D1 목표선 "운영 대시보드 연계(케이웨어 접점)"), 여기 있는 것은
**우리가 확인·검토·소통하기 위한 프로토타입**이다. 목적이 셋이다.

1. 연구개발계획서의 기능이 실제 데이터 위에서 돌아가는지 **눈으로 확인**
2. 사람이 판단해야만 진도가 나가는 일(관계 검토·라벨링)을 **실제로 처리**
3. 케이웨어에 넘길 C6 OpenAPI의 **첫 소비자**가 되어 빠진 엔드포인트를 찾기

화면 구성은 와이즈넛 「백엔드 설계 초안 v2」 §5 화면요구사항을 따른다 —
수집 현황 / 등재 검토 / 검색 결과 / 데이터셋 상세 / 관계 지도.
우리 쪽에만 필요한 둘(관계 검토·평가셋 라벨링)을 더했다.

---

## 권한 (2026-11-10, 시제품 로그인 — ADR-021)

- 관리자 화면 전용(수집 운영·이력·관계 검토·라벨링·특징 원본)은 `require_admin`
- 포털 사용자 화면이 쓰는 것(목록·필터·통계·검색·상세·미리보기·관계 지도·수집 상태)은
  로그인 없이도 열리되 **공개 범위로 거른다**(`src/api/access.py`)
- `/overview`는 건수 집계뿐이라 거르지 않는다(홈 위젯)

⚠️ 인증이 시제품이라 **외부에 열면 안 된다.** 로컬에서만 띄운다.

## 정형은 비워 둔다

`meta_datagokr_file` 0건이고 스키마도 협의 중이다(D-2). 지금 화면을 만들면
합의 결과에 따라 다시 만들게 된다. **탭만 두고 비워 두는 편이**
"정형이 아직 안 들어왔다"를 가장 정확히 보여준다.
"""

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from src.api.access import ensure_visible, visible_clause, visible_ids
from src.api.auth import User, optional_user, require_admin
from src.common import config
from src.common.category_taxonomy import PRIVATE_FEATURES
from src.common.error_kind import classify_error
from src.database.db import get_conn
from src.api.db_scope import ReleaseDbRoute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/console", tags=["내부 콘솔"], route_class=ReleaseDbRoute)

#: 평가셋 라벨링 대상. C1 완료 판정이 여기 막혀 있다(대기 #1).
#: `LABEL_POOL_PATH`로 바꿀 수 있다 — 클러스터에서 영구 볼륨에 둘 때 쓴다(아래 `_pool_storage`).
LABEL_POOL = Path(os.environ.get("LABEL_POOL_PATH") or "eval/search/video/pool_for_labeling.json")

#: 테이블명을 DB에서 읽어 쓰므로(아래 `items`) 모양을 한 번 더 확인한다.
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")

#: 자격증명 성격의 컬럼은 내보내지 않는다. meta_*에는 없지만, 테이블명을 동적으로
#: 받는 경로라 방어를 한 겹 둔다.
#:
#: ⚠️ 부분 문자열로 거르면 안 된다 — `keywords`가 'key'에 걸려 사라진다.
#: 이름을 조각(스네이크·카멜)으로 끊어 **낱말 단위로** 본다.
_SECRET_WORDS = frozenset({"key", "keys", "secret", "token", "password", "passwd",
                           "credential", "credentials", "apikey", "accesskey"})
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def is_secret_column(name: str) -> bool:
    parts = re.split(r"[^a-z0-9]+", _CAMEL.sub("_", name).lower())
    return any(p in _SECRET_WORDS for p in parts)

#: 미리보기 행수. 전수를 보내면 브라우저가 멈춘다.
PREVIEW_LIMIT = 20


def _rows(cur) -> List[Dict[str, Any]]:
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _jsonb(v):
    return json.loads(v) if isinstance(v, str) else v


# ── 화면 1. 수집 현황 ───────────────────────────────────────────────────────

@router.get("/overview")
def overview(user: Optional[User] = Depends(optional_user)):
    """단계별 적체와 사람 대기 건수.

    와이즈넛 화면1은 `수집 → 매핑 → 검토 대기 → 등재` 4단계다. **비정형에는
    '매핑' 단계가 없다** — 원천이 주는 모양이 고정이라 반자동 매핑을 할 일이
    없다. 그 자리에 우리가 실제로 하는 일(특징 추출)을 넣고 그렇게 표시한다.
    없는 단계를 있는 척하면 화면이 거짓말을 한다.
    """
    cur = get_conn().cursor()
    out: Dict[str, Any] = {}

    cur.execute("SELECT count(*) FROM dcat_dataset")
    registered = cur.fetchone()[0]
    cur.execute("SELECT coalesce(sum(item_count),0) FROM data_registry")
    items = cur.fetchone()[0]
    cur.execute("SELECT count(DISTINCT dataset_id) FROM meta_feature WHERE scope='dataset'")
    featured = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM dcat_dataset_relation WHERE status='PENDING'")
    pending_rel = cur.fetchone()[0]

    out["stages"] = [
        {"key": "collect",  "label": "수집",      "count": int(items),
         "unit": "아이템", "note": "수집해 저장한 아이템 수"},
        {"key": "feature",  "label": "특징 추출", "count": featured,
         "unit": "데이터셋", "note": "비정형 데이터는 '매핑' 단계 대신 특징 추출(B1)을 거칩니다"},
        {"key": "review",   "label": "검토 대기", "count": pending_rel,
         "unit": "관계", "note": "관리자가 승인해야 확정됩니다"},
        {"key": "listed",   "label": "등재",      "count": registered,
         "unit": "데이터셋", "note": "카탈로그에 등재된 데이터셋 수"},
    ]

    # 유형별 건수는 포털 첫 화면에 나간다 — 그 사람이 눌러 들어가 볼 수 있는 것만 센다
    cond, vparams = visible_clause(user)
    cur.execute(f"""SELECT source_type, count(*) AS datasets,
                           coalesce(sum(item_count),0) AS items
                    FROM dcat_dataset WHERE {cond} GROUP BY 1 ORDER BY 1""", vparams)
    out["by_type"] = _rows(cur)

    # 사람이 처리해야 진도가 나가는 것들. 화면의 존재 이유다.
    labels = _label_progress()
    cur.execute("""SELECT count(*) FROM meta_feature
                   WHERE scope='dataset' AND feature_name='suggested_category'""")
    out["waiting_on_human"] = {
        "relations": pending_rel,
        "category_suggestions": cur.fetchone()[0],
        "labels_total": labels["total"],
        "labels_done": labels["done"],
    }
    return out


#: 드리프트 컬럼 존재 여부. 한 번만 보고 기억한다 — 아래 주석 참조.
_HAS_DRIFT: Optional[bool] = None


def _has_drift_columns(cur) -> bool:
    """`source_schema_*` 컬럼이 있는가(= 2026-11-04 마이그레이션 적용 여부).

    ⚠️ **일부러 실패하는 SELECT로 알아내면 안 된다.** 커넥션은 프로세스당 하나를
    **공유**하는데(src/database/db.py), 콘솔은 화면 하나가 API 세 개를 동시에 부른다.
    실패한 질의가 트랜잭션을 ERROR로 만들면 **같은 순간 다른 요청의 질의까지**
    `InFailedSqlTransaction`으로 죽는다. 2026-11-04 콘솔을 붙이고 실제로 겪었다.

    그래서 스키마는 information_schema로 **묻고**, 결과는 기억한다.
    """
    global _HAS_DRIFT
    if _HAS_DRIFT is None:
        cur.execute("SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='data_registry' AND column_name='source_schema_fingerprint'")
        _HAS_DRIFT = cur.fetchone() is not None
    return _HAS_DRIFT


@router.get("/registry", dependencies=[Depends(require_admin)])
def registry():
    """데이터셋별 수집 운영 현황. 원천 스키마 드리프트가 있으면 함께 보여준다."""
    cur = get_conn().cursor()
    drift = _has_drift_columns(cur)
    extra = (", r.source_schema_fingerprint, r.source_schema_checked_at, "
             "r.source_schema_changed_at") if drift else ""
    cur.execute(
        "SELECT r.dataset_id, d.title, d.source_type, r.status, r.item_count, "
        "r.row_count, r.last_collected_at, r.next_collect_at, r.last_error" + extra +
        " FROM data_registry r JOIN dcat_dataset d USING (dataset_id) "
        "ORDER BY r.next_collect_at NULLS LAST")
    return {"drift_columns": drift, "items": _rows(cur)}


@router.get("/runs", dependencies=[Depends(require_admin)])
def runs(limit: int = Query(50, le=300)):
    """수집 실행 이력(PROV-O). 와이즈넛 화면1의 '실행 이력'."""
    cur = get_conn().cursor()
    cur.execute("""SELECT p.prov_id, p.dataset_id, d.title, p.activity_type, p.agent,
                          p.triggered_by, p.started_at, p.ended_at, p.status,
                          p.rows_affected, p.error_message
                   FROM dcat_provenance p LEFT JOIN dcat_dataset d USING (dataset_id)
                   ORDER BY p.started_at DESC LIMIT %s""", (limit,))
    return {"items": _rows(cur)}


# ── 화면 4. 데이터셋 상세 ───────────────────────────────────────────────────

@router.get("/datasets/{dataset_id:path}/features", dependencies=[Depends(require_admin)])
def features(dataset_id: str):
    """B1 특징 추출 결과 전부. 데이터셋이 '무엇에 관한 것인가'의 실제 근거다."""
    cur = get_conn().cursor()
    cur.execute("""SELECT feature_name, value, method, computed_at
                   FROM meta_feature WHERE dataset_id=%s AND scope='dataset'
                   ORDER BY feature_name""", (dataset_id,))
    return {"items": [{**r, "value": _jsonb(r["value"])} for r in _rows(cur)]}


@router.get("/datasets/{dataset_id:path}/items")
def items(dataset_id: str, limit: int = Query(PREVIEW_LIMIT, le=100),
          user: Optional[User] = Depends(optional_user)):
    """아이템 미리보기 — 와이즈넛 화면4의 '데이터 미리보기'.

    어느 테이블을 볼지는 **`data_registry.pg_meta_table`이 이미 알고 있다.**
    소스별 분기를 코드에 또 쓰지 않는다. 소스가 늘어도 이 함수는 그대로다.
    """
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    cur.execute("SELECT pg_meta_table FROM data_registry WHERE dataset_id=%s", (dataset_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    table = row[0]
    if not table:
        # 외부 카탈로그 연합분이 여기 걸린다 — 메타만 받아 오고 아이템이 없다.
        # 비어 있는 것이 **정상**이고, 화면은 그 사실을 보여줘야 한다.
        return {"table": None, "columns": [], "items": [],
                "reason": "메타데이터만 수집하는 데이터셋이라 아이템이 없습니다"}
    if not _IDENT.match(table):
        raise HTTPException(500, "아이템 저장 위치 설정이 올바르지 않습니다. 관리자에게 문의해 주세요")
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (table,))
    if not cur.fetchone():
        raise HTTPException(500, "아이템 저장 테이블을 찾을 수 없습니다. 관리자에게 문의해 주세요")

    cur.execute(f"SELECT * FROM {table} WHERE dataset_id=%s LIMIT %s", (dataset_id, limit))
    rows = _rows(cur)
    cols = [c for c in (rows[0] if rows else {}) if not is_secret_column(c)]
    return {"table": table, "columns": cols,
            "items": [{k: r[k] for k in cols} for r in rows]}


# ── 화면 5. 관계 지도 ───────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id:path}/graph")
def graph(dataset_id: str, hops: int = Query(2, ge=1, le=3),
          per_node: int = Query(5, le=20), include_pending: bool = True,
          user: Optional[User] = Depends(optional_user)):
    """기준 데이터셋에서 이어지는 관계 그래프.

    **목록으로 표현할 수 없는 다단계 연결이 이 화면의 존재 이유다**(와이즈넛 §5.2).
    단계 수(`hop`)를 함께 돌려주므로 화면이 거리로 그릴 수 있다.
    """
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    allowed = "('PENDING','APPROVED')" if include_pending else "('APPROVED')"
    seen = {dataset_id: 0}
    edges: List[Dict[str, Any]] = []
    frontier = [dataset_id]

    for hop in range(1, hops + 1):
        if not frontier:
            break
        cur.execute(
            f"SELECT source_dataset_id, target_dataset_id, relation_type, "
            f"       relation_label, score, status, evidence "
            f"FROM (SELECT *, row_number() OVER (PARTITION BY source_dataset_id, relation_type "
            f"                                   ORDER BY score DESC) AS rn "
            f"      FROM dcat_dataset_relation "
            f"      WHERE source_dataset_id = ANY(%s) AND status IN {allowed}) t "
            f"WHERE rn <= %s", (frontier, per_node))
        nxt = []
        hop_rows = _rows(cur)
        # 볼 수 없는 데이터셋으로 가는 간선은 그리지 않고, 그 너머로도 건너가지 않는다
        ok = visible_ids(cur, [r["target_dataset_id"] for r in hop_rows], user)
        for r in hop_rows:
            if r["target_dataset_id"] not in ok:
                continue
            r["evidence"] = _jsonb(r["evidence"])
            r["hop"] = hop
            edges.append(r)
            tgt = r["target_dataset_id"]
            if tgt not in seen:
                seen[tgt] = hop
                nxt.append(tgt)
        frontier = nxt

    cur.execute("""SELECT dataset_id, title, source_type, item_count
                   FROM dcat_dataset WHERE dataset_id = ANY(%s)""", (list(seen),))
    nodes = [{**n, "hop": seen[n["dataset_id"]]} for n in _rows(cur)]
    return {"root": dataset_id, "nodes": nodes, "edges": edges}


# ── 화면 2. 검토 (관계 승인/거부) ───────────────────────────────────────────

@router.get("/review/relations", dependencies=[Depends(require_admin)])
def review_relations(status: str = Query("PENDING"), limit: int = Query(50, le=1000)):
    """사람이 판단할 관계 목록. `evidence`를 그대로 실어 보낸다 —
    근거 없이 승인/거부를 누르게 하면 검토가 아니라 요식이 된다."""
    cur = get_conn().cursor()
    cur.execute("""SELECT r.id, r.source_dataset_id, s.title AS source_title,
                          r.target_dataset_id, t.title AS target_title,
                          r.relation_type, r.relation_label, r.score, r.method,
                          r.status, r.evidence, r.created_at
                   FROM dcat_dataset_relation r
                   JOIN dcat_dataset s ON s.dataset_id = r.source_dataset_id
                   JOIN dcat_dataset t ON t.dataset_id = r.target_dataset_id
                   WHERE r.status = %s
                   ORDER BY r.relation_type, r.score DESC LIMIT %s""", (status, limit))
    return {"items": [{**r, "evidence": _jsonb(r["evidence"])} for r in _rows(cur)]}


@router.post("/review/relations", dependencies=[Depends(require_admin)])
def decide_relation(payload: Dict[str, Any] = Body(...)):
    """관계 하나를 승인/거부한다. **콘솔에서 유일하게 쓰는 경로다.**

    B2 재실행은 `method='embedding' AND status='PENDING'`만 지운다 —
    여기서 사람이 바꾼 행은 살아남는다(`relations/store.py`).
    """
    rid, action = payload.get("id"), payload.get("action")
    if action not in ("APPROVED", "REJECTED", "PENDING"):
        raise HTTPException(400, "처리 값은 APPROVED · REJECTED · PENDING 중 하나여야 합니다")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE dcat_dataset_relation SET status=%s WHERE id=%s RETURNING id",
                (action, rid))
    if cur.fetchone() is None:
        raise HTTPException(404, "해당 관계를 찾을 수 없습니다")
    conn.commit()
    return {"id": rid, "status": action}


# ── 평가셋 라벨링 (C1 완료 판정이 여기 막혀 있다) ───────────────────────────

#: 읽고-고치고-쓰기를 한 번에 하나만. 키보드로 빠르게 누르면 요청이 겹치고,
#: 겹친 두 저장 중 하나가 다른 하나를 덮어 **채점이 조용히 사라진다**.
_POOL_LOCK = threading.Lock()

#: 채점 판단용 요약 길이. 길면 393건을 훑는 속도가 떨어진다.
CONTEXT_SNIPPET = 200


def _load_pool() -> List[Dict[str, Any]]:
    if not LABEL_POOL.is_file():
        return []
    return json.loads(LABEL_POOL.read_text(encoding="utf-8"))


def _write_pool(pool: List[Dict[str, Any]]) -> None:
    """임시 파일에 쓰고 바꿔 끼운다 — 쓰는 도중 죽어도 원본이 반쯤 잘리지 않는다."""
    tmp = LABEL_POOL.with_name(LABEL_POOL.name + ".tmp")
    tmp.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, LABEL_POOL)


def _progress_of(pool: List[Dict[str, Any]]) -> Dict[str, int]:
    total = done = 0
    for q in pool:
        for c in q.get("candidates", []):
            total += 1
            if c.get("grade") is not None:
                done += 1
    return {"total": total, "done": done}


def _label_progress() -> Dict[str, int]:
    return _progress_of(_load_pool())


def _pool_storage() -> Dict[str, Any]:
    """저장 위치가 오래 남는지. 채점 결과는 이 파일 하나뿐이라 화면이 미리 알려야 한다.

    - `LABEL_POOL_PERSISTENT=1|0`이 있으면 그대로 따른다(영구 볼륨을 붙였을 때 1)
    - 없으면 k8s 파드 안(`KUBERNETES_SERVICE_HOST`)은 **컨테이너 파일시스템**이라
      파드가 다시 뜨면 사라진다고 본다. 로컬 실행은 작업 사본(레포)에 남는다.
    """
    flag = os.environ.get("LABEL_POOL_PERSISTENT", "").strip().lower()
    in_pod = bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
    if flag in ("1", "true", "yes"):
        persistent, reason = True, "env"
    elif flag in ("0", "false", "no"):
        persistent, reason = False, "env"
    else:
        persistent, reason = not in_pod, ("pod" if in_pod else "local")
    target = LABEL_POOL if LABEL_POOL.exists() else LABEL_POOL.parent
    return {"path": str(LABEL_POOL.resolve()), "writable": os.access(target, os.W_OK),
            "persistent": persistent, "reason": reason}


def _trim(text: Optional[str], n: int = CONTEXT_SNIPPET) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[:n].rstrip() + "…"


def _video_context(doc_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """후보 판단에 필요한 맥락을 **한 번의 조회로** 붙인다. `doc_id` = `meta_video.id`.

    요약은 AI 요약(자막·설명 기반)을 먼저, 없으면 설명을 쓴다. 숫자가 아닌 id는 건너뛴다.
    """
    ids = sorted({int(d) for d in doc_ids if str(d).isdigit()})
    if not ids:
        return {}
    cur = get_conn().cursor()
    cur.execute("""SELECT m.id, m.video_id, m.channel_title, m.published_at,
                          m.duration_seconds, m.description, m.thumbnail_url,
                          m.has_transcript, m.is_removed,
                          a.ai_summary, a.ai_keywords
                   FROM meta_video m
                   LEFT JOIN meta_video_ai a ON a.meta_id = m.id AND a.status = 'ok'
                   WHERE m.id = ANY(%s)""", (ids,))
    out: Dict[str, Dict[str, Any]] = {}
    for r in _rows(cur):
        summary = _trim(r.get("ai_summary"))
        pub = r.get("published_at")
        vid = r.get("video_id")
        out[str(r["id"])] = {
            "channel": r.get("channel_title"),
            "published_at": pub.date().isoformat() if hasattr(pub, "date") else pub,
            "duration_seconds": r.get("duration_seconds"),
            "snippet": summary or _trim(r.get("description")),
            "snippet_source": "ai_summary" if summary else ("description" if r.get("description") else None),
            "keywords": list(r.get("ai_keywords") or [])[:6],
            "has_transcript": bool(r.get("has_transcript")),
            "removed": bool(r.get("is_removed")),
            "thumbnail_url": r.get("thumbnail_url"),
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
        }
    return out


@router.get("/labeling", dependencies=[Depends(require_admin)])
def labeling():
    """채점 대상 전부와 진행률. 후보마다 채널·요약·길이·게시일·원본 링크를 붙인다 —
    제목과 번호만으로는 원본을 열어 보지 않고 판단할 수 없었다.

    맥락은 덧붙임이다. DB가 안 되면 맥락 없이(`context_error`) 채점은 계속할 수 있게 둔다.
    """
    pool = _load_pool()
    context_error = None
    try:
        ctx = _video_context([c.get("doc_id") for q in pool for c in q.get("candidates", [])])
    except Exception as e:  # noqa: BLE001 — 맥락 실패로 채점 화면 전체를 막지 않는다
        logger.warning("라벨링 맥락 조회 실패: %s", e)
        ctx, context_error = {}, "후보 맥락(채널·요약)을 불러오지 못했습니다"
    for q in pool:
        for c in q.get("candidates", []):
            extra = ctx.get(str(c.get("doc_id")))
            if extra:
                c.update({k: v for k, v in extra.items() if k not in ("doc_id", "title", "grade")})
    return {"file": str(LABEL_POOL), "progress": _progress_of(pool), "queries": pool,
            "storage": _pool_storage(), "context_error": context_error}


@router.post("/labeling", dependencies=[Depends(require_admin)])
def save_label(payload: Dict[str, Any] = Body(...)):
    """한 건 채점. 파일에 바로 쓴다 — 중간 저장 장치를 따로 두면
    브라우저를 닫는 순간 날아간다."""
    query_id, doc_id, grade = payload.get("query_id"), payload.get("doc_id"), payload.get("grade")
    if grade not in (0, 1, 2, None) or isinstance(grade, bool):
        raise HTTPException(400, "등급은 0·1·2 또는 미채점(null)이어야 합니다")
    with _POOL_LOCK:
        pool = _load_pool()
        for q in pool:
            if q.get("query_id") != query_id:
                continue
            for c in q.get("candidates", []):
                if str(c.get("doc_id")) == str(doc_id):
                    c["grade"] = grade
                    _write_pool(pool)
                    return {"query_id": query_id, "doc_id": doc_id, "grade": grade,
                            "progress": _progress_of(pool)}
    raise HTTPException(404, "해당 질의·문서 조합을 찾을 수 없습니다")


# ════════════════════════════════════════════════════════════════════════════
# 포털 화면용 — 카탈로그·검색·통계 (2026-11-04, portal-mockup을 실데이터에 붙이며 추가)
#
# 공개 `/v1/datasets`는 응답을 일부러 좁게 둔다(외부 노출 전제). 포털 화면은
# 21개 메타데이터 전부와 공개 범위까지 보여줘야 하므로 여기 따로 둔다.
# 이 영역도 콘솔과 같이 **권한을 보지 않는다**(총괄 관리자 시점).
# ════════════════════════════════════════════════════════════════════════════

#: 포털이 보여주는 카탈로그 컬럼. `owner_id`는 계정 식별자라 화면에 내지 않는다.
_CATALOG_COLS = (
    "dataset_id, title, description, publisher, source_type, source, landing_page, "
    "access_url, subjects, language, spatial, temporal_start, temporal_end, "
    "temporal_resolution, accrual_periodicity, keywords, license, rights, "
    "dataset_origin, version, created_at, updated_at, item_count, category, theme, "
    "external_ids, party, visibility"
)
_JSONB_COLS = ("subjects", "keywords", "category", "theme", "external_ids")

#: 정렬 허용 목록. 사용자 입력을 SQL에 그대로 넣지 않는다.
_SORTS = {
    "created_at": "created_at DESC NULLS LAST",
    "updated_at": "updated_at DESC NULLS LAST",
    "title": "title ASC",
    "item_count": "item_count DESC NULLS LAST",
}


def _catalog_row(r: Dict[str, Any]) -> Dict[str, Any]:
    for c in _JSONB_COLS:
        v = _jsonb(r.get(c))
        r[c] = v if isinstance(v, list) else ([] if v is None else [v])
    for c in ("temporal_start", "temporal_end"):
        if r.get(c) is not None:
            r[c] = r[c].isoformat()
    return r


@router.get("/datasets")
def catalog(q: Optional[str] = None, source_type: Optional[str] = None,
            exclude_source_type: Optional[str] = None, publisher: Optional[str] = None, category: Optional[str] = None,
            origin: Optional[str] = None, party: Optional[str] = None, date_from: Optional[str] = None,
            date_to: Optional[str] = None, ids: Optional[str] = None,
            sort: str = Query("updated_at"), limit: int = Query(20, ge=1, le=200),
            offset: int = Query(0, ge=0), user: Optional[User] = Depends(optional_user)):
    """포털 카탈로그 — 조건 검색(키워드검색 탭)과 목록·신규데이터가 함께 쓴다.

    `category`는 **대분류 접두**로 거른다(`기술` → `기술 > 전기·전자` 등). 분류표가
    `대분류 > 중분류` 문자열이라 대분류만 고르는 화면에서 정확 일치로는 안 걸린다.
    `ids`는 문장검색 결과를 카탈로그 정보로 채울 때 쓴다(쉼표 구분).
    `exclude_source_type`은 그 유형을 뺀다(쉼표 구분) — 홈 신규데이터가 외부 포털
    연합분(`external_catalog`)에 덮이지 않게 쓴다.
    """
    if sort not in _SORTS:
        raise HTTPException(400, f"정렬 기준은 {sorted(_SORTS)} 중 하나여야 합니다")
    vis, vparams = visible_clause(user)
    where, params = [vis], {"limit": limit, "offset": offset, **vparams}
    if q:
        where.append("(title ILIKE %(q)s OR description ILIKE %(q)s "
                     "OR keywords::text ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    if source_type:
        where.append("source_type = %(st)s"); params["st"] = source_type
    if exclude_source_type:
        where.append("NOT (source_type = ANY(%(xst)s))")
        params["xst"] = [v.strip() for v in exclude_source_type.split(",") if v.strip()]
    if publisher:
        where.append("publisher = %(pub)s"); params["pub"] = publisher
    if origin:
        where.append("dataset_origin = %(origin)s"); params["origin"] = origin
    if party:
        # 정형 1st party(기관 직접 보유) / 3rd party(외부 원천). 값이 비어 있는 행은 '미지정'
        if party == "none":
            where.append("party IS NULL")
        else:
            where.append("party = %(party)s"); params["party"] = party
    if category:
        where.append("EXISTS (SELECT 1 FROM jsonb_array_elements_text(category) c "
                     "WHERE c = %(cat)s OR c LIKE %(catp)s)")
        params["cat"], params["catp"] = category, f"{category} >%"
    if date_from:
        where.append("created_at >= %(df)s::date"); params["df"] = date_from
    if date_to:
        where.append("created_at < (%(dt)s::date + 1)"); params["dt"] = date_to
    if ids:
        where.append("dataset_id = ANY(%(ids)s)")
        params["ids"] = [i for i in ids.split(",") if i]
    cond = " AND ".join(where)
    cur = get_conn().cursor()
    cur.execute(f"SELECT count(*) FROM dcat_dataset WHERE {cond}", params)
    total = cur.fetchone()[0]
    cur.execute(f"SELECT {_CATALOG_COLS} FROM dcat_dataset WHERE {cond} "
                f"ORDER BY {_SORTS[sort]}, dataset_id LIMIT %(limit)s OFFSET %(offset)s",
                params)
    return {"total": total, "limit": limit, "offset": offset,
            "items": [_catalog_row(r) for r in _rows(cur)]}


@router.get("/facets")
def facets(user: Optional[User] = Depends(optional_user)):
    """필터 선택지와 건수. 화면이 선택지를 하드코딩하면 데이터와 어긋난다 —
    목업의 10개 분류가 실제 분류표(대분류 7)와 달랐던 것처럼."""
    cur = get_conn().cursor()
    vis, vp = visible_clause(user)
    out: Dict[str, Any] = {}
    for key, col in (("source_types", "source_type"), ("publishers", "publisher"),
                     ("sources", "source"), ("origins", "dataset_origin"),
                     ("parties", "coalesce(party, 'none')")):
        cur.execute(f"SELECT {col} AS value, count(*) AS count FROM dcat_dataset "
                    f"WHERE {col} IS NOT NULL AND {vis} GROUP BY 1 ORDER BY 2 DESC, 1", vp)
        out[key] = _rows(cur)
    cur.execute(f"""SELECT split_part(c, ' > ', 1) AS value, count(DISTINCT dataset_id) AS count
                   FROM dcat_dataset, jsonb_array_elements_text(category) c WHERE {vis}
                   GROUP BY 1 ORDER BY 2 DESC, 1""", vp)
    out["categories"] = _rows(cur)
    # 중분류 건수 — 검색 화면의 카테고리 트리(대분류 → 중분류)가 쓴다
    cur.execute(f"""SELECT c AS value, count(DISTINCT dataset_id) AS count
                   FROM dcat_dataset, jsonb_array_elements_text(category) c WHERE {vis}
                   GROUP BY 1 ORDER BY 1""", vp)
    out["subcategories"] = _rows(cur)
    return out


@router.get("/stats")
def stats(user: Optional[User] = Depends(optional_user)):
    """현황 화면·메인 통계. 전부 실측이다. 볼 수 있는 데이터셋 기준."""
    cur = get_conn().cursor()
    vis, vp = visible_clause(user)
    vis_d, vp_d = visible_clause(user, "d.")
    cur.execute(f"""SELECT count(*) AS datasets, coalesce(sum(item_count),0) AS items,
                          count(DISTINCT source) AS platforms
                   FROM dcat_dataset WHERE {vis}""", vp)
    totals = _rows(cur)[0]
    cur.execute("SELECT count(*) FROM dcat_dataset_relation WHERE status <> 'REJECTED'")
    totals["relations"] = cur.fetchone()[0]
    cur.execute(f"""SELECT split_part(c, ' > ', 1) AS category,
                          count(DISTINCT d.dataset_id) AS datasets,
                          coalesce(sum(d.item_count),0) AS items
                   FROM dcat_dataset d, jsonb_array_elements_text(d.category) c WHERE {vis_d}
                   GROUP BY 1 ORDER BY 3 DESC""", vp_d)
    by_category = _rows(cur)
    cur.execute(f"""SELECT source AS platform, count(*) AS datasets,
                          coalesce(sum(item_count),0) AS items
                   FROM dcat_dataset WHERE {vis} GROUP BY 1 ORDER BY 3 DESC""", vp)
    by_platform = _rows(cur)
    # 조회수를 기록하지 않는다 — '인기'를 만들어 낼 수 없다. 아이템이 많은 순으로
    # 대신하고, 화면에 그렇게 적는다(없는 지표를 있는 척하지 않는다).
    cur.execute(f"""SELECT dataset_id, title, source_type, item_count, created_at
                   FROM dcat_dataset WHERE {vis} ORDER BY item_count DESC NULLS LAST LIMIT 10""", vp)
    top = _rows(cur)
    return {"totals": totals, "by_category": by_category, "by_platform": by_platform,
            "top_by_items": top, "view_tracking": False}


#: 아이템 검색 결과를 화면에 쓸 모양으로 채운다. hybrid.py의 SQL은 평가로 튜닝한 것이라
#: 손대지 않고, 결과 id로 원본 테이블을 한 번 더 읽는다.
_ITEM_HYDRATE = {
    "video": ("meta_video", "dataset_id, title, description, published_at, channel_title AS byline, "
                            "'https://www.youtube.com/watch?v=' || video_id AS url, thumbnail_url"),
    "news":  ("meta_news",  "dataset_id, title, description, published_at, publisher AS byline, "
                            "article_url AS url, NULL AS thumbnail_url"),
    "blog":  ("meta_blog",  "dataset_id, title, description, published_at, blogger_name AS byline, "
                            "post_url AS url, NULL AS thumbnail_url"),
}


@router.get("/search/items")
def search_items(q: str = Query(..., min_length=1), source: str = Query("video"),
                 limit: int = Query(20, ge=1, le=50), user: Optional[User] = Depends(optional_user)):
    """콘텐츠(아이템) 검색 — 영상·기사·글 단위. **C1이 실제로 만든 검색은 이쪽이다.**

    목업은 데이터셋만 찾았다. 하이브리드 검색과 평가셋은 아이템 단위로 만들어졌고,
    사용자가 실제로 찾는 것도 대개 "그 내용이 담긴 영상"이다.
    """
    if source not in _ITEM_HYDRATE:
        raise HTTPException(400, f"검색 대상은 {sorted(_ITEM_HYDRATE)} 중 하나여야 합니다")
    from src.search import hybrid
    # 볼 수 없는 데이터셋의 아이템을 빼고도 limit을 채우려고 넉넉히 받는다(RRF 순위라 위쪽은 같다)
    hits = hybrid.search(q, source, top_k=limit * 2)
    table, cols = _ITEM_HYDRATE[source]
    cur = get_conn().cursor()
    # 왕복을 줄인다(2026-11-10) — 예전엔 소유 데이터셋 조회 → 공개 범위 → 원본 → 데이터셋
    # 제목으로 4번 오갔다. 원본 행에 dataset_id가 있으므로 원본을 먼저 한 번에 읽고,
    # 공개 범위 판정과 제목은 같은 조건(visible_clause)으로 한 번에 얻는다.
    extra: Dict[Any, Dict[str, Any]] = {}
    titles: Dict[str, Any] = {}
    if hits:
        cur.execute(f"SELECT id, {cols} FROM {table} WHERE id = ANY(%s)",
                    ([h["id"] for h in hits],))
        extra = {r["id"]: r for r in _rows(cur)}
        ds_ids = sorted({r["dataset_id"] for r in extra.values() if r.get("dataset_id")})
        if ds_ids:
            cond, vp = visible_clause(user)
            cur.execute(f"SELECT dataset_id, title FROM dcat_dataset "
                        f"WHERE dataset_id = ANY(%(_ids)s) AND {cond}", {**vp, "_ids": ds_ids})
            titles = dict(cur.fetchall())          # 볼 수 있는 데이터셋만 들어온다
    hits = [h for h in hits if extra.get(h["id"], {}).get("dataset_id") in titles][:limit]
    ai: Dict[Any, Dict[str, Any]] = {}
    if source == "video" and hits:
        cur.execute("SELECT meta_id, ai_summary, ai_keywords FROM meta_video_ai "
                    "WHERE meta_id = ANY(%s) AND status='ok'", ([h["id"] for h in hits],))
        ai = {r["meta_id"]: r for r in _rows(cur)}
    out = []
    for h in hits:
        e = extra.get(h["id"], {})
        a = ai.get(h["id"], {})
        out.append({
            "id": h["id"], "title": h["title"], "byline": e.get("byline"),
            "description": e.get("description"), "url": e.get("url"),
            "thumbnail_url": e.get("thumbnail_url"), "published_at": e.get("published_at"),
            "dataset_id": e.get("dataset_id"), "dataset_title": titles.get(e.get("dataset_id")),
            "rrf": float(h["rrf"]) if h.get("rrf") is not None else None,
            "vec_rank": h.get("vec_rank"), "kw_rank": h.get("kw_rank"),
            "ai_summary": a.get("ai_summary"), "ai_keywords": _jsonb(a.get("ai_keywords")) or [],
        })
    return {"query": q, "source": source, "total": len(out), "items": out,
            "rarest_token": hybrid.rarest_token_df(q, source)}


@router.get("/datasets/{dataset_id:path}/status")
def dataset_status(dataset_id: str, user: Optional[User] = Depends(optional_user)):
    """한 데이터셋의 수집 운영 상태와 최근 실행 이력 — 상세 화면의 '수집 정보'.
    원문 오류는 관리자에게만 준다(사용자에게는 원인 분류의 안내 문구만)."""
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    cur.execute("""SELECT status, item_count, row_count, last_collected_at, next_collect_at,
                          last_error, pg_meta_table, s3_raw_prefix
                   FROM data_registry WHERE dataset_id=%s""", (dataset_id,))
    reg = _rows(cur)
    cur.execute("""SELECT activity_type, triggered_by, started_at, ended_at, status,
                          rows_affected
                   FROM dcat_provenance WHERE dataset_id=%s
                   ORDER BY started_at DESC LIMIT 10""", (dataset_id,))
    if reg:
        reg[0]["last_error"] = config.mask_secrets(reg[0]["last_error"] or "") or None
        reg[0]["cause"] = classify_error(reg[0]["last_error"]) if reg[0]["status"] == "error" else None
        if not (user and user.is_admin):
            reg[0]["last_error"] = None
            reg[0]["s3_raw_prefix"] = None      # 내부 저장 경로
    return {"registry": reg[0] if reg else None, "runs": _rows(cur)}


# ⚠️ 이 라우트는 **맨 마지막에** 둔다. `{dataset_id:path}`가 슬래시까지 삼키므로
# 앞에 있으면 `/features`·`/items`·`/graph`·`/status`를 식별자의 일부로 읽는다.
# main.py의 `/jsonld`가 바로 그렇게 죽어 있었다(2026-11-04).
@router.get("/datasets/{dataset_id:path}")
def catalog_detail(dataset_id: str, user: Optional[User] = Depends(optional_user)):
    """포털 상세 — 21개 메타데이터 + 공개 범위 + B1 특징 + 관계 + 수집 상태."""
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    cur.execute(f"SELECT {_CATALOG_COLS} FROM dcat_dataset WHERE dataset_id=%s", (dataset_id,))
    rows = _rows(cur)
    if not rows:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    out = _catalog_row(rows[0])
    # 확정 이력(누가 골랐나)은 사용자 상세에 내지 않는다 — 관리자는 /features에서 본다
    cur.execute("SELECT feature_name, value FROM meta_feature "
                "WHERE dataset_id=%s AND scope='dataset' AND feature_name <> ALL(%s)",
                (dataset_id, PRIVATE_FEATURES))
    out["features"] = {n: _jsonb(v) for n, v in cur.fetchall()}
    cur.execute("""SELECT r.id, r.target_dataset_id AS dataset_id, t.title, t.source_type,
                          r.relation_type, r.relation_label, r.score, r.status, r.evidence
                   FROM dcat_dataset_relation r
                   JOIN dcat_dataset t ON t.dataset_id = r.target_dataset_id
                   WHERE r.source_dataset_id=%s AND r.status <> 'REJECTED'
                   ORDER BY r.relation_type, r.score DESC""", (dataset_id,))
    rels = _rows(cur)
    ok = visible_ids(cur, [r["dataset_id"] for r in rels], user)
    out["relations"] = [{**r, "score": float(r["score"]), "evidence": _jsonb(r["evidence"])}
                        for r in rels if r["dataset_id"] in ok]
    return out
