"""템플릿 파이프라인 (C3) — 스펙 하나로 수집부터 적재까지.

여기서 막으려는 것 셋.

1. **단계 순서가 섞이는 것** — normalize 없이 store하면 원천 모양이 그대로
   들어가고, store 없이 postprocess하면 빈 데이터셋을 임베딩한다.
2. **스펙에 없는 컬럼에 쓰는 것** — 원천이 필드를 늘리면 없는 컬럼에 쓰려다
   실패하거나, 더 나쁘게는 엉뚱한 컬럼에 들어간다.
3. **식별자 없는 행이 쌓이는 것** — 중복 판정 기준이 없으면 넣을 때마다 새 행이 된다.
"""

import pytest

from src.collectors.adapters import rest_json as R
from src.pipeline_engine import runner, steps


class TestCleanText:
    """2026-11-04: 어댑터가 `<b>` 태그를 안 벗겨 28건이 오염됐다."""

    def test_태그를_벗긴다(self):
        assert R.clean_text("한미<b>반도체</b> 회장") == "한미반도체 회장"

    def test_엔티티를_푼다(self):
        assert R.clean_text("&quot;인용&quot; &amp; 기호") == '"인용" & 기호'

    def test_문자열이_아니면_그대로(self):
        assert R.clean_text(None) is None
        assert R.clean_text(123) == 123

    def test_기본으로_켜져_있다(self):
        # 검색 API의 강조 태그는 예외가 아니라 기본값에 가깝다
        c = R.RestJsonCollector({"source": "s", "endpoint": "http://x",
                                 "fields": {"title": "t"}})
        assert c.normalize({"t": "<b>제목</b>"})["title"] == "제목"

    def test_스펙으로_끌_수_있다(self):
        # 마크업이 의미를 갖는 원천은 명시해서 끈다
        c = R.RestJsonCollector({"source": "s", "endpoint": "http://x",
                                 "fields": {"title": "t"}, "clean_text": False})
        assert c.normalize({"t": "<b>제목</b>"})["title"] == "<b>제목</b>"


class TestSpecValidation:
    def test_필수_키가_없으면_거부한다(self, tmp_path):
        import yaml
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({"source_spec": "x"}), encoding="utf-8")
        with pytest.raises(runner.PipelineError):
            runner.load(str(p))

    def test_target_키가_없으면_거부한다(self, tmp_path):
        import yaml
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({"source_spec": "x", "dataset_id": "d",
                                "target": {"table": "t"}}), encoding="utf-8")
        with pytest.raises(runner.PipelineError):
            runner.load(str(p))

    def test_알_수_없는_단계를_거부한다(self, tmp_path):
        import yaml
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({
            "source_spec": "x", "dataset_id": "d",
            "target": {"table": "t", "columns": ["a"], "conflict_key": "a"},
            "steps": ["collect", "없는단계"]}), encoding="utf-8")
        with pytest.raises(runner.PipelineError):
            runner.load(str(p))

    def test_없는_파일을_거부한다(self):
        with pytest.raises(runner.PipelineError):
            runner.load("존재하지_않는_파이프라인")

    def test_실제_스펙이_전부_읽힌다(self):
        for name in runner.available():
            spec = runner.load(name)
            assert spec["target"]["conflict_key"] in spec["target"]["columns"]


class TestStepOrder:
    def test_고정_순서가_정의돼_있다(self):
        assert runner.STEP_ORDER == ["collect", "normalize", "store", "postprocess"]

    def test_스펙의_나열_순서를_믿지_않는다(self, monkeypatch, tmp_path):
        """스펙에 거꾸로 적어도 고정 순서로 돈다."""
        import yaml
        called = []
        monkeypatch.setattr(steps, "collect", lambda *a, **k: called.append("collect") or [])
        monkeypatch.setattr(steps, "normalize", lambda *a, **k: called.append("normalize") or [])
        monkeypatch.setattr(steps, "store", lambda *a, **k: called.append("store") or {})
        monkeypatch.setattr(steps, "postprocess", lambda *a, **k: called.append("postprocess") or {})
        monkeypatch.setattr(runner, "adapter_from_file", lambda p: object())

        p = tmp_path / "rev.yaml"
        p.write_text(yaml.dump({
            "source_spec": "x", "dataset_id": "d",
            "target": {"table": "t", "columns": ["a"], "conflict_key": "a"},
            "steps": ["postprocess", "store", "normalize", "collect"]}), encoding="utf-8")
        runner.run(str(p))
        assert called == runner.STEP_ORDER


class TestStore:
    def test_conflict_key가_columns에_없으면_거부한다(self):
        # 충돌 키가 INSERT에 안 들어가면 ON CONFLICT가 성립하지 않는다
        with pytest.raises(steps.StepError):
            steps.store([{"a": 1}], "ds", "t", ["a"], "없는키")

    def test_빈_입력은_아무것도_하지_않는다(self):
        assert steps.store([], "ds", "t", ["a"], "a") == {"attempted": 0, "stored": 0}

    def test_스펙에_없는_값은_보내지_않는다(self, monkeypatch):
        """원천이 필드를 늘려도 엉뚱한 컬럼에 들어가지 않는다."""
        captured = {}

        class _Cur:
            def execute(self, *a, **k):
                pass

        class _Conn:
            def cursor(self):
                return _Cur()

            def commit(self):
                pass

        monkeypatch.setattr(steps, "get_conn", lambda: _Conn())
        monkeypatch.setattr(steps, "execute_values",
                            lambda cur, sql, payload, **k: captured.update(
                                {"sql": sql, "payload": payload}))
        steps.store([{"a": 1, "몰래": "들어온값"}], "ds", "t", ["a"], "a")
        assert "몰래" not in captured["sql"]
        assert "들어온값" not in str(captured["payload"])

    def test_멱등하게_넣는다(self, monkeypatch):
        captured = {}

        class _Cur:
            def execute(self, *a, **k):
                pass

        class _Conn:
            def cursor(self):
                return _Cur()

            def commit(self):
                pass

        monkeypatch.setattr(steps, "get_conn", lambda: _Conn())
        monkeypatch.setattr(steps, "execute_values",
                            lambda cur, sql, payload, **k: captured.update({"sql": sql}))
        steps.store([{"a": 1}], "ds", "t", ["a"], "a")
        assert "ON CONFLICT (dataset_id, a) DO UPDATE" in captured["sql"]


class _Adapter:
    def __init__(self, rows):
        self.rows = rows

    def fetch(self, query=None):
        return iter(self.rows)

    def normalize(self, raw):
        return dict(raw)

    def item_id(self, row):
        if "id" not in row:
            raise ValueError("식별자 없음")
        return row["id"]


class TestNormalizeStep:
    def test_식별자가_없는_행은_버린다(self):
        # 중복 판정 기준이 없으면 넣을 때마다 새 행이 쌓인다
        a = _Adapter([])
        out = steps.normalize(a, [{"id": "1"}, {"식별자없음": True}, {"id": "2"}])
        assert [r["id"] for r in out] == ["1", "2"]

    def test_collect는_상한을_지킨다(self):
        a = _Adapter([{"id": str(i)} for i in range(100)])
        assert len(steps.collect(a, limit=7)) == 7


class TestPostprocess:
    def test_알_수_없는_동작은_거부한다(self):
        with pytest.raises(steps.StepError):
            steps.postprocess("ds", "news", ["없는동작"])

    def test_후속_실패가_수집을_무효로_만들지_않는다(self, monkeypatch):
        # 데이터는 이미 들어갔다. 임베딩 실패로 그걸 되돌릴 이유가 없다
        import src.embedding.sync as S

        def _boom(*a, **k):
            raise RuntimeError("모델 없음")

        monkeypatch.setattr(S, "sync_for_dataset", _boom)
        out = steps.postprocess("ds", "news", ["embed"])
        assert "실패" in out["embed"]
