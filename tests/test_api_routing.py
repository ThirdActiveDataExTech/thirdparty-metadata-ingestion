"""라우트가 의도한 함수에 닿는가 — DB 없이 라우팅만 본다.

2026-11-04 포털을 붙이다 발견했다. `/v1/datasets/{id}/jsonld`가 상세 라우트
`/v1/datasets/{dataset_id:path}`보다 **뒤에** 선언돼 있었고, `:path`가 슬래시까지
삼키는 바람에 `…/jsonld`를 식별자의 일부로 읽어 **한 번도 닿은 적이 없었다.**
상세 응답의 `downloads.jsonld`는 죽은 링크였다.

함수를 직접 부르는 테스트로는 이런 고장이 절대 안 잡힌다. 그래서 URL에서 출발한다.
"""

import pytest
from starlette.routing import Match

from src.api.main import app


def _endpoint(path: str):
    scope = {"type": "http", "path": path, "method": "GET", "root_path": ""}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.endpoint.__name__
    return None


URN = "urn:naver:blog_dataset_256a67"


@pytest.mark.parametrize("path,expected", [
    (f"/v1/datasets/{URN}", "get_dataset"),
    (f"/v1/datasets/{URN}/jsonld", "get_jsonld"),
    ("/v1/console/datasets", "catalog"),
    (f"/v1/console/datasets/{URN}", "catalog_detail"),
    (f"/v1/console/datasets/{URN}/features", "features"),
    (f"/v1/console/datasets/{URN}/items", "items"),
    (f"/v1/console/datasets/{URN}/graph", "graph"),
    (f"/v1/console/datasets/{URN}/status", "dataset_status"),
    # 외부 연합분 식별자는 콜론이 더 많다
    ("/v1/console/datasets/urn:ckan:open-canada-ca:04079572/graph", "graph"),
])
def test_하위_경로가_상세에_삼켜지지_않는다(path, expected):
    assert _endpoint(path) == expected


def test_JSON_LD는_업로드_없이_만든다(monkeypatch):
    """GET 요청이 오브젝트 스토리지를 고치면 안 된다."""
    from src.storage import jsonld_export as J

    monkeypatch.setattr(J, "_fetch_dataset_context", lambda ds: {
        "dataset_id": ds, "source_type": "external_catalog", "title": "t",
        "description": "d", "publisher": "p", "license": None, "keywords": [],
        "external_ids": [], "accrual_periodicity": None, "temporal_start": None,
        "temporal_end": None, "status": None, "item_count": None, "row_count": None,
        "last_collected_at": None, "next_collect_at": None})
    monkeypatch.setattr(J.s3_client, "upload_json",
                        lambda *a, **k: pytest.fail("GET이 업로드를 했다"))
    doc = J.build_dataset_jsonld("urn:ckan:x")
    # 빌더가 없는 외부 연합분은 카탈로그 기본 정보만 담는다
    assert doc["@type"] == "dcat:Dataset" and doc["@id"] == "urn:ckan:x"
    assert doc["mi:activeMetadata"]["status"] is None
