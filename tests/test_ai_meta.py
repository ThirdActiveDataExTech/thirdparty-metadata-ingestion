"""AI 생성 메타데이터 (A2) — 추출 요약과 키워드.

ADR-013이 외부 LLM을 금지했으므로 문장을 **생성하지 않고 고른다.**
그래서 여기서 지켜야 할 성질이 생긴다 — **요약의 모든 문장이 원문에 있어야 한다.**
생성 요약이었다면 못 거는 단언이고, 이것이 hallucination 없음의 기계적 보장이다.
"""

import pytest

from src.ai_meta import extractive as E
from src.search import tokenize

_tok = lambda s: [w for w in s.split() if len(w) > 1]      # noqa: E731


class TestSentences:
    def test_정형_안내문구를_뺀다(self):
        # 모든 영상에 붙어 있어 요약에 들어가면 전부 같은 요약이 된다
        for noise in ["구독과 좋아요 눌러주세요", "문의 : 010-0000-0000",
                      "▶ 더보기를 눌러주세요", "https://example.com/채널"]:
            assert E.sentences(noise) == []

    def test_짧은_조각은_버린다(self):
        assert E.sentences("짧다. 네.") == []

    def test_줄바꿈도_문장_경계다(self):
        # 영상 설명란은 마침표 없이 줄로 끊는 경우가 흔하다
        assert len(E.sentences("첫 줄입니다 충분히 길게\n둘째 줄입니다 충분히 길게")) == 2


class TestIdf:
    def test_드물수록_크다(self):
        idf = E.corpus_idf([["a", "b"], ["a", "c"], ["a", "d"], ["b", "e"]])
        assert idf["c"] > idf["b"] > idf["a"]

    def test_한_문서에_여러_번_나와도_df는_1이다(self):
        idf = E.corpus_idf([["a", "a", "a"], ["b"]])
        assert idf["a"] == idf["b"]

    def test_빈_코퍼스(self):
        assert E.corpus_idf([]) == {}


class TestKeywords:
    def test_드문_말이_위로_온다(self):
        idf = {"희귀": 3.0, "흔함": 0.1}
        assert E.keywords(["흔함", "흔함", "희귀"], idf, top_n=1) == ["희귀"]

    def test_idf가_없는_토큰은_빠진다(self):
        assert E.keywords(["모르는말"], {}, top_n=5) == []

    def test_상위_N을_지킨다(self):
        idf = {f"t{i}": float(i + 1) for i in range(20)}
        assert len(E.keywords(list(idf), idf, top_n=5)) == 5


class TestSummarize:
    LONG = (". ".join([
        "치핵은 항문 주변 혈관이 돌출되는 질환입니다",
        "변비가 있거나 오래 앉아 있는 습관이 원인이 됩니다",
        "수술은 보통 삼십 분에서 한 시간 정도 걸립니다",
        "회복 기간에는 좌욕과 섬유질 섭취가 도움이 됩니다",
        "통증이 심하면 바로 병원에 연락하셔야 합니다",
    ]))

    def test_요약의_모든_문장이_원문에_있다(self):
        # 추출 요약의 핵심 성질. hallucination 없음의 기계적 보장이다
        idf = {t: 1.0 for t in _tok(self.LONG)}
        out = E.summarize(self.LONG, idf, _tok, n=2)
        for sent in out.split(". "):
            assert sent.strip(". ") in self.LONG

    def test_원문_순서를_지킨다(self):
        # 점수 순으로 이으면 사람이 읽을 수 없다
        idf = {"통증": 5.0, "병원": 5.0, "치핵": 4.0, "항문": 4.0}
        out = E.summarize(self.LONG, idf, _tok, n=2)
        sents = E.sentences(self.LONG)
        picked = [i for i, s in enumerate(sents) if s.strip(". ") in out]
        assert picked == sorted(picked)

    def test_짧은_입력은_만들지_않는다(self):
        # 제목 한 줄로 "요약"을 만들면 원문과 같은 말이고,
        # 받는 쪽이 요약이 있다고 믿게 만드는 쪽이 더 나쁘다
        assert E.summarize("짧은 제목", {"제목": 1.0}, _tok) is None
        assert E.summarize("", {}, _tok) is None

    def test_같은_문장이_반복되면_한_번만_쓴다(self):
        text = ("똑같은 문장이 계속 반복되고 있습니다. " * 6) + "다른 내용의 문장입니다 여기."
        out = E.summarize(text, {w: 1.0 for w in _tok(text)}, _tok, n=3)
        assert out.count("똑같은 문장이 계속 반복되고 있습니다") == 1

    def test_길이로_나눠_긴_문장이_그냥_이기지_않는다(self):
        short = "핵심 내용 요약"
        longer = " ".join(["부수적인"] * 40)
        text = f"{short} 입니다 충분히 길게 만들기 위한 문장. {longer} 입니다 그리고 또 다른 말."
        idf = {"핵심": 10.0, "내용": 10.0, "요약": 10.0, "부수적인": 0.1}
        out = E.summarize(text, idf, _tok, n=1)
        assert "핵심" in out

    def test_문장이_N개_이하면_전부_쓴다(self):
        text = "첫 번째 문장입니다 충분히 길게. 두 번째 문장입니다 충분히 길게."
        out = E.summarize(text + " " * 100, {w: 1.0 for w in _tok(text)}, _tok, n=5)
        assert "첫 번째" in out and "두 번째" in out


class TestNounTokenizer:
    """키워드는 명사만 — 2026-11-04 A2 실측에서 나온 요구."""

    def test_동사_어간이_키워드에_안_들어간다(self):
        # `짧`·`보`·`느끼`는 df가 낮아 IDF가 오히려 밀어 올린다.
        # 문서빈도 상한으로는 못 잡고 품사로 걸러야 한다
        allw = tokenize.tokens("치질 수술이 끝나면 통증을 느끼고 회복이 짧습니다")
        nouns = tokenize.tokens("치질 수술이 끝나면 통증을 느끼고 회복이 짧습니다",
                                keep=tokenize.NOUNS)
        assert "느끼" in allw and "느끼" not in nouns
        assert "치질" in nouns and "수술" in nouns

    def test_영어_기능어를_거른다(self):
        # Kiwi는 영어를 전부 SL로 태깅해 품사로는 안 걸러진다
        nouns = tokenize.tokens("SK hynix Showcases Full Stack AI Memory at the OCP",
                                keep=tokenize.NOUNS)
        assert "the" not in nouns and "at" not in nouns
        assert "hynix" in nouns and "ai" in nouns

    def test_검색_색인에서는_불용어를_거르지_않는다(self):
        # 질의의 `the`가 문서의 `the`와 만나야 한다. 거기서는 해롭지 않다
        assert "the" in tokenize.tokens("the memory")

    def test_명사만_뽑아도_검색_토큰과_소문자_규약이_같다(self):
        assert tokenize.tokens("HBM", keep=tokenize.NOUNS) == ["hbm"]


class TestSourceText:
    def test_자막이_있으면_입력에_들어간다(self):
        from src.ai_meta.runner import _source_text
        row = {"title": "제목", "description": "설명"}
        assert "자막내용" in _source_text(row, "자막내용")

    def test_자막이_없어도_동작한다(self):
        from src.ai_meta.runner import _source_text
        assert _source_text({"title": "제목", "description": "설명"}, None) == "제목. 설명"

    def test_태그는_넣지_않는다(self):
        # 태그는 문장이 아니라 나열이라 추출 요약의 후보가 되면 읽히지 않는다
        from src.ai_meta.runner import _source_text
        out = _source_text({"title": "제목", "description": "설명", "tags": ["태그1"]}, None)
        assert "태그1" not in out
