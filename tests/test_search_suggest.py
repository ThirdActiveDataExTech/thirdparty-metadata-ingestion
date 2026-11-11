"""검색어 자동완성 (C1, 2026-11-11) — 볼 수 있는 데이터셋의 제목·키워드에서만, 검색 기록 없이."""

from fastapi.testclient import TestClient

from src.api import main
from src.api.main import app


class Cur:
    def __init__(self, log, rows):
        self.log, self.rows = log, rows

    def execute(self, sql, params=None):
        self.log.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self.rows.pop(0) if self.rows else []


class Conn:
    def __init__(self, rows):
        self.log, self.rows = [], rows

    def cursor(self):
        return Cur(self.log, self.rows)


def _call(monkeypatch, q, rows):
    conn = Conn(rows)
    monkeypatch.setattr(main, "get_conn", lambda: conn)
    return TestClient(app).get("/v1/search/suggest", params={"q": q}), conn


def test_키워드_먼저_제목_다음(monkeypatch):
    r, _ = _call(monkeypatch, "HB", [[("urn:a", "HBM 뉴스", True)], [("HBM", 3, True), ("hbm 뉴스", 1, True)]])
    items = r.json()["items"]
    assert [(i["kind"], i["text"]) for i in items] == [("keyword", "HBM"), ("dataset", "HBM 뉴스")]


def test_비로그인은_전체_공개만_본다(monkeypatch):
    _, conn = _call(monkeypatch, "암", [[], []])
    assert all("visibility = 'PUBLIC'" in sql for sql, _ in conn.log)


def test_와일드카드_문자는_이스케이프한다(monkeypatch):
    _, conn = _call(monkeypatch, "100%_x", [[], []])
    params = conn.log[0][1]
    assert params["any"] == "%100\\%\\_x%" and params["pre"] == "100\\%\\_x%"


def test_공백뿐이면_빈_목록이고_DB를_부르지_않는다(monkeypatch):
    r, conn = _call(monkeypatch, "  ", [])
    assert r.json()["items"] == [] and conn.log == []
