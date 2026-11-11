"""기존 수집기 어댑터 이관 (A1 목표선, 2026-11-11) — POST·중첩 배열·엑셀.

실제 원천 대조는 scripts/verify_adapter_migration.py(블로그 300/300, 쇼핑인사이트 31/31 일치 — 2026-11-11).
"""

import pytest

from src.collectors.adapters import rest_json as R
from src.collectors.adapters.file_source import FileCollector, adapter_from_file
from src.collectors.base import CollectorError, RemovalPolicy


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code, self.text = data, status, ""

    def json(self):
        return self._d


def test_POST_본문에_스펙_body와_질의를_합치고_중첩을_펼친다(monkeypatch):
    sent = {}

    def post(url, headers, params, json, timeout):
        sent.update(url=url, json=json, params=params)
        return Resp({"results": [{"title": "패션의류", "category": ["5"], "data": [
            {"period": "2026-11-01", "ratio": 10.0}, {"period": "2026-11-02", "ratio": 12.5}]}]})
    monkeypatch.setattr(R.requests, "post", post)
    monkeypatch.setattr(R.requests, "get", lambda *a, **k: pytest.fail("GET이면 안 된다"))
    monkeypatch.setenv("NAVER_CLIENT_ID", "x")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "y")
    a = R.RestJsonCollector.from_file("configs/sources/naver_shopping_insight.yaml")
    rows = [a.normalize(r) for r in a.fetch(query={"startDate": "2026-11-01", "category": [{"name": "패션의류"}]})]
    assert sent["json"]["timeUnit"] == "date" and sent["json"]["startDate"] == "2026-11-01"
    assert rows == [{"category": "패션의류", "period": "2026-11-01", "ratio": 10.0},
                    {"category": "패션의류", "period": "2026-11-02", "ratio": 12.5}]


def test_모르는_method는_거부한다():
    with pytest.raises(CollectorError):
        R.RestJsonCollector({"source": "s", "endpoint": "http://x", "method": "put"})


def test_블로그_스펙은_뉴스와_같은_규칙을_지킨다():
    a = R.RestJsonCollector.from_file("configs/sources/naver_blog.yaml")
    assert a.removal_policy is RemovalPolicy.VERIFY_EACH          # 검색형 원천
    row = a.normalize({"link": "https://blog.naver.com/a/1", "title": "<b>홈트</b> 루틴", "bloggername": "b",
                       "bloggerlink": "x", "postdate": "20261110", "description": "d"})
    assert row["title"] == "홈트 루틴" and a.item_id(row) == "https://blog.naver.com/a/1"


def test_엑셀_첫_행을_머리글로_빈_행은_건너뛴다(tmp_path):
    from datetime import date
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "목록"
    ws.append(["번호", "제목", "등록일"])
    ws.append([1, "가", date(2026, 11, 1)])
    ws.append([None, None, None])
    ws.append([2, "나", None])
    p = tmp_path / "x.xlsx"
    wb.save(p)
    c = FileCollector({"source": "s", "path": str(p), "fields": {"id": "번호", "title": "제목", "d": "등록일"},
                       "id_field": "번호", "sheet": "목록"})
    rows = [c.normalize(r) for r in c.fetch()]
    assert rows == [{"id": 1, "title": "가", "d": "2026-11-01"}, {"id": 2, "title": "나", "d": None}]
    with pytest.raises(CollectorError):
        list(FileCollector({"source": "s", "path": str(p), "sheet": "없음"}).fetch())


def test_엑셀도_스펙_종류_file로_고른다(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("kind: file\nsource: s\npath: '*.xlsx'\n", encoding="utf-8")
    assert isinstance(adapter_from_file(str(p)), FileCollector)
