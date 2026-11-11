"""외부 반출(허깅페이스 형식) — 결정 7 (src/export/policy.py · hf.py, 2026-11-11).

못박는 것
  - 전체 공개 + 재배포 허용 라이선스일 때만 내보낸다. 모르는 라이선스는 불가(보수적)
  - 네이버·YouTube 원천은 공개여도 불가, 사유가 사람이 읽는 문장으로 나온다
  - zip 구성(카드·Parquet·JSON-LD), 벡터 컬럼 제외, 카드 머리말이 허깅페이스 형식
  - 불가 데이터는 403이고 파일을 만들지 않는다
"""

import io
import zipfile
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from src.api import manage
from src.api.main import app
from src.export import hf, policy

OGL = "Open Government Licence - Canada"


@pytest.mark.parametrize("st,vis,lic,ok", [
    ("external_catalog", "PUBLIC", OGL, True),
    ("external_catalog", "PUBLIC", "open government licence - canada ", True),   # 대소문자·공백
    ("external_catalog", "ORG", OGL, False),
    ("external_catalog", "PUBLIC", "Some Custom Licence", False),               # 모르는 라이선스는 불가
    ("external_catalog", "PUBLIC", None, False),
    ("news", "PUBLIC", "https://developers.naver.com/notice/terms", False),
    ("video", "PUBLIC", "cc-by-4.0", False),                                     # 원천 약관이 우선
])
def test_반출_가능_판정(st, vis, lic, ok):
    e = policy.eligibility(st, vis, lic)
    assert e.allowed is ok
    assert (e.reasons == []) is ok


def test_불가_사유가_전부_나온다():
    e = policy.eligibility("news", "ORG", None)
    assert len(e.reasons) == 2
    assert any("전체 공개" in r for r in e.reasons) and any("네이버" in r for r in e.reasons)


def test_my_API와_같은_규칙을_쓴다():
    from src.api import my
    assert my.NO_EXPORT is policy.NO_EXPORT


class _Cur:
    def __init__(self, with_items=True):
        self.with_items, self._q = with_items, ""

    def execute(self, sql, params=None):
        self._q = sql

    def fetchone(self):
        if "FROM dcat_dataset" in self._q:
            return ("urn:x", "제목", "설명", "기관", "external_catalog", OGL, ["건강", "임신"], [], [],
                    "https://example.org/x", [], None, None, "unknown", datetime(2026, 11, 11, tzinfo=timezone.utc))
        if "pg_meta_table" in self._q:
            return ("meta_news",) if self.with_items else (None,)

    def fetchall(self):
        if "information_schema" in self._q:
            return [("id", "int8"), ("dataset_id", "text"), ("title", "text"), ("raw", "jsonb"),
                    ("embedding", "vector"), ("blob", "bytea")]
        return [(1, "urn:x", "가", {"a": 1}), (2, "urn:x", "나", None)]


class _Conn:
    def __init__(self, cur):
        self.cur = cur

    def cursor(self):
        return self.cur


def test_zip_구성과_카드(tmp_path):
    out = tmp_path / "x.zip"
    lic = policy.ALLOWED_LICENSES[OGL.lower()]
    info = hf.build(_Conn(_Cur()), "urn:x", lic, out, {"@id": "urn:x"})
    assert info == {"items": 2, "table": "meta_news"}
    z = zipfile.ZipFile(out)
    assert sorted(z.namelist()) == ["README.md", "data/items.parquet", "data/metadata.parquet", "metadata.jsonld"]
    card = z.read("README.md").decode()
    head = card.split("---")[1]
    assert "license: other" in head and 'license_name: "Open Government Licence - Canada"' in head
    assert "config_name: items" in head and '- "건강"' in head
    assert "출처 표시 필요" in card                       # 재배포 조건을 카드에 적는다
    items = pq.read_table(io.BytesIO(z.read("data/items.parquet")))
    assert items.column_names == ["id", "dataset_id", "title", "raw"]      # vector·bytea 제외
    assert items.column("raw").to_pylist() == ['{"a": 1}', None]          # JSON은 JSON 문자열


def test_아이템이_없으면_메타데이터만(tmp_path):
    out = tmp_path / "x.zip"
    hf.build(_Conn(_Cur(with_items=False)), "urn:x", policy.ALLOWED_LICENSES["cc0-1.0"], out, {})
    z = zipfile.ZipFile(out)
    assert "data/items.parquet" not in z.namelist()
    assert "license: cc0-1.0" in z.read("README.md").decode()


class _EpCur:
    def __init__(self, row):
        self.row, self._q = row, ""

    def execute(self, sql, params=None):
        self._q = sql

    def fetchone(self):
        return (1,) if self._q.startswith("SELECT 1") else self.row


def test_불가_데이터는_403이고_파일을_만들지_않는다(monkeypatch):
    cur = _EpCur(("news", "PUBLIC", "https://developers.naver.com/notice/terms"))
    monkeypatch.setattr(manage, "get_conn", lambda: _Conn(cur))
    built = []
    monkeypatch.setattr(hf, "build", lambda *a, **k: built.append(1))
    c = TestClient(app)
    r = c.get("/v1/console/datasets/urn:naver:news_1/export/hf")
    assert r.status_code == 403 and "네이버" in r.json()["detail"] and built == []
    chk = c.get("/v1/console/datasets/urn:naver:news_1/export/hf/check").json()
    assert chk["allowed"] is False and chk["license"] is None
