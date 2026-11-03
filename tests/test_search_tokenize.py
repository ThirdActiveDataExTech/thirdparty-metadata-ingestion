"""형태소 토큰화 — 키워드 채널의 입력을 만드는 부분.

여기서 지키려는 성질은 하나다: **질의와 문서가 같은 토큰을 낸다.**
어긋나면 오류가 나지 않고 리콜만 조용히 0이 되므로, 검증은 테스트로만 가능하다.
"""

import pytest

from src.search import tokenize


class TestJosaStripping:
    """ADR-018이 측정한 문서빈도 왜곡(65배)의 원인을 제거했는지."""

    @pytest.mark.parametrize("with_josa, bare", [
        ("대역폭을", "대역폭"),
        ("맨몸으로", "맨몸"),
        ("규제가", "규제"),
        ("메모리는", "메모리"),
    ])
    def test_같은_단어는_조사가_달라도_같은_토큰(self, with_josa, bare):
        assert tokenize.tokens(with_josa) == tokenize.tokens(bare)

    def test_어미가_달라도_어간은_같다(self):
        assert tokenize.tokens("올랐다") == tokenize.tokens("오르는")


class TestTokenShape:
    def test_조사와_어미는_남지_않는다(self):
        toks = tokenize.tokens("반도체 수출 규제가 강화되면서")
        assert "가" not in toks and "면서" not in toks
        assert "반도체" in toks and "수출" in toks and "규제" in toks

    def test_영문은_소문자로_맞춘다(self):
        # `simple` 설정 tsvector는 소문자화를 하지 않으므로 여기서 해야 한다
        assert tokenize.tokens("HBM") == tokenize.tokens("hbm") == ["hbm"]

    def test_기호는_떨어져_나간다(self):
        # Kiwi는 `©`를 외국어(SL)로 태깅해서 품사만으로는 안 걸러진다
        assert "©" not in tokenize.token_text("© 배종태 기자")
        assert tokenize.token_text("50% 증가") == "50 증가"

    def test_짧은_토큰을_길이로_버리지_않는다(self):
        # '맨몸' → 맨(XPN) + 몸(NNG). 1글자를 버리면 토큰이 하나도 안 남는다
        assert tokenize.tokens("맨몸으로") == ["몸"]
        # '전기차' → 전기 + 차. '차'를 버리면 전기 일반 기사와 구분이 안 된다
        assert "차" in tokenize.tokens("전기차 보조금")

    def test_토큰에는_공백이_없다(self):
        # 토큰 안에 공백이 들어가면 to_tsvector가 두 토큰으로 쪼갠다
        for t in tokenize.tokens("A/S 센터 50% 할인 © 2026"):
            assert " " not in t and t


class TestEmptyInput:
    @pytest.mark.parametrize("text", ["", "   ", "!!! ???", None])
    def test_내용어가_없으면_빈_결과(self, text):
        assert tokenize.tokens(text or "") == []

    def test_tsquery는_None을_돌려준다(self):
        # 호출 측이 키워드 채널을 건너뛰는 신호다
        assert tokenize.to_tsquery("!!!") is None
        assert tokenize.to_tsquery("") is None


class TestTsquery:
    def test_기본은_OR이다(self):
        # 리콜 우선 — 정밀도는 RRF 결합과 재순위가 맡는다
        assert tokenize.to_tsquery("반도체 수출") == "반도체 | 수출"

    def test_AND_모드(self):
        assert tokenize.to_tsquery("반도체 수출", mode="and") == "반도체 & 수출"

    @pytest.mark.parametrize("hostile", [
        "a & b", "foo:*", "!bar", "a | b & !c", "'; DROP TABLE x; --",
    ])
    def test_연산자_문자가_질의에_실려가지_않는다(self, hostile):
        # 사용자 입력을 to_tsquery에 직접 넣지 않는다(ADR-010).
        # 토큰화를 거치면 화이트리스트가 자연히 성립한다.
        q = tokenize.to_tsquery(hostile)
        if q is None:
            return
        for ch in "&!():*'\";":
            assert ch not in q.replace(" | ", "").replace(" & ", "")


class TestVersionGuard:
    """불일치를 막지 못하면 리콜이 조용히 0이 된다 — ADR-010이 기동 실패를 요구한 이유."""

    def test_버전에_분석기와_품사설정이_모두_들어간다(self):
        v = tokenize.version()
        assert v.startswith("kiwi-") and "model-" in v and "pos" in v

    def test_같은_버전은_통과(self):
        tokenize.assert_tokenizer_match([tokenize.version(), tokenize.version()])

    def test_빈_목록은_통과(self):
        # 아직 백필 전이라는 뜻. 그건 결과 0건으로 드러난다
        tokenize.assert_tokenizer_match([])
        tokenize.assert_tokenizer_match([None])

    def test_다른_버전이_섞이면_중단(self):
        with pytest.raises(tokenize.TokenizerMismatch) as e:
            tokenize.assert_tokenizer_match([tokenize.version(), "kiwi-0.0.1+model-0+pos0"])
        assert "backfill_tokens" in str(e.value)   # 고치는 방법을 메시지에 담는다
