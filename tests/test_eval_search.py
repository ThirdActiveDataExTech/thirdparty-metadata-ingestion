"""검색 평가 하네스 (P0-6).

평가 코드가 틀리면 **틀린 수치를 믿고 설계를 바꾸게 된다.** 검색이 나빠진 것을
좋아졌다고 읽는 쪽이, 그냥 측정이 없는 것보다 나쁘다.
"""

import math

import pytest

from src.eval import build as B, dataset as D, metrics as M


class TestMetrics:
    def test_recall(self):
        assert M.recall_at_k(["a", "b", "c"], {"a": 2, "c": 1, "z": 2}, 3) == pytest.approx(2 / 3)

    def test_등급_0은_정답이_아니다(self):
        assert M.recall_at_k(["a"], {"a": 0}, 1) != 1.0

    def test_정답이_없는_질의는_nan이다(self):
        # 0으로 세면 "답이 없는 질의"가 평균을 끌어내려 설정 비교가 왜곡된다
        assert math.isnan(M.recall_at_k(["a"], {"a": 0}, 1))
        assert math.isnan(M.mrr(["a"], {}))
        assert math.isnan(M.ndcg_at_k(["a"], {"a": 0}, 1))

    def test_평균은_nan을_뺀다(self):
        assert M.mean([1.0, float("nan"), 0.0]) == 0.5
        assert math.isnan(M.mean([float("nan")]))

    def test_mrr은_첫_정답_순위의_역수(self):
        assert M.mrr(["x", "a"], {"a": 1}) == 0.5
        assert M.mrr(["x", "y"], {"a": 1}) == 0.0

    def test_ndcg는_등급_높은_것을_위로_올리면_커진다(self):
        rel = {"hi": 2, "lo": 1}
        good = M.ndcg_at_k(["hi", "lo"], rel, 2)
        bad = M.ndcg_at_k(["lo", "hi"], rel, 2)
        assert good > bad and good == pytest.approx(1.0)

    def test_라벨_없는_질의는_채점에서_빠진다(self):
        out = M.evaluate({"q1": ["a"], "q2": ["b"]}, {"q1": {"a": 2}})
        assert out["queries"] == 1


class TestKnownItem:
    def test_질의를_문서_원문에서_뽑는다(self):
        # 검색 결과를 쓰지 않으므로 순환이 아니다
        docs = [("d1", "고대역폭 메모리는 적층 기술로 만들어진다"),
                ("d2", "완전히 다른 내용이 여기에 들어가 있다")]
        qs, qrels = B.known_item_queries(docs, n=5)
        for q in qs:
            assert q["query"] in dict(docs)[q["source_doc"]]
            assert qrels[q["query_id"]] == {q["source_doc"]: 2}

    def test_여러_문서에_걸친_구절은_쓰지_않는다(self):
        # 정답이 하나로 안 정해지면 찾아낸 것이 오답 처리된다
        same = "완전히 똑같은 문장이 양쪽에 들어 있다"
        qs, _ = B.known_item_queries([("d1", same), ("d2", same)], n=5)
        assert qs == []

    def test_문서당_한_건만_만든다(self):
        text = ". ".join(f"충분히 긴 서로 다른 문장 번호 {i}" for i in range(10))
        qs, _ = B.known_item_queries([("d1", text)], n=10)
        assert len(qs) <= 1

    def test_seed가_같으면_같은_질의가_나온다(self):
        # 돌 때마다 달라지면 설정 비교가 불가능하다
        docs = [(f"d{i}", f"서로 다른 충분히 긴 문장 번호 {i}입니다") for i in range(20)]
        a, _ = B.known_item_queries(docs, n=5)
        b, _ = B.known_item_queries(docs, n=5)
        assert [q["query"] for q in a] == [q["query"] for q in b]

    def test_정형_안내문구는_제외한다(self):
        # 모든 문서에 있어 정답이 하나로 정해지지 않는다
        assert B.phrases("구독과 좋아요 눌러주시면 감사하겠습니다") == []
        assert B.phrases("저작권자 ⓒ 무단 전재 및 재배포 금지합니다") == []


class TestPooling:
    def test_여러_설정의_상위를_합친다(self):
        # 한 설정으로만 모으면 그 설정이 놓친 정답이 영원히 판정되지 않는다
        pooled = B.pool({"a": {"q": ["x", "y"]}, "b": {"q": ["y", "z"]}}, depth=2)
        assert pooled["q"] == ["x", "y", "z"]

    def test_depth를_지킨다(self):
        pooled = B.pool({"a": {"q": list("abcdef")}}, depth=3)
        assert pooled["q"] == ["a", "b", "c"]


class TestCorpusPinning:
    """평가셋이 썩는 것을 잡는다 — 2026-11-04에 기존 정답지가 0% 겹침이었다."""

    def _es(self):
        es = D.EvalSet(source="video")
        es.queries = [{"query_id": "q1", "query": "x", "kind": "topical"}]
        es.qrels = {"q1": {"alive": 2, "gone": 2, "irrelevant": 0}}
        es.pin_corpus({"alive", "gone", "other"})
        return es

    def test_코퍼스가_그대로면_쓸_수_있다(self):
        d = self._es().drift({"alive", "gone", "other"})
        assert d["usable"] and d["gold_alive"] == 2

    def test_정답이_사라지면_쓸_수_없다고_알린다(self):
        # 모르고 돌리면 Recall이 떨어진 게 알고리즘 탓인지 문서 소실 탓인지 모른다
        d = self._es().drift({"alive"})
        assert not d["usable"] and d["gold_alive"] == 1 and d["gold_docs"] == 2

    def test_판정_0등급_문서는_정답에_안_센다(self):
        d = self._es().drift({"alive", "gone", "irrelevant"})
        assert d["gold_docs"] == 2 and d["judged_docs"] == 3

    def test_고정_시각을_남긴다(self):
        assert self._es().corpus_captured_at


class TestRoundTrip:
    def test_저장하고_읽으면_같다(self, tmp_path):
        es = D.EvalSet(source="video")
        es.queries = [{"query_id": "q1", "query": "치질 수술", "kind": "topical"}]
        es.qrels = {"q1": {"d1": 2}}
        es.pin_corpus({"d1", "d2"})
        es.save(root=tmp_path)
        back = D.EvalSet.load("video", root=tmp_path)
        assert back.queries == es.queries
        assert back.qrels == es.qrels
        assert back.corpus_ids == es.corpus_ids

    def test_라벨_없는_질의를_가려낸다(self):
        es = D.EvalSet(source="video")
        es.queries = [{"query_id": "a", "query": "x"}, {"query_id": "b", "query": "y"}]
        es.qrels = {"a": {"d": 1}}
        assert [q["query_id"] for q in es.unlabeled()] == ["b"]


class TestRealEvalSet:
    """저장소에 실제로 들어 있는 평가셋이 규약을 지키는지."""

    def test_질의가_두_종류로_나뉜다(self):
        es = D.EvalSet.load("video")
        assert es.by_kind("known_item") and es.by_kind("topical")

    def test_known_item은_전부_라벨이_있다(self):
        es = D.EvalSet.load("video")
        for q in es.by_kind("known_item"):
            assert es.qrels.get(q["query_id"]), f"{q['query_id']} 라벨 없음"

    def test_topical_난이도가_고르게_섞여_있다(self):
        # 한 종류만 모으면 그 종류에 유리한 설정이 이기고,
        # 그게 전반적 개선인 줄 착각하게 된다
        es = D.EvalSet.load("video")
        kinds = {q.get("difficulty") for q in es.by_kind("topical")}
        assert len(kinds) >= 4
        assert "no_answer" in kinds      # "답 없음" 판정도 재야 한다

    def test_코퍼스가_고정돼_있다(self):
        es = D.EvalSet.load("video")
        assert es.corpus_ids and es.corpus_captured_at
