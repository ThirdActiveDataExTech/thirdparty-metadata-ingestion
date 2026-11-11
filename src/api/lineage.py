"""데이터 리니지 — 원천에서 제공까지 한 데이터셋이 거친 경로 (C5 · 4차년도 "데이터 리니지").

연구계획서 4차년도: "데이터 히스토리와 데이터 리니지 정보 등을 함께 ... 데이터의 수정 사항을 파악".
새로 기록하지 않는다 — 이미 쌓이는 기록을 모아 단계별로 보여 준다.

    원천        dcat_dataset(발행처·원천 주소·라이선스)
    수집        dcat_provenance(실행 이력 — 누가·언제·결과·행 수), 수집 방식(파이프라인·외부 연합·현장 번들)
    저장        data_registry(아이템 테이블·행 수·원본 저장 위치), meta_*
    가공        *_vec(청크·임베딩), meta_video_ai(AI 요약), meta_feature(특징), dcat_dataset_relation(관계)
    제공        dataset_usage_event(조회·내려받기 — 형식별)

볼 수 있는 사람에게만 보인다. 내부 저장 위치(테이블·오브젝트 경로)는 관리자에게만, 오류 원문은 누구에게도 내지 않는다.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from psycopg2 import errors as pg_errors

from src.api.access import ensure_visible
from src.api.auth import User, optional_user
from src.api.db_scope import ReleaseDbRoute
from src.database.db import get_conn

router = APIRouter(prefix="/v1", tags=["리니지"], route_class=ReleaseDbRoute)

#: 원천 유형 → (아이템 테이블, 벡터 테이블). 아이템 단위 가공이 있는 것만
ITEM_TABLES = {"video": ("meta_video", "meta_video_vec"), "news": ("meta_news", "meta_news_vec"),
               "blog": ("meta_blog", "meta_blog_vec")}
COLLECTOR = {"video": "YouTube Data API 수집 파이프라인", "news": "네이버 뉴스 검색 API 수집 파이프라인",
             "blog": "네이버 블로그 검색 API 수집 파이프라인", "shopping_insight": "네이버 데이터랩 쇼핑인사이트 수집 파이프라인",
             "persona_insight": "네이버 데이터랩 검색어 트렌드(연령·성별) 수집 파이프라인",
             "external_catalog": "외부 포털 메타데이터 연합(CKAN·SDMX)"}


def _trigger_kind(t: Optional[str]) -> str:
    t = t or ""
    if t.startswith("agent:"):
        return "현장 수집 번들"
    if "scheduler" in t:
        return "정기 수집"
    if t.startswith("manual") or t in ("console", "portal") or "console" in t:
        return "수동 실행"
    return t or "기록 없음"


def _safe_count(cur, sql: str, args) -> Optional[int]:
    try:
        cur.execute(sql, args)
        return cur.fetchone()[0]
    except (pg_errors.UndefinedTable, pg_errors.UndefinedColumn):
        cur.connection.rollback()
        return None


def build(cur, dataset_id: str, admin: bool) -> Dict[str, Any]:
    cur.execute("SELECT title, source_type, dataset_origin, publisher, source, landing_page, license, "
                "       created_at, updated_at FROM dcat_dataset WHERE dataset_id = %s", (dataset_id,))
    title, st, origin, pub, src, landing, lic, created, updated = cur.fetchone()
    cur.execute("SELECT pg_meta_table, s3_raw_prefix, s3_jsonld_prefix, item_count, last_collected_at, "
                "       next_collect_at, status, source_schema_changed_at FROM data_registry WHERE dataset_id = %s",
                (dataset_id,))
    reg = cur.fetchone()

    cur.execute("SELECT activity_type, triggered_by, started_at, ended_at, status, rows_affected "
                "FROM dcat_provenance WHERE dataset_id = %s ORDER BY started_at DESC", (dataset_id,))
    runs = cur.fetchall()
    kinds = Counter(_trigger_kind(r[1]) for r in runs)
    ok = [r for r in runs if r[4] == "success"]

    stages: List[Dict[str, Any]] = []
    stages.append({"key": "source", "label": "원천", "items": [
        {"label": "발행처", "value": pub}, {"label": "원천", "value": src},
        {"label": "원천 주소", "value": landing, "link": bool(landing)},
        {"label": "라이선스", "value": lic}]})
    stages.append({"key": "collect", "label": "수집", "items": [
        {"label": "수집 방식", "value": COLLECTOR.get(st, st)},
        {"label": "실행", "value": f"{len(runs)}회 (성공 {len(ok)} · 실패 {sum(1 for r in runs if r[4] == 'failure')})"},
        {"label": "실행 주체", "value": " · ".join(f"{k} {n}" for k, n in kinds.most_common()) or "기록 없음"},
        {"label": "마지막 성공", "value": ok[0][3].isoformat() if ok and ok[0][3] else None},
        {"label": "다음 예정", "value": reg[5].isoformat() if reg and reg[5] else None},
        {"label": "원천 형식 변화", "value": reg[7].isoformat() if reg and reg[7] else "감지 기록 없음"}]})

    store_items = [{"label": "아이템", "value": f"{reg[3]:,}건" if reg and reg[3] is not None else None}]
    if admin and reg:
        store_items += [{"label": "아이템 테이블", "value": reg[0]}, {"label": "원본 저장 위치", "value": reg[1]},
                        {"label": "JSON-LD 저장 위치", "value": reg[2]}]
    if st == "external_catalog":
        store_items = [{"label": "저장", "value": "카탈로그 메타데이터만(원본 데이터는 원천에 있음)"}]
    stages.append({"key": "store", "label": "저장", "items": store_items})

    process: List[Dict[str, Any]] = []
    if st in ITEM_TABLES:
        items_t, vec_t = ITEM_TABLES[st]
        n = _safe_count(cur, f"SELECT count(*) FROM {vec_t} v JOIN {items_t} m ON m.id = v.meta_id "
                             f"WHERE m.dataset_id = %s", (dataset_id,))
        process.append({"label": "검색 색인(청크·임베딩)", "value": f"{n:,}개" if n is not None else None})
        if st == "video":
            n = _safe_count(cur, "SELECT count(*) FROM meta_video_ai a JOIN meta_video m ON m.id = a.meta_id "
                                 "WHERE m.dataset_id = %s AND a.status = 'ok'", (dataset_id,))
            process.append({"label": "AI 요약·키워드", "value": f"{n:,}건" if n is not None else None})
    n = _safe_count(cur, "SELECT count(*) FROM dcat_dataset_vec WHERE dataset_id = %s", (dataset_id,))
    process.append({"label": "데이터셋 설명 색인", "value": f"{n:,}개" if n is not None else None})
    cur.execute("SELECT count(*), max(computed_at) FROM meta_feature WHERE dataset_id = %s AND scope = 'dataset'",
                (dataset_id,))
    nf, last_f = cur.fetchone()
    process.append({"label": "특징 분석", "value": f"{nf}종" + (f" (최근 {last_f.date().isoformat()})" if last_f else "")})
    cur.execute("SELECT relation_type, count(*) FROM dcat_dataset_relation "
                "WHERE source_dataset_id = %s OR target_dataset_id = %s GROUP BY 1 ORDER BY 2 DESC",
                (dataset_id, dataset_id))
    rel = cur.fetchall()
    process.append({"label": "관계", "value": " · ".join(f"{t} {c}" for t, c in rel) or "없음"})
    stages.append({"key": "process", "label": "가공", "items": process})

    deliver: List[Dict[str, Any]] = []
    try:
        cur.execute("SELECT event_type, coalesce(detail, ''), count(*) FROM dataset_usage_event "
                    "WHERE dataset_id = %s AND origin <> 'api' GROUP BY 1, 2", (dataset_id,))
        usage = cur.fetchall()
        views = sum(n for t, _, n in usage if t == "view")
        dl = {d: n for t, d, n in usage if t == "download"}
        label = {"package": "신뢰 패키지", "jsonld": "JSON-LD", "hf": "허깅페이스 형식"}
        deliver.append({"label": "조회", "value": f"{views:,}회"})
        deliver.append({"label": "내려받기", "value": " · ".join(f"{label.get(d, d)} {n}" for d, n in dl.items()) or "없음"})
    except pg_errors.UndefinedTable:
        cur.connection.rollback()
        deliver.append({"label": "활용 기록", "value": "준비되지 않았습니다"})
    deliver.append({"label": "제공 형식", "value": "OpenAPI · JSON-LD · 신뢰 패키지 · 허깅페이스 형식(반출 허용 시)"})
    stages.append({"key": "deliver", "label": "제공", "items": deliver})

    return {"dataset_id": dataset_id, "title": title, "source_type": st, "origin": origin,
            "created_at": created.isoformat() if created else None,
            "updated_at": updated.isoformat() if updated else None,
            "stages": stages,
            "recent_runs": [{"activity": a, "trigger": _trigger_kind(t), "started_at": s.isoformat() if s else None,
                             "ended_at": e.isoformat() if e else None, "status": stt, "rows": n}
                            for a, t, s, e, stt, n in runs[:10]]}


@router.get("/datasets/{dataset_id:path}/lineage")
def lineage(dataset_id: str, user: Optional[User] = Depends(optional_user)):
    """한 데이터셋이 원천에서 제공까지 거친 단계(원천·수집·저장·가공·제공)와 최근 수집 실행 10회."""
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    return build(cur, dataset_id, admin=bool(user and user.is_admin))
