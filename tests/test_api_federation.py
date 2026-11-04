"""카탈로그 API와 외부 포털 연합 (C6).

여기서 막으려는 것 둘이다.

1. **내보내면 안 되는 것이 응답에 섞이는 것** — API Key 암호문, 계정 식별자.
   한 번 나가면 되돌릴 수 없다.
2. **우리 기본값이 외국 데이터에 잘못 붙는 것** — `language`가 `'ko'`,
   `spatial`이 `'KR'`로 기본이라 그냥 두면 캐나다 데이터셋이 한국어·한국
   소재로 기록된다. 오류가 안 나서 눈으로는 안 보인다.
"""

import pytest

from src.api import schemas
from src.federation import ckan


class TestResponseAllowlist:
    """응답은 허용 목록으로 고정한다 — 컬럼이 늘어도 저절로 넓어지지 않는다."""

    FORBIDDEN = {"owner_id", "party", "encrypted_value", "credential_type",
                 "visibility"}

    @pytest.mark.parametrize("model", [schemas.DatasetSummary, schemas.DatasetDetail,
                                       schemas.SearchHit])
    def test_민감_필드가_없다(self, model):
        leaked = self.FORBIDDEN & set(model.model_fields)
        assert not leaked, f"{model.__name__}에 노출 금지 필드: {leaked}"

    def test_검색_결과에_채널_순위가_실린다(self):
        # 어느 채널이 올렸는지 안 보이면 결과를 해석할 수 없다
        assert {"vec_rank", "kw_rank", "rrf"} <= set(schemas.SearchHit.model_fields)


class TestCkanMapping:
    PKG = {
        "id": "abc-123", "name": "my-dataset", "title": "보건 데이터",
        "notes": "## 설명 **굵게** [링크](http://x)",
        "organization": {"title": "Health Canada"},
        "tags": [{"display_name": "health"}, {"name": "water"}],
        "license_title": "Open Government Licence", "frequency": "annual",
    }
    PORTAL = "https://open.canada.ca/data"

    def test_식별자가_포털과_원천id로_정해진다(self):
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        assert r["dataset_id"] == "urn:ckan:open-canada-ca:abc-123"

    def test_같은_입력이면_같은_식별자다(self):
        # 다시 들여오면 갱신돼야 한다. 매번 달라지면 중복이 쌓인다
        a = ckan.to_dcat(self.PKG, self.PORTAL)
        b = ckan.to_dcat(self.PKG, self.PORTAL)
        assert a["dataset_id"] == b["dataset_id"]

    def test_외부로_표시한다(self):
        # 수집 파이프라인이 건드리지 않게 하는 표시다
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        assert r["dataset_origin"] == "external"
        assert r["source"].startswith("CKAN:")
        assert r["external_ids"] == ["open-canada-ca:abc-123"]

    def test_원본을_복제하지_않고_가리킨다(self):
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        assert r["landing_page"].endswith("/dataset/my-dataset")

    def test_마크다운_기호를_걷어낸다(self):
        # 그대로 두면 검색 텍스트에 기호가 낀다
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        for ch in "#*[]()":
            assert ch not in r["description"]

    def test_제목이_없으면_버린다(self):
        # 이름 없는 행이 카탈로그에 쌓이면 검색 결과가 망가진다
        assert ckan.to_dcat({"id": "x", "title": "  "}, self.PORTAL) is None
        assert ckan.to_dcat({"title": "제목만"}, self.PORTAL) is None

    def test_키워드를_태그에서_가져온다(self):
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        assert r["keywords"] == ["health", "water"]


class TestForeignDefaults:
    """우리 기본값(`ko`/`KR`)이 외국 데이터에 붙지 않게 한다."""

    PORTAL = "https://open.canada.ca/data"
    PKG = {"id": "x", "title": "Canadian dataset"}

    def test_언어를_한국어로_두지_않는다(self):
        r = ckan.to_dcat(self.PKG, self.PORTAL)
        assert r["language"] == ckan.DEFAULT_LANGUAGE != "ko"

    def test_포털이_준_언어를_우선한다(self):
        r = ckan.to_dcat({**self.PKG, "language": "fr"}, self.PORTAL)
        assert r["language"] == "fr"

    def test_목록으로_와도_읽는다(self):
        r = ckan.to_dcat({**self.PKG, "language": ["fr", "en"]}, self.PORTAL)
        assert r["language"] == "fr"

    def test_소재는_추측하지_않는다(self):
        # 모르면 NULL이 맞다. 기본값 'KR'이 붙으면 캐나다 데이터가 한국 소재가 된다
        assert ckan.to_dcat(self.PKG, self.PORTAL)["spatial"] is None


class TestPortalSlug:
    @pytest.mark.parametrize("portal, want", [
        ("https://open.canada.ca/data", "open-canada-ca"),
        ("http://demo.ckan.org", "demo-ckan-org"),
        ("open.canada.ca", "open-canada-ca"),
    ])
    def test_호스트만_쓴다(self, portal, want):
        assert ckan._portal_slug(portal) == want


class TestRateLimit:
    def test_429를_재시도_대상으로_본다(self):
        # 하드 실패로 처리하면 가져올 수 있는 데이터를 버린다.
        # 실제로 2026-11-04에 429로 0건이 됐다
        import inspect
        src = inspect.getsource(ckan.search)
        assert "429" in src and "RetryableError" in src

    def test_쪽_사이에_쉰다(self):
        # 남의 서버를 쓰는 쪽이 맞춰야 한다
        assert ckan.RATE_LIMIT_SEC > 0


class TestStoreContract:
    def test_data_registry에_INSERT하지_않는다(self):
        """그 테이블은 수집 스케줄이다. 외부 데이터셋을 넣으면 스케줄러가
        수집하려 들고 실패만 쌓인다.

        주석·docstring은 빼고 **실행되는 코드만** 본다 — 설명에 테이블
        이름이 나온다고 걸리면 테스트가 설명을 못 쓰게 만든다.
        """
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(ckan.store)))
        fn = tree.body[0]
        body = fn.body[1:] if ast.get_docstring(fn) else fn.body
        code = "\n".join(ast.unparse(n) for n in body)
        assert "data_registry" not in code

    def test_다시_들여오면_갱신한다(self):
        import inspect
        assert "ON CONFLICT" in inspect.getsource(ckan.store)
