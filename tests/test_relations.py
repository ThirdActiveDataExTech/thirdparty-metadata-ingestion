"""데이터셋 간 관계 산출 (B2) — 상위 K, 두 축 분리, 근거 기록.

여기서 막으려는 것은 "그럴듯한데 쓸 수 없는 관계"다. 점수만 있고 근거가 없으면
결과를 해석할 수도 고칠 수도 없고, 자기 자신이 섞여 들어오면 항상 1위를 차지한다.
둘 다 눈으로는 잘 안 보인다.
"""

import numpy as np
import pytest

from src.analysis.relations import similarity as S


@pytest.fixture
def fake_encode(monkeypatch):
    """텍스트를 결정적인 벡터로 바꾼다 — 모델을 올리지 않는다."""
    def _apply(mapping):
        monkeypatch.setattr(S.embedder, "encode", lambda texts: [mapping[t] for t in texts])
        monkeypatch.setattr(S.embedder, "MODEL_NAME", "test-model")
    return _apply


class TestRank:
    def test_자기_자신은_이웃에_없다(self, fake_encode):
        # 코사인 1.0이라 빼지 않으면 모든 데이터셋의 1위가 자기 자신이 된다
        fake_encode({"a": [1, 0], "b": [0.9, 0.1], "c": [0, 1]})
        out = S.rank({"A": "a", "B": "b", "C": "c"}, top_k=3)
        for src, neighbours in out.items():
            assert src not in [d for d, _ in neighbours]

    def test_가까운_것이_위로_온다(self, fake_encode):
        fake_encode({"a": [1, 0], "b": [0.99, 0.14], "c": [0, 1]})
        out = S.rank({"A": "a", "B": "b", "C": "c"}, top_k=2)
        assert out["A"][0][0] == "B"

    def test_상위_K를_지킨다(self, fake_encode):
        fake_encode({f"t{i}": [1, i * 0.01] for i in range(6)})
        out = S.rank({f"D{i}": f"t{i}" for i in range(6)}, top_k=2)
        assert all(len(v) == 2 for v in out.values())

    def test_K가_데이터셋_수보다_크면_잘린다(self, fake_encode):
        fake_encode({"a": [1, 0], "b": [0, 1]})
        out = S.rank({"A": "a", "B": "b"}, top_k=10)
        assert all(len(v) == 1 for v in out.values())   # 자기 제외 1개뿐

    def test_데이터셋이_하나면_관계가_없다(self, fake_encode):
        fake_encode({"a": [1, 0]})
        assert S.rank({"A": "a"}) == {}

    def test_영벡터가_섞여도_0으로_나누지_않는다(self, fake_encode):
        # 빈 텍스트가 들어오면 norm이 0이 된다. NaN이 섞이면 순위가 조용히 망가진다
        fake_encode({"a": [0, 0], "b": [1, 0], "c": [0, 1]})
        out = S.rank({"A": "a", "B": "b", "C": "c"}, top_k=2)
        for neighbours in out.values():
            assert all(not np.isnan(s) for _, s in neighbours)


class TestAxes:
    def test_두_축이_서로_다른_관계_유형을_쓴다(self):
        types = {rt for rt, _ in S.AXES.values()}
        assert types == {"SEMANTICALLY_RELATED", "KEYWORD_OVERLAP"}

    def test_축은_B1_산출물을_입력으로_쓴다(self):
        # 등록 메타데이터는 쓰지 않는다 — description 24~36자, keywords 2~3개
        features = {f for _, f in S.AXES.values()}
        assert features == {"representative_text", "top_keywords"}

    def test_대표문장은_이어붙인다(self):
        assert S._axis_text("representative_text", ["첫 문장", "둘째 문장"]) == "첫 문장 둘째 문장"

    def test_키워드는_순서대로_이어붙인다(self):
        v = [{"term": "반도체"}, {"term": "메모리"}]
        assert S._axis_text("top_keywords", v) == "반도체 메모리"

    def test_빈_값은_None(self):
        assert S._axis_text("top_keywords", []) is None
        assert S._axis_text("representative_text", None) is None


class TestEvidence:
    def test_점수와_축을_남긴다(self):
        ev = S._evidence("summary", "가 나", "나 다", 0.8123)
        assert ev["axis"] == "summary" and ev["cosine"] == 0.8123

    def test_키워드_축은_공유_키워드를_남긴다(self):
        # 사람이 결과를 납득하는 가장 빠른 근거다
        ev = S._evidence("keywords", "반도체 메모리 수출", "반도체 메모리 로봇", 0.9)
        assert ev["shared_keywords"] == ["메모리", "반도체"]
        assert ev["shared_count"] == 2

    def test_자카드도_같이_남긴다(self):
        # 점수의 근거는 아니지만, 임베딩이 자카드보다 무엇을 더 잡았는지 보인다
        ev = S._evidence("keywords", "가 나", "가 다", 0.9)
        assert ev["jaccard"] == round(1 / 3, 4)

    def test_겹치는_키워드가_없어도_관계는_성립한다(self):
        # ADR-019의 핵심 — `의류`와 `패션`은 집합 연산에서 남남이지만 의미는 같다
        ev = S._evidence("keywords", "의류", "패션", 0.98)
        assert ev["jaccard"] == 0.0 and ev["shared_count"] == 0
        assert ev["cosine"] == 0.98

    def test_요약_축에는_키워드_근거가_없다(self):
        assert "shared_keywords" not in S._evidence("summary", "가", "나", 0.5)


class TestWriteContract:
    def test_method는_테이블_CHECK_허용값이다(self):
        assert S.METHOD in ("rule", "embedding", "llm", "gnn")

    def test_자동_산출은_PENDING으로_넣는다(self):
        # 사람 검토 전이라는 뜻. 자동 판정을 확정으로 쓰지 않는다(ADR-020과 같은 태도)
        assert S.STATUS == "PENDING"

    def test_상위_K_기본값이_있다(self):
        # 고정 임계값을 쓰지 않는 대신 K로 자른다 — 300쌍이 전부 0.89~0.99에 뭉친다
        assert S.TOP_K > 0
