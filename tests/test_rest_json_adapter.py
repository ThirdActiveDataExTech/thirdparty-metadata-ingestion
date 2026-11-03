"""스펙으로 동작하는 수집 어댑터 (A1).

여기서 막으려는 것 둘이다.

1. **자격증명이 스펙에 평문으로 들어가는 것** — 커밋되면 되돌릴 수 없다.
2. **삭제 감지가 기본으로 켜지는 것** — 2026-07-28에 뉴스 146건이 "부재"였는데
   91건(62%)이 살아 있었다. 새 어댑터가 그 사고를 모르고 반복하면 데이터가
   조용히 사라진다.
"""

import pytest

from src.collectors.base import BaseCollector, CollectorError, RemovalPolicy
from src.collectors.adapters import rest_json as R


class TestDig:
    @pytest.mark.parametrize("obj, path, want", [
        ({"a": {"b": "c"}}, "a.b", "c"),
        ({"a": {"b": [{"c": 1}]}}, "a.b.0.c", 1),
        ({"a": 1}, "x.y", None),
        (None, "a", None),
        ({"a": [1, 2]}, "a.9", None),     # 범위 밖
        ({"a": "문자열"}, "a.b", None),    # 더 못 들어감
    ])
    def test_중첩_경로(self, obj, path, want):
        assert R.dig(obj, path) == want


class TestCredentials:
    def test_환경변수_이름만_해석한다(self, monkeypatch):
        monkeypatch.setattr(R.config, "get_env", lambda n: "비밀값" if n == "KEY" else None)
        assert R._resolve({"env": "KEY"}, "x") == "비밀값"

    def test_빈_환경변수는_요청_전에_실패시킨다(self, monkeypatch):
        # 빈 헤더로 보내면 원천이 401을 주는데 "없음"인지 "틀림"인지 구분이 안 된다
        monkeypatch.setattr(R.config, "get_env", lambda n: None)
        with pytest.raises(CollectorError) as e:
            R._resolve({"env": "MISSING"}, "src.auth.key")
        assert "MISSING" in str(e.value)

    def test_평문_값도_허용한다(self):
        # 비밀이 아닌 상수(sort=date 등)는 그대로 적는다
        assert R._resolve("date", "x") == "date"

    def test_실제_스펙에_평문_자격증명이_없다(self):
        import glob
        import yaml
        suspicious = ("key", "secret", "token", "password", "client_id", "client_secret")
        for path in glob.glob("configs/sources/*.yaml"):
            spec = yaml.safe_load(open(path, encoding="utf-8"))
            auth = spec.get("auth") or {}
            for where in ("headers", "params"):
                for name, value in (auth.get(where) or {}).items():
                    assert isinstance(value, dict) and "env" in value, (
                        f"{path}: auth.{where}.{name}이 환경변수 참조가 아니다")
            for name, value in (spec.get("params") or {}).items():
                if any(s in name.lower() for s in suspicious):
                    assert isinstance(value, dict) and "env" in value, (
                        f"{path}: params.{name}이 평문이다")


class TestSpecValidation:
    def test_source가_없으면_거부한다(self):
        with pytest.raises(CollectorError):
            R.RestJsonCollector({"endpoint": "http://x"})

    def test_endpoint가_없으면_거부한다(self):
        with pytest.raises(CollectorError):
            R.RestJsonCollector({"source": "s"})

    def test_실제_스펙이_전부_읽힌다(self):
        import glob
        for path in glob.glob("configs/sources/*.yaml"):
            c = R.RestJsonCollector.from_file(path)
            assert c.source and c.endpoint


class TestNormalize:
    def test_매핑대로_평평하게_만든다(self):
        c = R.RestJsonCollector({
            "source": "s", "endpoint": "http://x",
            "fields": {"id": "a.b", "title": "t"}})
        assert c.normalize({"a": {"b": "X"}, "t": "제목"}) == {"id": "X", "title": "제목"}

    def test_매핑이_없으면_raw를_그대로_준다(self):
        # 원천 구조를 모를 때 한 번 돌려보고 fields를 채우는 흐름을 위해서다
        c = R.RestJsonCollector({"source": "s", "endpoint": "http://x"})
        assert c.normalize({"무엇이든": 1}) == {"무엇이든": 1}

    def test_id_field로_식별자를_채운다(self):
        c = R.RestJsonCollector({"source": "s", "endpoint": "http://x",
                                 "fields": {"title": "t"}, "id_field": "vid"})
        assert c.item_id(c.normalize({"vid": "V1", "t": "제목"})) == "V1"

    def test_식별자가_없으면_분명히_실패한다(self):
        c = R.RestJsonCollector({"source": "s", "endpoint": "http://x",
                                 "fields": {"title": "t"}})
        with pytest.raises(CollectorError) as e:
            c.item_id(c.normalize({"t": "제목"}))
        assert "id_field" in str(e.value)


class _Probe(BaseCollector):
    """verify_exists만 흉내 내는 수집기."""

    source = "probe"

    def __init__(self, policy, alive=None):
        self.removal_policy = policy
        self.alive = alive or {}

    def fetch(self, cursor=None):
        return iter(())

    def normalize(self, raw):
        return raw

    def verify_exists(self, item_id):
        return self.alive.get(item_id)


class TestRemovalPolicy:
    def test_기본값은_판정하지_않는다(self):
        # 모르면 지우지 않는다. 조용히 사라지는 것보다 남는 쪽이 낫다
        assert BaseCollector.removal_policy is RemovalPolicy.UNSUPPORTED

    def test_UNSUPPORTED는_아무것도_지우지_않는다(self):
        p = _Probe(RemovalPolicy.UNSUPPORTED)
        assert p.detect_removed(["a", "b"], []) == []

    def test_ABSENT는_부재를_전부_삭제로_본다(self):
        # 원천이 전수 목록을 줄 때만 안전하다
        p = _Probe(RemovalPolicy.ABSENT_MEANS_REMOVED)
        assert p.detect_removed(["a", "b", "c"], ["a"]) == ["b", "c"]

    def test_VERIFY는_404가_확정된_것만_지운다(self):
        # 2026-07-28: 부재 146건 중 91건(62%)이 살아 있었다
        p = _Probe(RemovalPolicy.VERIFY_EACH, alive={"b": True, "c": False})
        assert p.detect_removed(["a", "b", "c"], ["a"]) == ["c"]

    def test_VERIFY는_확인_불가를_보존한다(self):
        # 네트워크 오류로 데이터를 지우면 안 된다
        p = _Probe(RemovalPolicy.VERIFY_EACH, alive={"b": None})
        assert p.detect_removed(["a", "b"], ["a"]) == []

    def test_검색형_스펙은_VERIFY여야_한다(self):
        c = R.RestJsonCollector.from_file("configs/sources/naver_news.yaml")
        assert c.removal_policy is RemovalPolicy.VERIFY_EACH


class TestPagingSpec:
    def test_두_가지_페이징_방식을_스펙으로_쓴다(self):
        # 코드 수정 없이 YAML만으로 새 원천이 도는 것이 A1 완료 기준이다
        news = R.RestJsonCollector.from_file("configs/sources/naver_news.yaml")
        yt = R.RestJsonCollector.from_file("configs/sources/youtube_search.yaml")
        assert news.spec["paging"]["mode"] == "offset"
        assert yt.spec["paging"]["mode"] == "cursor"

    def test_offset_스펙에_상한이_있다(self):
        # 멈추는 조건이 빠지면 무한 루프가 된다
        c = R.RestJsonCollector.from_file("configs/sources/naver_news.yaml")
        p = c.spec["paging"]
        assert p.get("max_pages") and p.get("max_offset")

    def test_cursor_스펙에_토큰_경로가_있다(self):
        c = R.RestJsonCollector.from_file("configs/sources/youtube_search.yaml")
        p = c.spec["paging"]
        assert p.get("token_param") and p.get("token_path") and p.get("max_pages")
