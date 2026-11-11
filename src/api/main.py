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
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import anyio.to_thread
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse

from src.api import auth, console, lineage, manage, modules, my, schemas, structured, usage
from src.api.access import ensure_visible, item_dataset_map, visible_clause, visible_ids
from src.api.auth import current_user, optional_user, User
from src.api.db_scope import ReleaseDbRoute
from src.common.category_taxonomy import PRIVATE_FEATURES
from src.common.config import get_env
from src.database.db import get_conn

logger = logging.getLogger(__name__)

#: 동기 엔드포인트를 돌리는 스레드 수 상한. DB 커넥션은 스레드마다 1개라(src/database/db.py)
#: 이 값이 곧 API가 여는 커넥션 상한이다. anyio 기본값(40)이면 DB max_connections(100)의
#: 40%를 API 혼자 쓸 수 있다 — 수집·와이즈넛 적재와 같은 DB를 쓴다.
API_THREADS = int(get_env("API_THREADS", "10"))


@asynccontextmanager
async def _lifespan(_app):
    anyio.to_thread.current_default_thread_limiter().total_tokens = API_THREADS
    yield


app = FastAPI(
    lifespan=_lifespan,
    title="써드파티 액티브 메타데이터 카탈로그 API",
    version="0.1.0",
    description=(
        "수집한 비정형 데이터의 카탈로그와 검색을 제공합니다. 읽기 전용입니다.\n\n"
        "검색은 벡터·키워드 두 채널을 RRF로 결합합니다(ADR-010). "
        "결과에 두 채널의 순위가 함께 나오므로 어느 채널이 해당 문서를 "
        "상위로 올렸는지 확인할 수 있습니다."
    ),
)
# 요청이 끝나면 그 요청이 연 DB 트랜잭션을 닫는다(src/api/db_scope.py). 아래 @app.get 라우트용 —
# 하위 라우터들은 각자 APIRouter(route_class=ReleaseDbRoute)로 만든다.
app.router.route_class = ReleaseDbRoute

# ── 포털·관리자 페이지용 API (/v1/console/…) ─────────────────────────────────
# 이름은 예전 내부 콘솔에서 왔다. 콘솔 화면(src/api/static)은 2026-11-09 지웠고
# (NEXT_STEPS 결정 9) 지금은 포털(portal-mockup)이 이 API를 쓴다 — 이름을 바꾸려면 포털과 함께.
#
# ⚠️ **권한을 보지 않는다**(총괄 관리자 시점). 로컬에서만 띄운다.
# ⚠️ manage를 **먼저** 넣는다. console의 상세 `GET /datasets/{dataset_id:path}`는 슬래시까지
# 삼키므로, 뒤에 오는 `…/trend`·`…/package`·`…/run`을 식별자의 일부로 읽는다
# (main.py `/jsonld`가 그렇게 죽어 있었다 — tests/test_api_routing.py).
app.include_router(auth.router)
app.include_router(manage.router)
app.include_router(my.router)
app.include_router(structured.router)
app.include_router(usage.router)
app.include_router(lineage.router)
app.include_router(modules.router)
app.include_router(console.router)


@app.get("/", include_in_schema=False)
def _root():
    """맨손으로 열었을 때 빈 화면 대신 API 문서로 보낸다. 화면은 포털에 있다."""
    return RedirectResponse("/docs")


#: 공개 범위 — 2026-11-10 시제품 로그인(ADR-021)으로 **비로그인은 PUBLIC만** 본다.
#: 그 전에는 인증이 없어 ORG까지 내보냈다(2026-11-06 기준 PUBLIC 40 · ORG 15).
#: 로그인하면 기관·소유자 기준으로 더 본다 — 규칙은 src/api/access.py 한 곳.

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


@app.get("/v1/packaging/public-key", tags=["패키지"])
def packaging_public_key():
    """신뢰 패키지 서명 공개키(Ed25519)와 지문입니다.

    받은 패키지를 `package_dataset.py verify --pubkey <이 키>`로 검증하면 서명이 이 서버에서
    만들어졌는지까지 확인할 수 있습니다. 서버에 공개키 서명이 설정되지 않았으면 404입니다.
    """
    from src.packaging import signing
    try:
        key = signing.private_key_from_env()
    except signing.SigningError:
        key = None
    if key is None:
        raise HTTPException(404, "공개키 서명이 설정되지 않았습니다")
    pub = key.public_key()
    return {"algorithm": signing.ALGORITHM, "fingerprint": signing.fingerprint(pub),
            "public_key_pem": signing.public_pem(pub).decode("ascii")}


#: 포털 검증에 올릴 수 있는 패키지 크기 상한
VERIFY_MAX_BYTES = 200 * 1024 * 1024


@app.post("/v1/packaging/verify", tags=["패키지"])
async def packaging_verify(file: UploadFile = File(..., description="받은 신뢰 패키지(zip)"),
                           user: User = Depends(current_user)):
    """받은 신뢰 패키지를 이 포털의 **공식 공개키**로 검증합니다(로그인 필요).

    서명(출처), 파일 체크섬(무결성), 손상 블록 복원 가능 여부, 만든 쪽의 점검 결과를 알려 줍니다.
    파일은 검증 뒤 바로 지웁니다. 암호화 패키지(*.zip.enc)는 먼저 복호화해야 합니다.
    """
    import tempfile
    from pathlib import Path

    from src.packaging import signing, verify as V

    try:
        key = signing.private_key_from_env()
    except signing.SigningError:
        key = None
    pub = signing.public_pem(key.public_key()) if key else None
    with tempfile.TemporaryDirectory(prefix="verify-") as tmp:
        path = Path(tmp) / "package.zip"
        size = 0
        with open(path, "wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > VERIFY_MAX_BYTES:
                    raise HTTPException(413, f"{VERIFY_MAX_BYTES // 1024 // 1024}MB까지 검증할 수 있습니다")
                fh.write(chunk)
        r = V.verify_package(path, pubkey_pem=pub)
    m = r.manifest or {}
    q = m.get("quality") or {}
    return {
        "ok": r.ok, "signature_ok": r.signature_ok, "files_ok": r.files_ok,
        "signatures": r.signatures,
        "signer_trusted": r.signer_trusted, "signer_fingerprint": r.signer_fingerprint,
        "server_key_configured": pub is not None,
        "problems": r.problems[:20], "repairable": r.repairable, "unrepairable": r.unrepairable,
        "manifest": {k: m.get(k) for k in ("dataset_id", "version", "created_at", "manifest_version",
                                           "file_count", "total_bytes")} if m else None,
        "source_title": (m.get("source") or {}).get("title"),
        "quality": {"passed": q.get("passed"), "failed": q.get("failed")} if q else None,
        "collection_runs": len(((m.get("lineage") or {}).get("collection_runs")) or []),
    }


@app.get("/healthz", tags=["운영"])
def healthz():
    """DB까지 닿는지 확인한다. 프로세스가 살아 있는 것만으로는 부족하다."""
    try:
        cur = get_conn().cursor()
        cur.execute("SELECT count(*) FROM dcat_dataset")
        return {"status": "ok", "datasets": cur.fetchone()[0]}
    except Exception as e:                        # noqa: BLE001
        logger.warning("헬스 체크 DB 실패: %s", type(e).__name__)
        raise HTTPException(503, "데이터베이스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요")


@app.get("/v1/datasets", response_model=schemas.Page, tags=["카탈로그"])
def list_datasets(
    source_type: Optional[str] = Query(None, description="video · news · blog · shopping_insight · persona_insight"),
    origin: Optional[str] = Query(None, description="admin · user · external"),
    keyword: Optional[str] = Query(None, description="키워드 정확 일치"),
    q: Optional[str] = Query(None, description="제목·설명 부분 일치"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(optional_user),
):
    """카탈로그 목록. 외부 포털에서 수집한 것(`origin=external`)도 함께 나온다."""
    vis, vparams = visible_clause(user, "d.")
    where = [vis]
    params: Dict[str, Any] = {"limit": limit, "offset": offset, **vparams}
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


# ⚠️ **이 라우트는 상세(`{dataset_id:path}`)보다 먼저 선언해야 한다.** `:path`는
# 슬래시까지 삼키므로, 상세가 먼저 있으면 `…/jsonld`를 식별자의 일부로 읽어 404를 낸다.
# 2026-11-04 포털을 붙이다 발견했다 — 그 전까지 이 엔드포인트는 한 번도 닿은 적이 없고,
# 상세 응답의 `downloads.jsonld`는 죽은 링크였다.
@app.get("/v1/datasets/{dataset_id:path}/jsonld", tags=["카탈로그"])
def get_jsonld(dataset_id: str, user: Optional[User] = Depends(optional_user),
               x_usage_session: Optional[str] = Header(None)):
    """DCAT JSON-LD. 오브젝트 스토리지에 내보낸 것과 같은 형식이다."""
    ensure_visible(get_conn().cursor(), dataset_id, user)
    # `except AttributeError`로 501을 내던 분기를 걷어냈다. 그게 존재하지 않는 함수를
    # 부르는 프로그래밍 오류를 "미지원"으로 보이게 해, 모든 요청이 실패하는데도 몰랐다.
    try:
        from src.storage import jsonld_export
        doc = jsonld_export.build_dataset_jsonld(dataset_id)
    except Exception as e:                        # noqa: BLE001
        logger.warning("JSON-LD 생성 실패 %s: %s", dataset_id, e)
        raise HTTPException(500, "JSON-LD를 생성하지 못했습니다")
    usage.record_server_event("download", dataset_id, user, x_usage_session, detail="jsonld")
    return JSONResponse(doc, media_type="application/ld+json")


@app.get("/v1/datasets/{dataset_id:path}", response_model=schemas.DatasetDetail,
         tags=["카탈로그"])
def get_dataset(dataset_id: str, user: Optional[User] = Depends(optional_user)):
    """데이터셋 상세. B1 특징과 B2 관계를 함께 돌려준다.

    `{dataset_id:path}`인 이유 — 식별자가 URN(`urn:naver:news_dataset_38b665`)이라
    콜론이 들어간다. 기본 경로 변환기는 콜론에서 끊는다.
    """
    cur = get_conn().cursor()
    vis, vparams = visible_clause(user, "d.")
    cur.execute(
        f"SELECT {_COLS}, d.accrual_periodicity, d.language, d.spatial, d.rights "
        f"FROM dcat_dataset d WHERE d.dataset_id = %(_id)s AND {vis}",
        {**vparams, "_id": dataset_id})
    rows = _rows(cur)
    if not rows:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    row = rows[0]

    cur.execute(
        "SELECT feature_name, value FROM meta_feature "
        "WHERE dataset_id = %s AND scope = 'dataset' AND feature_name <> ALL(%s)",
        (dataset_id, PRIVATE_FEATURES))
    features = {n: v for n, v in cur.fetchall()}

    cur.execute(
        "SELECT r.target_dataset_id, t.title, r.relation_type, r.score, r.evidence "
        "FROM dcat_dataset_relation r JOIN dcat_dataset t ON t.dataset_id = r.target_dataset_id "
        "WHERE r.source_dataset_id = %s AND r.status <> 'REJECTED' "
        "ORDER BY r.score DESC LIMIT 10", (dataset_id,))
    rel_rows = cur.fetchall()
    ok = visible_ids(cur, [r[0] for r in rel_rows], user)
    relations = [{"dataset_id": a, "title": b, "relation_type": c,
                  "score": round(float(d), 4), "evidence": e}
                 for a, b, c, d, e in rel_rows if a in ok]

    detail = schemas.DatasetDetail(
        **_summary(row).model_dump(),
        accrual_periodicity=row["accrual_periodicity"], language=row["language"],
        spatial=row["spatial"], rights=row["rights"],
        features=features, relations=relations,
        downloads={"jsonld": f"/v1/datasets/{dataset_id}/jsonld"},
    )
    return detail


@app.get("/v1/discover", response_model=schemas.DiscoverResponse, tags=["검색"])
def discover(
    purpose: str = Query(..., min_length=2,
                         description="하려는 일을 자연어로. 예: 암 환자 교육 자료를 만들고 싶다"),
    limit: int = Query(10, ge=1, le=30),
    seeds: int = Query(5, ge=1, le=20, description="씨앗으로 쓸 검색 결과 수"),
    user: Optional[User] = Depends(optional_user),
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

    r = disc.discover(purpose, top_k=limit * 2, seeds=seeds, user=user)
    # 볼 수 없는 데이터셋은 씨앗·묶음에서 뺀다(넉넉히 받아 limit을 채운다).
    # 근거(paths)의 경유 데이터셋도 같다 — 보이는 항목이라도 숨은 데이터셋을 거쳐 왔다면
    # 그 경로는 지우고(제목이 새지 않게), 남는 경로가 없으면 항목째 뺀다.
    ids = ([x["dataset_id"] for x in r["seeds"]] + [b["dataset_id"] for b in r["bundle"]]
           + [p["via"] for b in r["bundle"] for p in b["paths"] if p.get("via")])
    ok = visible_ids(get_conn().cursor(), ids, user)
    r["seeds"] = [x for x in r["seeds"] if x["dataset_id"] in ok]
    bundle = []
    for b in r["bundle"]:
        if b["dataset_id"] not in ok:
            continue
        paths = [p for p in b["paths"] if p["how"] == "search" or p.get("via") in ok]
        if paths:
            bundle.append({**b, "paths": paths})
    r["bundle"] = bundle[:limit]
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


def _like(text: str) -> str:
    """LIKE 패턴용 이스케이프(기본 이스케이프 문자 \\)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.get("/v1/search/suggest", tags=["검색"])
def search_suggest(q: str = Query(..., min_length=1, max_length=50, description="입력 중인 검색어"),
                   limit: int = Query(8, ge=1, le=20),
                   user: Optional[User] = Depends(optional_user)):
    """검색어 자동완성 — 볼 수 있는 데이터셋의 **제목·키워드**에서 고른다.

    검색 기록을 쓰지 않는다(개인정보 안내: 검색어는 저장하지 않는다). 그래서 '인기 검색어'는 만들지 않았다.
    앞부분이 일치하는 것을 먼저, 그다음 중간에 들어간 것을 보여 준다.
    """
    text = q.strip()
    if not text:
        return {"query": q, "items": []}
    cond, params = visible_clause(user, "d.")
    params = {**params, "pre": _like(text.lower()) + "%", "any": "%" + _like(text.lower()) + "%", "lim": limit}
    cur = get_conn().cursor()
    cur.execute(f"""SELECT d.dataset_id, d.title, (lower(d.title) LIKE %(pre)s) AS prefix
                    FROM dcat_dataset d
                    WHERE {cond} AND lower(d.title) LIKE %(any)s
                    ORDER BY prefix DESC, length(d.title), d.title LIMIT %(lim)s""", params)
    titles = [{"text": t, "kind": "dataset", "dataset_id": i} for i, t, _ in cur.fetchall()]
    cur.execute(f"""SELECT kw, count(*) AS n, bool_or(lower(kw) LIKE %(pre)s) AS prefix
                    FROM dcat_dataset d, jsonb_array_elements_text(coalesce(d.keywords, '[]'::jsonb)) AS kw
                    WHERE {cond} AND lower(kw) LIKE %(any)s
                    GROUP BY kw ORDER BY prefix DESC, n DESC, kw LIMIT %(lim)s""", params)
    seen = {x["text"].lower() for x in titles}
    keywords = [{"text": k, "kind": "keyword", "datasets": n} for k, n, _ in cur.fetchall() if k.lower() not in seen]
    items = (keywords[: max(2, limit // 2)] + titles)[:limit] if titles else keywords[:limit]
    return {"query": q, "items": items}


@app.get("/v1/search", response_model=schemas.SearchResponse, tags=["검색"])
def search(
    q: str = Query(..., min_length=1, description="자연어 질의"),
    source: str = Query("video", description="video · news · blog · dataset"),
    limit: int = Query(10, ge=1, le=50),
    explain: bool = Query(False, description="질의 토큰과 최희귀어 판정을 함께 돌려준다"),
    synonyms: bool = Query(True, description="동의어를 키워드 채널에 더한다(configs/synonyms.yaml)"),
    title_weight: float = Query(0.0, ge=0, le=2, description="제목 일치 채널 가중치(0=끔, 평가 근거는 hybrid.py)"),
    user: Optional[User] = Depends(optional_user),
):
    """하이브리드 검색 — 벡터 + 키워드를 RRF로 결합한다(ADR-010).

    두 채널의 순위가 결과에 그대로 실린다. `vec_rank`/`kw_rank`가 null이면
    그 채널에는 안 걸렸다는 뜻이고, 결과를 해석할 때 이것이 필요하다.
    """
    from src.search import hybrid, tokenize

    if source not in hybrid.SOURCES:
        raise HTTPException(400, f"지원하지 않는 검색 대상입니다: {source} "
                                 f"(가능한 값: {sorted(hybrid.SOURCES)})")
    try:
        rows = hybrid.search(q, source, limit * 2, expand_synonyms=synonyms, title_weight=title_weight)
    except tokenize.TokenizerMismatch as e:
        # 조용히 빈 결과를 주면 "결과가 없다"로 오해한다. 분명히 알린다
        logger.error("검색 색인·토크나이저 불일치: %s", e)
        raise HTTPException(503, "검색 색인을 다시 만들어야 합니다. 관리자에게 문의해 주세요")
    # 볼 수 없는 데이터셋의 결과는 뺀다(넉넉히 받아 limit을 채운다)
    cur0 = get_conn().cursor()
    owner = item_dataset_map(cur0, source, [r["id"] for r in rows])
    ok = visible_ids(cur0, owner.values(), user)
    rows = [r for r in rows if owner.get(r["id"]) in ok][:limit]

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
            vec_rank=r["vec_rank"], kw_rank=r["kw_rank"], title_rank=r.get("title_rank"),
            ai_summary=(ai.get(r["id"]) or {}).get("summary"),
            ai_keywords=(ai.get(r["id"]) or {}).get("keywords", []),
        )
        for r in rows
    ]
    out = schemas.SearchResponse(query=q, source=source, total=len(hits), hits=hits,
                                 expansions=hybrid.expansions(q) if synonyms else {})
    if explain:
        out.tokens = tokenize.tokens(q)
        out.rarest_token = hybrid.rarest_token_df(q, source)
    return out
