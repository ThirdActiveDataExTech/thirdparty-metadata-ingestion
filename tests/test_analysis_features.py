"""데이터셋 특징 추출 (B1) — 키워드가 주제를 잡는가, 통계가 모양을 지키는가.

여기서 막으려는 것은 "그럴듯한데 틀린 값"이다. TF-IDF는 잘못돼도 단어 목록이
나오고, 길이 분포는 잘못돼도 숫자가 나온다. 눈으로는 안 보인다.
"""

from collections import Counter

import pytest

from src.analysis.features import stats, text


class TestTfidf:
    def test_모든_문서에_있는_말은_버린다(self):
        # '하'처럼 어디에나 나오는 말이 상위에 오면 데이터셋이 전부 비슷해 보인다
        tf = {"a": Counter({"반도체": 10, "하": 50}),
              "b": Counter({"패션": 10, "하": 50}),
              "c": Counter({"캠핑": 10, "하": 50})}
        out = text.tfidf(tf, top_k=5)
        for ds in out:
            assert "하" not in [d["term"] for d in out[ds]]

    def test_그_데이터셋에만_있는_말이_위로_온다(self):
        tf = {"a": Counter({"반도체": 5, "기업": 5}),
              "b": Counter({"패션": 5, "기업": 5}),
              "c": Counter({"캠핑": 5, "기업": 5})}
        out = text.tfidf(tf, top_k=5)
        assert out["a"][0]["term"] == "반도체"

    def test_드물게_나온_말은_버린다(self):
        # 오탈자·고유명사 파편이 상위에 오는 것을 막는다
        tf = {"a": Counter({"반도체": 10, "ㅁㄴㅇㄹ": 1}), "b": Counter({"패션": 10})}
        terms = [d["term"] for d in text.tfidf(tf, top_k=10)["a"]]
        assert "ㅁㄴㅇㄹ" not in terms

    def test_df_상한이_실제로_걸린다(self):
        # 2026-11-02 실측으로 0.5를 골랐다. 상한이 꺼지면 기능어가 되돌아온다
        tf = {k: Counter({"공통": 10, f"고유{k}": 10}) for k in "abcd"}
        assert "공통" not in [d["term"] for d in text.tfidf(tf, max_df_ratio=0.5)["a"]]
        assert "공통" in [d["term"] for d in text.tfidf(tf, max_df_ratio=1.0)["a"]]

    def test_기본_상한은_측정값_0_5다(self):
        assert text.MAX_DF_RATIO == 0.5

    def test_빈_입력(self):
        assert text.tfidf({}) == {}

    def test_상위_K를_지킨다(self):
        tf = {"a": Counter({f"w{i}": 100 - i for i in range(50)}), "b": Counter({"x": 5})}
        assert len(text.tfidf(tf, top_k=7)["a"]) <= 7

    def test_근거를_같이_돌려준다(self):
        # dcat_dataset_relation.evidence에 넣을 값이라 점수만으로는 부족하다
        tf = {"a": Counter({"반도체": 9}), "b": Counter({"패션": 9})}
        kw = text.tfidf(tf)["a"][0]
        assert set(kw) >= {"term", "tf", "df", "idf", "tfidf"}


class TestRepresentativeChunks:
    def test_키워드가_조밀한_청크를_고른다(self):
        kws = [{"term": "반도체", "tfidf": 10.0}, {"term": "수출", "tfidf": 8.0}]
        chunks = [("날씨가 좋다", "날씨 좋"), ("반도체 수출이 늘었다", "반도체 수출 늘")]
        assert text.representative_chunks(chunks, kws)[0] == "반도체 수출이 늘었다"

    def test_긴_청크가_그냥_이기지_않는다(self):
        # 길이로 나누지 않으면 여러 주제가 섞인 긴 청크가 대표가 된다
        kws = [{"term": "반도체", "tfidf": 10.0}]
        chunks = [("반도체", "반도체"),
                  ("반도체 " + " ".join(f"잡음{i}" for i in range(40)),
                   "반도체 " + " ".join(f"잡음{i}" for i in range(40)))]
        assert text.representative_chunks(chunks, kws)[0] == "반도체"

    def test_중복_문장을_지운다(self):
        kws = [{"term": "반도체", "tfidf": 10.0}]
        chunks = [("반도체 뉴스", "반도체 뉴스")] * 5
        assert len(text.representative_chunks(chunks, kws)) == 1

    def test_키워드가_없으면_빈_결과(self):
        assert text.representative_chunks([("아무 말", "아무 말")], []) == []

    def test_걸리는_청크가_없으면_빈_결과(self):
        kws = [{"term": "반도체", "tfidf": 10.0}]
        assert text.representative_chunks([("날씨", "날씨")], kws) == []


class TestLengthDistribution:
    def test_분위수를_같이_낸다(self):
        # 본문 수집 실패분(20자)과 정상 기사(2000자)가 섞이면 평균은 둘 다 아니다
        d = stats.length_distribution([10, 20, 30, 40, 2000])
        assert d["count"] == 5 and d["min"] == 10 and d["max"] == 2000
        assert d["p50"] < d["mean"] < d["p90"]

    def test_빈_입력은_count만(self):
        assert stats.length_distribution([]) == {"count": 0}

    def test_None을_건너뛴다(self):
        assert stats.length_distribution([None, 10, None, 20])["count"] == 2


class TestBuild:
    def test_없는_값은_행을_만들지_않는다(self):
        # NULL 특징 행이 쌓이면 "값으로 필터 조회"가 쓰레기를 돌려준다
        rows = stats.build("x", {"item_count": 10})
        assert [r["feature_name"] for r in rows] == ["item_count"]

    def test_본문_보유율을_비율까지_낸다(self):
        rows = stats.build("x", {"item_count": 100, "with_content": 62})
        cr = next(r for r in rows if r["feature_name"] == "content_rate")
        assert cr["value"]["ratio"] == 0.62

    def test_본문_플래그가_없는_원천은_보유율을_안_낸다(self):
        rows = stats.build("x", {"item_count": 100})
        assert all(r["feature_name"] != "content_rate" for r in rows)

    @pytest.mark.parametrize("raw", [{}, {"item_count": None}])
    def test_빈_입력은_빈_결과(self, raw):
        assert stats.build("x", raw) == []
