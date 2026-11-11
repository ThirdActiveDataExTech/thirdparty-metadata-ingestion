"""검색 동의어 확장 (C1, 2026-11-11) — 키워드 채널에만, 낮은 가중치로."""

import pytest

from src.search import synonyms


def toks(text):
    # Kiwi 대신 공백 분리 — 사전 매칭 규칙만 본다
    return [t.lower() for t in text.split()]


@pytest.fixture
def dic(tmp_path, monkeypatch):
    p = tmp_path / "syn.yaml"
    p.write_text("groups:\n  - [전기차, 전기 자동차, EV]\n  - [반도체, semiconductor]\n  - [혼자]\n", encoding="utf-8")
    monkeypatch.setattr(synonyms, "PATH", p)
    synonyms.reset()
    yield
    synonyms.reset()


def test_묶음의_다른_표기를_낮은_가중치로_더한다(dic):
    extra = synonyms.expand(toks("전기차 보조금"), toks)
    assert extra == {"전기": synonyms.WEIGHT, "자동차": synonyms.WEIGHT, "ev": synonyms.WEIGHT}


def test_여러_토큰_표기는_전부_있어야_맞는다(dic):
    assert synonyms.expand(toks("전기 보조금"), toks) == {}           # '전기'만으론 '전기 자동차'가 아니다
    assert "전기차" in synonyms.expand(toks("전기 자동차"), toks)


def test_원래_질의에_있는_토큰은_더하지_않는다(dic):
    assert synonyms.expand(toks("반도체 semiconductor"), toks) == {}


def test_한_표기뿐인_묶음과_없는_사전은_무시한다(dic, tmp_path, monkeypatch):
    assert synonyms.expand(toks("혼자"), toks) == {}
    monkeypatch.setattr(synonyms, "PATH", tmp_path / "없음.yaml")
    synonyms.reset()
    assert synonyms.expand(toks("전기차"), toks) == {}


def test_저장소의_사전이_규칙을_지킨다():
    """너무 넓은 표기(한 글자·흔한 말)가 들어가면 엉뚱한 문서가 올라온다."""
    import yaml
    groups = yaml.safe_load(open("configs/synonyms.yaml", encoding="utf-8"))["groups"]
    for g in groups:
        assert len(g) >= 2
        for x in g:
            assert len(str(x).replace(" ", "")) >= 2, x


def test_동의어는_키워드_채널에만_가중치를_낮춰_들어간다(dic, monkeypatch):
    """하이브리드 검색: 벡터 질의는 원문 그대로, tsquery·IDF 배열에만 확장어."""
    from src.search import hybrid, tokenize
    monkeypatch.setattr(tokenize, "tokens", toks)
    captured = {}

    class Cur:
        description = [("id",)]

        def execute(self, sql, params=None):
            if params and "qvec" in params:
                captured.update(params)

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

    monkeypatch.setattr(hybrid, "get_conn", lambda: Conn())
    monkeypatch.setattr(hybrid, "_assert_tokenizer", lambda cur, t: None)
    monkeypatch.setattr(hybrid, "token_idf", lambda cur, t, terms: {x: 2.0 for x in terms})
    seen_q = []
    monkeypatch.setattr(hybrid.embedder, "encode_query", lambda q: seen_q.append(q) or [0.0])
    hybrid.search("전기차 보조금", "news", 5)
    assert seen_q == ["전기차 보조금"]
    assert captured["tsq"] == "전기차 | 보조금 | 전기 | 자동차 | ev"
    weights = dict(zip(captured["terms"], captured["idfs"]))
    assert weights["보조금"] == 2.0 and weights["ev"] == pytest.approx(2.0 * synonyms.WEIGHT)
    hybrid.search("전기차 보조금", "news", 5, expand_synonyms=False)
    assert captured["tsq"] == "전기차 | 보조금"
