"""내부 카탈로그 OpenAPI (C6 최소선).

연구개발계획서 3차년도 "탐색 확장·통합 구성" / 최종 산출물
"써드파티 데이터 활용 통합 플랫폼". 지금까지 API가 없어 사람이 CLI를 쳐야 했다.

    GET /v1/datasets              카탈로그 목록 (필터·페이징)
    GET /v1/datasets/{id}         상세 — B1 특징·B2 관계·내려받기 경로 포함
    GET /v1/datasets/{id}/jsonld  DCAT JSON-LD
    GET /v1/search                하이브리드 검색 (ADR-010)
    GET /healthz                  상태 확인

실행:
    PYTHONPATH=. uvicorn src.api.main:app --reload --port 8000
    문서: http://localhost:8000/docs

---

## 읽기 전용이다

등록·수정은 D1(운영 기능)의 일이고, 그때는 인증이 먼저 필요하다. 지금 쓰기를
열어 두면 인증 없이 데이터가 바뀐다.

## 내보내지 않는 것

- `dataset_credentials` — API Key 암호문. **어떤 경로로도 나가지 않는다**
- `owner_id` · `party` — 계정 식별자와 내부 권한 메타
- `visibility`가 `PUBLIC`이 아닌 데이터셋은 **기본으로 가린다**(아래 주석 참조)

응답 모양은 `schemas.py`의 허용 목록으로 고정한다 — 컬럼이 늘 때마다 응답이
저절로 넓어지면 언젠가 내보내면 안 되는 것이 섞인다.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api import console, schemas
from src.database.db import get_conn

logger = logging.getLogger(__name__)

app = FastAPI(
    title="써드파티 액티브 메타데이터 카탈로그 API",
    version="0.1.0",
    description=(
        "수집한 비정형 데이터의 카탈로그와 검색을 제공한다. 읽기 전용이다.\n\n"
        "검색은 벡터·키워드 두 채널을 RRF로 결합한다(ADR-010). "
        "결과에 두 채널의 순위가 그대로 실려 나오므로 어느 쪽이 그 문서를 "
        "올렸는지 볼 수 있다."
    ),
)

# ── 내부 개발 콘솔 ──────────────────────────────────────────────────────────
# 프로토타입이다. 실제 포털 화면은 케이웨어 과업이고, 여기 있는 것은 우리가
# 확인·검토·소통하기 위한 것이다(src/api/console.py 머리말).
#
# ⚠️ 콘솔은 **권한을 보지 않는다**(총괄 관리자 시점). 로컬에서만 띄운다.
app.include_router(console.router)

_STATIC = Path(__file__).parent / "static"
if _STATIC.is_dir():
    app.mount("/console", StaticFiles(directory=str(_STATIC), html=True), name="console")


@app.get("/", include_in_schema=False)
def _root():
    """맨손으로 열었을 때 빈 화면 대신 콘솔로 보낸다."""
    return RedirectResponse("/console/")


#: 기본으로 내보낼 공개 범위.
#: ⚠️ 2026-11-04 기준 모든 데이터셋이 `ORG`라, PUBLIC만 내보내면 빈 응답이 된다.
#: 그래서 지금은 ORG까지 허용하되 **인증이 붙는 D1에서 좁혀야 한다**.
#: 여기를 그대로 두고 외부에 열면 조직 내부용 데이터가 나간다.
DEFAULT_VISIBILITY = ("PUBLIC", "ORG")

_COLS = """
    d.dataset_id, d.title, d.description, d.publisher, d.source_type, d.source,
    d.dataset_origin, d.keywords, d.theme, d.category, d.item_count,
    d.temporal_start, d.temporal_end, d.license, d.landing_page,
    d.external_ids, d.updated_at
"""


def _jsonb(value) -> List:
    if value is None:
        return []
    return json.loads(value) if isinstance(value, str) else list(value)


def _summary(row: Dict[str, Any]) -> schemas.DatasetSummary:
    return schemas.DatasetSummary(
        dataset_id=row["dataset_id"], title=row["title"],
        description=row["description"], publisher=row["publisher"],
        source_type=row["source_type"], source=row["source"],
        origin=row["dataset_origin"],
        keywords=_jsonb(row["keywords"]), theme=_jsonb(row["theme"]),
        category=_jsonb(row["category"]), item_count=row["item_count"],
        temporal_start=row["temporal_start"], temporal_end=row["temporal_end"],
        license=row["license"], landing_page=row["landing_page"],
        external_ids=_jsonb(row["external_ids"]), updated_at=row["updated_at"],
    )


def _rows(cur) -> List[Dict[str, Any]]:
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


@app.get("/healthz", tags=["운영"])
def healthz():
    """DB까지 닿는지 확인한다. 프로세스가 살아 있는 것만으로는 부족하다."""
    try:
        cur = get_conn().cursor()
        cur.execute("SELECT count(*) FROM dcat_dataset")
        return {"status": "ok", "datasets": cur.fetchone()[0]}
    except Exception as e:                        # noqa: BLE001
        raise HTTPException(503, f"데이터베이스에 닿지 않는다: {type(e).__name__}")


@app.get("/v1/datasets", response_model=schemas.Page, tags=["카탈로그"])
def list_datasets(
    source_type: Optional[str] = Query(None, description="video · news · blog · shopping_insight · persona_insight"),
    origin: Optional[str] = Query(None, description="admin · user · external"),
    keyword: Optional[str] = Query(None, description="키워드 정확 일치"),
    q: Optional[str] = Query(None, description="제목·설명 부분 일치"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """카탈로그 목록. 외부 포털에서 수집한 것(`origin=external`)도 함께 나온다."""
    where = ["d.visibility = ANY(%(vis)s)"]
    params: Dict[str, Any] = {"vis": list(DEFAULT_VISIBILITY),
                              "limit": limit, "offset": offset}
    if source_type:
        where.append("d.source_type = %(source_type)s")
        params["source_type"] = source_type
    if origin:
        where.append("d.dataset_origin = %(origin)s")
        params["origin"] = origin
    if keyword:
        where.append("d.keywords @> %(kw)s::jsonb")
        params["kw"] = json.dumps([keyword])
    if q:
        # 카탈로그 목록은 제목·설명 부분 일치다. 본문 검색은 /v1/search 쪽이다
        where.append("(d.title ILIKE %(q)s OR d.description ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    cond = " AND ".join(where)

    cur = get_conn().cursor()
    cur.execute(f"SELECT count(*) FROM dcat_dataset d WHERE {cond}", params)
    total = cur.fetchone()[0]
    cur.execute(
        f"SELECT {_COLS} FROM dcat_dataset d WHERE {cond} "
        f"ORDER BY d.updated_at DESC NULLS LAST, d.dataset_id "
        f"LIMIT %(limit)s OFFSET %(offset)s", params)
    return schemas.Page(total=total, limit=limit, offset=offset,
                        items=[_summary(r) for r in _rows(cur)])


@app.get("/v1/datasets/{dataset_id:path}", response_model=schemas.DatasetDetail,
         tags=["카탈로그"])
def get_dataset(dataset_id: str):
    """데이터셋 상세. B1 특징과 B2 관계를 함께 돌려준다.

    `{dataset_id:path}`인 이유 — 식별자가 URN(`urn:naver:news_dataset_38b665`)이라
    콜론이 들어간다. 기본 경로 변환기는 콜론에서 끊는다.
    """
    cur = get_conn().cursor()
    cur.execute(
        f"SELECT {_COLS}, d.accrual_periodicity, d.language, d.spatial, d.rights "
        f"FROM dcat_dataset d WHERE d.dataset_id = %s AND d.visibility = ANY(%s)",
        (dataset_id, list(DEFAULT_VISIBILITY)))
    rows = _rows(cur)
    if not rows:
        raise HTTPException(404, f"없는 데이터셋: {dataset_id}")
    row = rows[0]

    cur.execute(
        "SELECT feature_name, value FROM meta_feature "
        "WHERE dataset_id = %s AND scope = 'dataset'", (dataset_id,))
    features = {n: v for n, v in cur.fetchall()}

    cur.execute(
        "SELECT r.target_dataset_id, t.title, r.relation_type, r.score, r.evidence "
        "FROM dcat_dataset_relation r JOIN dcat_dataset t ON t.dataset_id = r.target_dataset_id "
        "WHERE r.source_dataset_id = %s AND r.status <> 'REJECTED' "
        "ORDER BY r.score DESC LIMIT 10", (dataset_id,))
    relations = [{"dataset_id": a, "title": b, "relation_type": c,
                  "score": round(float(d), 4), "evidence": e}
                 for a, b, c, d, e in cur.fetchall()]

    detail = schemas.DatasetDetail(
        **_summary(row).model_dump(),
        accrual_periodicity=row["accrual_periodicity"], language=row["language"],
        spatial=row["spatial"], rights=row["rights"],
        features=features, relations=relations,
        downloads={"jsonld": f"/v1/datasets/{dataset_id}/jsonld"},
    )
    return detail


@app.get("/v1/datasets/{dataset_id:path}/jsonld", tags=["카탈로그"])
def get_jsonld(dataset_id: str):
    """DCAT JSON-LD. 오브젝트 스토리지에 내보낸 것과 같은 형식이다."""
    cur = get_conn().cursor()
    cur.execute("SELECT 1 FROM dcat_dataset WHERE dataset_id = %s AND visibility = ANY(%s)",
                (dataset_id, list(DEFAULT_VISIBILITY)))
    if not cur.fetchone():
        raise HTTPException(404, f"없는 데이터셋: {dataset_id}")
    try:
        from src.storage import jsonld_export
        doc = jsonld_export.build_dataset_jsonld(dataset_id)
    except AttributeError:
        raise HTTPException(501, "이 데이터셋 종류는 JSON-LD 내보내기가 아직 없다")
    except Exception as e:                        # noqa: BLE001
        logger.warning("JSON-LD 생성 실패 %s: %s", dataset_id, e)
        raise HTTPException(500, "JSON-LD를 만들지 못했다")
    return JSONResponse(doc, media_type="application/ld+json")


@app.get("/v1/discover", response_model=schemas.DiscoverResponse, tags=["검색"])
def discover(
    purpose: str = Query(..., min_length=2,
                         description="하려는 일을 자연어로. 예: 암 환자 교육 자료를 만들고 싶다"),
    limit: int = Query(10, ge=1, le=30),
    seeds: int = Query(5, ge=1, le=20, description="씨앗으로 쓸 검색 결과 수"),
):
    """활용 목적으로 **데이터셋 묶음**을 만든다 (C2).

    검색은 "맞는 것 하나하나"를 준다. 그런데 사람이 데이터를 찾는 이유는 대개
    무언가를 하기 위해서이고, 그러려면 **함께 쓸 것들**이 필요하다.

        목적 → 카탈로그 검색(C1) → 관계 1-hop 확장(B3) → 묶음

    각 항목에 **어떻게 도달했는지**가 `paths`로 실린다. 직접 검색됐는지,
    무엇을 통해 어떤 관계로 왔는지 — 근거가 없으면 묶음을 믿을 수도,
    틀린 것을 걸러낼 수도 없다.
    """
    from src.search import discovery as disc

    r = disc.discover(purpose, top_k=limit, seeds=seeds)
    return schemas.DiscoverResponse(
        purpose=r["purpose"], seeds=r["seeds"], note=r.get("note"),
        bundle=[
            schemas.BundleItem(
                dataset_id=b["dataset_id"], title=b["title"], score=b["score"],
                reached_by=b["reached_by"], why=disc.explain(b),
                paths=[schemas.BundlePath(**{k: v for k, v in p.items()
                                             if k in schemas.BundlePath.model_fields})
                       for p in b["paths"]],
            )
            for b in r["bundle"]
        ],
    )


@app.get("/v1/search", response_model=schemas.SearchResponse, tags=["검색"])
def search(
    q: str = Query(..., min_length=1, description="자연어 질의"),
    source: str = Query("video", description="video · news · blog · dataset"),
    limit: int = Query(10, ge=1, le=50),
    explain: bool = Query(False, description="질의 토큰과 최희귀어 판정을 함께 돌려준다"),
):
    """하이브리드 검색 — 벡터 + 키워드를 RRF로 결합한다(ADR-010).

    두 채널의 순위가 결과에 그대로 실린다. `vec_rank`/`kw_rank`가 null이면
    그 채널에는 안 걸렸다는 뜻이고, 결과를 해석할 때 이것이 필요하다.
    """
    from src.search import hybrid, tokenize

    if source not in hybrid.SOURCES:
        raise HTTPException(400, f"알 수 없는 source: {source} "
                                 f"(가능: {sorted(hybrid.SOURCES)})")
    try:
        rows = hybrid.search(q, source, limit)
    except tokenize.TokenizerMismatch as e:
        # 조용히 빈 결과를 주면 "결과가 없다"로 오해한다. 분명히 알린다
        raise HTTPException(503, f"검색 색인이 현재 토크나이저와 맞지 않는다: {e}")

    ai: Dict[Any, Dict[str, Any]] = {}
    if source == "video" and rows:
        cur = get_conn().cursor()
        cur.execute(
            "SELECT meta_id, ai_summary, ai_keywords FROM meta_video_ai "
            "WHERE meta_id = ANY(%s) AND status = 'ok'", ([r["id"] for r in rows],))
        ai = {a: {"summary": b, "keywords": c or []} for a, b, c in cur.fetchall()}

    hits = [
        schemas.SearchHit(
            id=str(r["id"]), title=r["title"], subtitle=r["subtitle"], source=source,
            rrf=float(r["rrf"]) if r["rrf"] is not None else None,
            vec_rank=r["vec_rank"], kw_rank=r["kw_rank"],
            ai_summary=(ai.get(r["id"]) or {}).get("summary"),
            ai_keywords=(ai.get(r["id"]) or {}).get("keywords", []),
        )
        for r in rows
    ]
    out = schemas.SearchResponse(query=q, source=source, total=len(hits), hits=hits)
    if explain:
        out.tokens = tokenize.tokens(q)
        out.rarest_token = hybrid.rarest_token_df(q, source)
    return out
