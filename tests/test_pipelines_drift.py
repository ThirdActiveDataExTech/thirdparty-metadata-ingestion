"""정기 수집 경로의 드리프트 감지 연결 (src/pipelines/_drift.py, C4 — 2026-11-11).

못박는 것
  - 표본은 파이프라인이 켰을 때만 모이고, 상한을 넘지 않는다
  - READS(수집기가 읽는 경로)가 수집기 코드와 맞고, 실제 응답 모양에서 "깨짐"으로 나오지 않는다
  - 5개 파이프라인 모두 begin/check를 부르고, 유형 이름이 src.main 등록과 맞는다
  - 감지가 실패해도 예외가 밖으로 나가지 않는다(수집은 성공)
"""

import inspect
import re

import pytest

from src import main as cli
from src.collectors import raw_sample
from src.pipeline_engine import drift
from src.pipelines import _drift


@pytest.fixture(autouse=True)
def _clean():
    raw_sample.stop()
    yield
    raw_sample.stop()


def test_켜지_않았으면_모으지_않는다():
    raw_sample.record({"a": 1})
    assert raw_sample.stop() == []


def test_상한까지_고르게_모은다():
    raw_sample.start(limit=10)
    raw_sample.record_many({"i": i} for i in range(1000))
    raw_sample.record("not-a-dict")
    got = raw_sample.stop()
    assert len(got) == 10 and all(isinstance(g, dict) for g in got)
    assert max(g["i"] for g in got) > 10          # 앞쪽 10건만이 아니다(저수지 표집)
    assert raw_sample.stop() == []                # stop 뒤엔 비어 있다


# ── READS가 실제 응답 모양과 맞는가 ──────────────────────────────────────────

def _news(i):
    return {"title": f"<b>t</b>{i}", "originallink": "https://a.example/x", "link": "https://n.news.naver.com/x",
            "description": "d", "pubDate": "Mon, 10 Nov 2026 10:00:00 +0900"}


def _blog(i):
    return {"title": "t", "link": "https://blog.naver.com/a/1", "description": "d", "bloggername": "b",
            "bloggerlink": "blog.naver.com/a", "postdate": "20261110"}


def _video(i):
    return {"kind": "youtube#video", "etag": "e", "id": f"v{i}",
            "snippet": {"publishedAt": "2026-11-10T00:00:00Z", "channelId": "c", "title": "t", "description": "d",
                        "thumbnails": {"default": {"url": "u"}}, "channelTitle": "ct", "categoryId": "22"},
            "contentDetails": {"duration": "PT5M", "dimension": "2d", "definition": "hd", "caption": "false"},
            "statistics": {"viewCount": "1"}}


def _shopping(i):
    return {"startDate": "2026-11-01", "endDate": "2026-11-10", "timeUnit": "date",
            "results": [{"title": "패션", "category": ["50000000"],
                         "data": [{"period": "2026-11-01", "ratio": 10.5}]}]}


def _persona(i):
    return {"startDate": "2026-11-01", "endDate": "2026-11-10", "timeUnit": "date",
            "results": [{"title": "패션", "category": ["50000000"],
                         "data": [{"period": "2026-11-01", "group": "f", "ratio": 60.1}]}]}


SAMPLES = {"news": _news, "blog": _blog, "video": _video,
           "shopping_insight": _shopping, "persona_insight": _persona}


class _Conn:
    """직전 기록이 비어 있는(첫 관측) 레지스트리 행 하나."""

    def __init__(self):
        self.saved = None

    def cursor(self):
        conn = self

        class C:
            def execute(self, sql, params=None):
                self._sql = sql
                if sql.startswith("UPDATE"):
                    conn.saved = params

            def fetchone(self):
                return (None, [])

            def close(self):
                pass

        return C()

    def commit(self):
        pass

    def rollback(self):
        pass


def test_모든_정기_수집_유형에_READS가_있다():
    assert set(_drift.READS) == set(cli.PIPELINE_MODULES)


@pytest.mark.parametrize("source", sorted(SAMPLES))
def test_실제_응답_모양에서_READS가_깨지지_않는다(source):
    raws = [SAMPLES[source](i) for i in range(10)]
    r = drift.check("urn:x", raws, {"fields": {p: p for p in _drift.READS[source]}}, conn=_Conn())
    assert r["status"] == "first_seen" and r["severity"] == "none", r.get("broken_mappings")


@pytest.mark.parametrize("source", sorted(SAMPLES))
def test_READS_경로가_사라지면_breaking으로_잡는다(source):
    path = _drift.READS[source][-1]
    leaf = path.split(".")[-1]

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k != leaf}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o

    raws = [strip(SAMPLES[source](i)) for i in range(10)]
    r = drift.check("urn:x", raws, {"fields": {p: p for p in _drift.READS[source]}}, conn=_Conn())
    assert r["severity"] == "breaking" and path in r["broken_mappings"]


COLLECTORS = {"news": "naver_news_collector", "blog": "naver_blog_collector", "video": "youtube_collector",
              "shopping_insight": "naver_shopping_collector", "persona_insight": "naver_persona_collector"}


@pytest.mark.parametrize("source", sorted(COLLECTORS))
def test_READS는_수집기가_실제로_읽는_키다(source):
    """수집기에서 읽는 필드를 바꾸면 READS도 같이 고치라는 경보."""
    import importlib
    code = inspect.getsource(importlib.import_module(f"src.collectors.{COLLECTORS[source]}"))
    for path in _drift.READS[source]:
        leaf = path.replace("[]", "").split(".")[-1]
        assert re.search(rf"""["']{re.escape(leaf)}["']""", code), f"{source}: {leaf}를 수집기에서 읽지 않는다"
    assert "raw_sample.record" in code


@pytest.mark.parametrize("source,module", sorted(cli.PIPELINE_MODULES.items()))
def test_정기_수집_파이프라인이_감지를_부른다(source, module):
    import importlib
    code = inspect.getsource(importlib.import_module(module).run)
    assert "_drift.begin()" in code
    assert f'_drift.check(dataset_id, "{source}")' in code
    # 레지스트리 갱신(커밋) 뒤에 부른다 — drift.save가 커밋하므로 앞의 쓰기를 섞어 확정하지 않게
    assert code.index("dcat.update_data_registry(") < code.index("_drift.check(")


def test_감지가_실패해도_예외를_내지_않는다(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(drift, "check", boom)
    raw_sample.start()
    raw_sample.record({"a": 1})
    assert _drift.check("urn:x", "news") is None
    assert raw_sample.stop() == []                # 표본은 정리됐다


def test_감지에_표본과_READS를_넘긴다(monkeypatch):
    seen = {}

    def fake(dataset_id, raws, spec, **k):
        seen.update(dataset_id=dataset_id, n=len(raws), spec=spec)
        return {"status": "unchanged", "severity": "none", "sample": len(raws)}
    monkeypatch.setattr(drift, "check", fake)
    _drift.begin()
    raw_sample.record_many(_news(i) for i in range(7))
    assert _drift.check("urn:n", "news")["status"] == "unchanged"
    assert seen["n"] == 7 and set(seen["spec"]["fields"]) == set(_drift.READS["news"])


def test_표본이_적은_원천도_판정한다(monkeypatch):
    """페르소나는 한 번 수집에 응답 2~4건 — 기본 최소 표본(5)이면 영영 건너뛴다(2026-11-11 실측)."""
    seen = {}

    def fake(dataset_id, raws, spec, **k):
        seen.update(k)
        return {"status": "first_seen", "severity": "none", "sample": len(raws)}
    monkeypatch.setattr(drift, "check", fake)
    _drift.begin()
    raw_sample.record_many(_persona(i) for i in range(2))
    _drift.check("urn:p", "persona_insight")
    assert seen["min_sample"] == 2
    _drift.begin()
    _drift.check("urn:n", "news")
    assert seen["min_sample"] == drift.MIN_SAMPLE
