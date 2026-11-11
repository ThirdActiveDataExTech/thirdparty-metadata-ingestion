"""원천 형식 변화에 따른 매핑 자동 변경 (C4 목표선, 2026-11-11).

**확실하지 않으면 고치지 않는다**가 핵심이다 — 틀린 자동 수정은 컬럼이 비는 것보다 나쁘다
(값이 엉뚱한 컬럼에 조용히 들어간다).
"""

import pytest
import yaml

from src.collectors.adapters.rest_json import RestJsonCollector
from src.pipeline_engine import autoheal as H
from src.pipeline_engine import drift

SPEC = {"source": "s", "endpoint": "http://x", "id_field": "link",
        "fields": {"id": "link", "title": "snippet.title", "published_at": "snippet.publishedAt",
                   "channel": "snippet.channelTitle"}}


def _drift(raws):
    """실제 드리프트 판정을 메모리에서(DB 없이) 돌린 것과 같은 모양."""
    observed = drift.observe(raws)
    fields = drift.core_fields(observed)
    wanted = drift.mapped_paths(SPEC)
    broken = [p for p in wanted if p not in fields]
    return {"broken_mappings": broken, "suggestions": drift.suggest(broken, fields)}


class TestPick:
    def test_잎_이름이_같으면_옮겨_간_것으로_본다(self):
        assert H.pick("snippet.publishedAt", ["meta.published_at", "snippet.title"]) == "meta.published_at"

    def test_같은_이름이_여러_곳이면_고르지_않는다(self):
        assert H.pick("snippet.title", ["a.title", "b.title"]) is None

    def test_후보가_하나이고_아주_닮았을_때만(self):
        assert H.pick("snippet.channelTitle", ["snippet.channelTitles"]) == "snippet.channelTitles"
        assert H.pick("snippet.channelTitle", ["owner.name"]) is None
        assert H.pick("snippet.channelTitle", ["snippet.channelName", "snippet.channelTag"]) is None


class TestPlan:
    def test_필드가_다른_가지로_옮겨_가면_고친_스펙을_낸다(self):
        raws = [{"link": f"u{i}", "snippet": {"title": "t", "channelTitle": "c"}, "meta": {"publishedAt": "2026"}}
                for i in range(10)]
        p = H.plan(SPEC, _drift(raws))
        assert p["changes"] == [{"field": "published_at", "from": "snippet.publishedAt", "to": "meta.publishedAt"}]
        assert p["spec"]["fields"]["published_at"] == "meta.publishedAt"
        assert SPEC["fields"]["published_at"] == "snippet.publishedAt"        # 원본은 그대로

    def test_식별자_경로도_고친다(self):
        raws = [{"url": f"u{i}", "snippet": {"title": "t", "channelTitle": "c", "publishedAt": "x"}} for i in range(10)]
        d = {"broken_mappings": ["link"], "suggestions": {"link": ["linkUrl"]}}
        p = H.plan(SPEC, d)
        assert p["spec"] is None and p["unresolved"][0]["path"] == "link"   # 닮지 않은 이름은 안 고친다
        p = H.plan(SPEC, {"broken_mappings": ["link"], "suggestions": {"link": ["Link"]}})
        assert {c["field"] for c in p["changes"]} == {"id", "id_field"}

    def test_다른_매핑이_읽는_경로로는_옮기지_않는다(self):
        d = {"broken_mappings": ["snippet.channelTitle"], "suggestions": {"snippet.channelTitle": ["snippet.title"]}}
        assert H.plan(SPEC, d)["unresolved"]
        d = {"broken_mappings": ["snippet.publishedAt"], "suggestions": {"snippet.publishedAt": ["snippet.title"]}}
        assert H.plan(SPEC, d)["spec"] is None

    def test_목록_경로는_스펙_표기로_바꾼다(self):
        assert H.to_dig("items[].snippet.title") == "items.0.snippet.title"
        assert H.to_dig("tags[]") == "tags.0"


class TestHeal:
    def _adapter(self):
        return RestJsonCollector(dict(SPEC, fields=dict(SPEC["fields"])))

    def _moved(self):
        return {"broken_mappings": ["snippet.publishedAt"], "suggestions": {"snippet.publishedAt": ["meta.publishedAt"]}}

    def test_propose는_매핑을_바꾸지_않고_제안_YAML만(self):
        a = self._adapter()
        r = H.heal(a, "propose", self._moved())
        assert r["applied"] is False and a._fields["published_at"] == "snippet.publishedAt"
        assert yaml.safe_load(r["proposed_spec_yaml"])["fields"]["published_at"] == "meta.publishedAt"

    def test_apply는_이번_실행부터_고친_매핑으로_정규화한다(self):
        a = self._adapter()
        r = H.heal(a, "apply", self._moved())
        assert r["applied"] is True
        row = a.normalize({"link": "u", "snippet": {"title": "t", "channelTitle": "c"}, "meta": {"publishedAt": "2026-11-11"}})
        assert row["published_at"] == "2026-11-11"

    def test_off이거나_깨진_것이_없으면_아무것도_안_한다(self):
        a = self._adapter()
        assert H.heal(a, "off", self._moved()) is None
        assert H.heal(a, "apply", {"broken_mappings": []}) is None

    def test_모르는_모드는_거부한다(self):
        with pytest.raises(ValueError):
            H.heal(self._adapter(), "auto", self._moved())


def test_러너가_수집_뒤_정규화_전에_고친다(monkeypatch):
    from src.pipeline_engine import runner, steps
    seen = {}
    adapter = RestJsonCollector(dict(SPEC, fields=dict(SPEC["fields"])))
    monkeypatch.setattr(runner, "load", lambda n: {"dataset_id": "urn:t", "source_spec": "x", "auto_remap": "apply",
                                                    "steps": ["collect", "normalize"],
                                                    "target": {"table": "t", "columns": ["title"], "conflict_key": "id"}})
    monkeypatch.setattr(runner, "adapter_from_file", lambda p: adapter)
    monkeypatch.setattr(steps, "collect", lambda a, query=None, limit=None: [{"link": "u", "meta": {"publishedAt": "d"}}])
    monkeypatch.setattr(runner, "_check_drift", lambda ds, raws, a, dry: {
        "broken_mappings": ["snippet.publishedAt"], "suggestions": {"snippet.publishedAt": ["meta.publishedAt"]}})
    monkeypatch.setattr(steps, "normalize", lambda a, raws: seen.setdefault("rows", [a.normalize(r) for r in raws]))
    r = runner.run("x")
    assert r["remap"]["applied"] and seen["rows"][0]["published_at"] == "d"
