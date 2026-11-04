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

## 권한을 보지 않는다

`/v1/*` 공개 API는 `visibility`로 거르지만(main.py), **콘솔은 거르지 않는다.**
총괄 관리자 시점으로 전부 본다. 권한 관리는 케이웨어 쪽에서 붙인다.

⚠️ 그래서 **외부에 열면 안 된다.** 로컬에서만 띄운다.

## 정형은 비워 둔다

`meta_datagokr_file` 0건이고 스키마도 협의 중이다(D-2). 지금 화면을 만들면
합의 결과에 따라 다시 만들게 된다. **탭만 두고 비워 두는 편이**
"정형이 아직 안 들어왔다"를 가장 정확히 보여준다.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.database.db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/console", tags=["내부 콘솔"])

#: 평가셋 라벨링 대상. C1 완료 판정이 여기 막혀 있다(대기 #1).
LABEL_POOL = Path("eval/search/video/pool_for_labeling.json")

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
def overview():
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
         "unit": "아이템", "note": "meta_* 적재 건수"},
        {"key": "feature",  "label": "특징 추출", "count": featured,
         "unit": "데이터셋", "note": "비정형에는 '매핑' 단계가 없다 — B1 특징 추출로 대체"},
        {"key": "review",   "label": "검토 대기", "count": pending_rel,
         "unit": "관계", "note": "사람이 승인해야 확정된다"},
        {"key": "listed",   "label": "등재",      "count": registered,
         "unit": "데이터셋", "note": "dcat_dataset"},
    ]

    cur.execute("""SELECT source_type, count(*) AS datasets,
                          coalesce(sum(item_count),0) AS items
                   FROM dcat_dataset GROUP BY 1 ORDER BY 1""")
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


@router.get("/registry")
def registry():
    """데이터셋별 수집 운영 현황. 원천 스키마 드리프트가 있으면 함께 보여준다."""
    cur = get_conn().cursor()
    base = ("SELECT r.dataset_id, d.title, d.source_type, r.status, r.item_count, "
            "r.row_count, r.last_collected_at, r.next_collect_at, r.last_error")
    tail = (" FROM data_registry r JOIN dcat_dataset d USING (dataset_id) "
            "ORDER BY r.next_collect_at NULLS LAST")
    try:
        cur.execute(base + ", r.source_schema_fingerprint, r.source_schema_checked_at, "
                    "r.source_schema_changed_at" + tail)
        rows = _rows(cur)
        drift = True
    except Exception:                             # noqa: BLE001
        # 드리프트 마이그레이션(2026-11-04) 미적용 상태. 실패한 SELECT가 트랜잭션을
        # ERROR로 남기므로 되돌려 놓는다 — 안 그러면 다음 질의가 전부 죽는다.
        get_conn().rollback()
        cur = get_conn().cursor()
        cur.execute(base + tail)
        rows = _rows(cur)
        drift = False
    return {"drift_columns": drift, "items": rows}


@router.get("/runs")
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

@router.get("/datasets/{dataset_id:path}/features")
def features(dataset_id: str):
    """B1 특징 추출 결과 전부. 데이터셋이 '무엇에 관한 것인가'의 실제 근거다."""
    cur = get_conn().cursor()
    cur.execute("""SELECT feature_name, value, method, computed_at
                   FROM meta_feature WHERE dataset_id=%s AND scope='dataset'
                   ORDER BY feature_name""", (dataset_id,))
    return {"items": [{**r, "value": _jsonb(r["value"])} for r in _rows(cur)]}


@router.get("/datasets/{dataset_id:path}/items")
def items(dataset_id: str, limit: int = Query(PREVIEW_LIMIT, le=100)):
    """아이템 미리보기 — 와이즈넛 화면4의 '데이터 미리보기'.

    어느 테이블을 볼지는 **`data_registry.pg_meta_table`이 이미 알고 있다.**
    소스별 분기를 코드에 또 쓰지 않는다. 소스가 늘어도 이 함수는 그대로다.
    """
    cur = get_conn().cursor()
    cur.execute("SELECT pg_meta_table FROM data_registry WHERE dataset_id=%s", (dataset_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "data_registry에 없는 데이터셋이다")
    table = row[0]
    if not table:
        # 외부 카탈로그 연합분이 여기 걸린다 — 메타만 받아 오고 아이템이 없다.
        # 비어 있는 것이 **정상**이고, 화면은 그 사실을 보여줘야 한다.
        return {"table": None, "columns": [], "items": [],
                "reason": "이 데이터셋에는 아이템 테이블이 없다 (메타데이터만 수집)"}
    if not _IDENT.match(table):
        raise HTTPException(500, "테이블명이 이상하다")
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (table,))
    if not cur.fetchone():
        raise HTTPException(500, f"{table} 테이블이 없다")

    cur.execute(f"SELECT * FROM {table} WHERE dataset_id=%s LIMIT %s", (dataset_id, limit))
    rows = _rows(cur)
    cols = [c for c in (rows[0] if rows else {}) if not is_secret_column(c)]
    return {"table": table, "columns": cols,
            "items": [{k: r[k] for k in cols} for r in rows]}


# ── 화면 5. 관계 지도 ───────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id:path}/graph")
def graph(dataset_id: str, hops: int = Query(2, ge=1, le=3),
          per_node: int = Query(5, le=20), include_pending: bool = True):
    """기준 데이터셋에서 이어지는 관계 그래프.

    **목록으로 표현할 수 없는 다단계 연결이 이 화면의 존재 이유다**(와이즈넛 §5.2).
    단계 수(`hop`)를 함께 돌려주므로 화면이 거리로 그릴 수 있다.
    """
    cur = get_conn().cursor()
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
        for r in _rows(cur):
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

@router.get("/review/relations")
def review_relations(status: str = Query("PENDING"), limit: int = Query(50, le=200)):
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


@router.post("/review/relations")
def decide_relation(payload: Dict[str, Any] = Body(...)):
    """관계 하나를 승인/거부한다. **콘솔에서 유일하게 쓰는 경로다.**

    B2 재실행은 `method='embedding' AND status='PENDING'`만 지운다 —
    여기서 사람이 바꾼 행은 살아남는다(`relations/store.py`).
    """
    rid, action = payload.get("id"), payload.get("action")
    if action not in ("APPROVED", "REJECTED", "PENDING"):
        raise HTTPException(400, "action은 APPROVED · REJECTED · PENDING 중 하나다")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE dcat_dataset_relation SET status=%s WHERE id=%s RETURNING id",
                (action, rid))
    if cur.fetchone() is None:
        raise HTTPException(404, "그런 관계가 없다")
    conn.commit()
    return {"id": rid, "status": action}


# ── 평가셋 라벨링 (C1 완료 판정이 여기 막혀 있다) ───────────────────────────

def _load_pool() -> List[Dict[str, Any]]:
    if not LABEL_POOL.is_file():
        return []
    return json.loads(LABEL_POOL.read_text(encoding="utf-8"))


def _label_progress() -> Dict[str, int]:
    pool = _load_pool()
    total = done = 0
    for q in pool:
        for c in q.get("candidates", []):
            total += 1
            if c.get("grade") is not None:
                done += 1
    return {"total": total, "done": done}


@router.get("/labeling")
def labeling():
    """채점 대상 전부와 진행률. 지금은 JSON 파일을 손으로 고쳐야 한다 —
    그래서 393건이 두 달째 그대로다."""
    pool = _load_pool()
    return {"file": str(LABEL_POOL), "progress": _label_progress(), "queries": pool}


@router.post("/labeling")
def save_label(payload: Dict[str, Any] = Body(...)):
    """한 건 채점. 파일에 바로 쓴다 — 중간 저장 장치를 따로 두면
    브라우저를 닫는 순간 날아간다."""
    query_id, doc_id, grade = payload.get("query_id"), payload.get("doc_id"), payload.get("grade")
    if grade not in (0, 1, 2, None):
        raise HTTPException(400, "grade는 0·1·2 또는 null(미채점)이다")
    pool = _load_pool()
    for q in pool:
        if q.get("query_id") != query_id:
            continue
        for c in q.get("candidates", []):
            if str(c.get("doc_id")) == str(doc_id):
                c["grade"] = grade
                LABEL_POOL.write_text(
                    json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"query_id": query_id, "doc_id": doc_id, "grade": grade,
                        "progress": _label_progress()}
    raise HTTPException(404, "그런 질의·문서 조합이 없다")
