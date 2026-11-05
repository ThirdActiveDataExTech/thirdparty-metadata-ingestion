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


def _endpoint_m(path: str, method: str):
    scope = {"type": "http", "path": path, "method": method, "root_path": ""}
    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route.endpoint.__name__
    return None


@pytest.mark.parametrize("method,path,expected", [
    ("GET", f"/v1/console/datasets/{URN}/trend", "trend"),
    ("GET", f"/v1/console/datasets/{URN}/package", "package"),
    ("GET", f"/v1/console/datasets/{URN}/run", "run_status"),
    ("POST", f"/v1/console/datasets/{URN}/run", "run_now"),
    ("POST", "/v1/console/datasets/check", "check_registration"),
    ("POST", "/v1/console/datasets", "register"),
    ("PATCH", f"/v1/console/datasets/{URN}", "update"),
    ("DELETE", f"/v1/console/datasets/{URN}", "delete"),
    ("GET", f"/v1/console/datasets/{URN}", "catalog_detail"),
])
def test_관리_라우트가_상세에_삼켜지지_않는다(method, path, expected):
    assert _endpoint_m(path, method) == expected


class TestYoutubeTargets:
    """사용자는 채널 ID를 모른다 — URL·@핸들을 받아 서버가 바꾼다(등록 시나리오 §2.2)."""

    @pytest.mark.parametrize("raw,kind,value", [
        ("https://www.youtube.com/channel/UCltyil2FaQZZ4kUNinKkKmw", "channel", "UCltyil2FaQZZ4kUNinKkKmw"),
        ("UCltyil2FaQZZ4kUNinKkKmw", "channel", "UCltyil2FaQZZ4kUNinKkKmw"),
        ("https://www.youtube.com/watch?v=Tiz771v_iLY", "video", "Tiz771v_iLY"),
        ("https://youtu.be/Tiz771v_iLY", "video", "Tiz771v_iLY"),
        ("https://www.youtube.com/watch?list=x&v=Tiz771v_iLY", "video", "Tiz771v_iLY"),
        ("https://www.youtube.com/@SKhynix", "handle", "@SKhynix"),
        ("@서울아산병원", "handle", "@서울아산병원"),
    ])
    def test_해석(self, raw, kind, value):
        from src.api.manage import parse_youtube_target
        p = parse_youtube_target(raw)
        assert (p["kind"], p["value"]) == (kind, value)

    def test_Shorts는_거른다(self):
        from src.api.manage import parse_youtube_target
        assert parse_youtube_target("https://youtube.com/shorts/Tiz771v_iLY")["kind"] == "invalid"

    def test_모르는_형식은_사유를_준다(self):
        from src.api.manage import parse_youtube_target
        p = parse_youtube_target("https://example.com/foo")
        assert p["kind"] == "invalid" and p["reason"]


class TestDeletePrefixGuard:
    """접두 삭제는 잘못 쓰면 버킷을 비운다."""

    @pytest.mark.parametrize("prefix", [
        "", "/", "raw/", "raw/video/", "raw/video/youtube_x",      # 끝 슬래시 없음
        "other/video/youtube_x/", "raw/video/youtube_x2/",          # 다른 데이터셋
    ])
    def test_위험한_접두는_거절한다(self, prefix, monkeypatch):
        from src.storage import s3_client
        monkeypatch.setattr(s3_client, "get_s3_client", lambda: pytest.fail("S3를 건드렸다"))
        with pytest.raises(ValueError):
            s3_client.delete_prefix(prefix, "urn:youtube:x")
