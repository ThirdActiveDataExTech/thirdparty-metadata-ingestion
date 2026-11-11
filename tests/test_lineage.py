"""데이터 리니지 (C5, 2026-11-11) — 단계 구성, 내부 정보 노출 범위."""

from datetime import datetime, timezone

from src.api import lineage as L

T = datetime(2026, 11, 1, tzinfo=timezone.utc)


class Cur:
    def __init__(self, st="news"):
        self.st = st
        self._r = []
        self.connection = self

    def rollback(self):
        pass

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT title, source_type"):
            self._r = [("뉴스", self.st, "mobigen", "네이버", "naver_news", "https://x", "약관", T, T)]
        elif "FROM data_registry" in s:
            self._r = [("meta_news", "raw/news/x/", "jsonld/x/", 300, T, T, "active", None)]
        elif "FROM dcat_provenance" in s:
            self._r = [("update", "scheduler_tick", T, T, "success", 10),
                       ("update", "agent:site_a.pub.pem", T, T, "success", 5),
                       ("update", "scheduler_tick", T, None, "failure", None)]
        elif "FROM meta_feature" in s:
            self._r = [(8, T)]
        elif "FROM dcat_dataset_relation" in s:
            self._r = [("KEYWORD_OVERLAP", 4)]
        elif "dataset_usage_event" in s:
            self._r = [("view", "", 7), ("download", "package", 2)]
        else:
            self._r = [(42,)]

    def fetchone(self):
        return self._r[0]

    def fetchall(self):
        return self._r


def _stage(d, key):
    return {i["label"]: i["value"] for i in next(s for s in d["stages"] if s["key"] == key)["items"]}


def test_다섯_단계와_실행_주체를_모은다():
    d = L.build(Cur(), "urn:n", admin=False)
    assert [s["key"] for s in d["stages"]] == ["source", "collect", "store", "process", "deliver"]
    c = _stage(d, "collect")
    assert c["실행"] == "3회 (성공 2 · 실패 1)"
    assert "정기 수집 2" in c["실행 주체"] and "현장 수집 번들 1" in c["실행 주체"]
    assert _stage(d, "deliver")["내려받기"] == "신뢰 패키지 2"
    assert _stage(d, "process")["검색 색인(청크·임베딩)"] == "42개"


def test_내부_저장_위치는_관리자에게만():
    assert "원본 저장 위치" not in _stage(L.build(Cur(), "urn:n", admin=False), "store")
    assert _stage(L.build(Cur(), "urn:n", admin=True), "store")["원본 저장 위치"] == "raw/news/x/"


def test_오류_원문은_싣지_않는다():
    d = L.build(Cur(), "urn:n", admin=True)
    assert all("error" not in r for r in d["recent_runs"])


def test_외부_카탈로그는_메타데이터만이라고_적는다():
    d = L.build(Cur("external_catalog"), "urn:e", admin=True)
    assert "원본 데이터는 원천에 있음" in _stage(d, "store")["저장"]


def test_API는_볼_수_없으면_404(monkeypatch):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from src.api.main import app

    def deny(cur, ds, user):
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    monkeypatch.setattr(L, "ensure_visible", deny)
    monkeypatch.setattr(L, "get_conn", lambda: type("C", (), {"cursor": lambda self: Cur()})())
    assert TestClient(app).get("/v1/datasets/urn:hidden/lineage").status_code == 404
