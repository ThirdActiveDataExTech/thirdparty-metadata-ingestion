"""활용 목적 기반 자동 탐색 (C2).

여기서 지켜야 할 성질 둘.

1. **근거 없는 묶음을 내지 않는다.** 왜 들어왔는지 모르면 사람이 믿을 수도,
   틀린 것을 걸러낼 수도 없다. 완료 기준이 "묶음 + 근거"다.
2. **그래프 구조가 사용자 의도를 밀어내지 않는다.** 2026-11-04 실측에서
   관계 기여가 검색 기여의 3배가 됐다 — 경로가 선형으로 더해졌기 때문이다.
   그러면 "목적에 맞는 것"이 아니라 "많이 연결된 것"이 1등이 된다.
"""

import pytest

from src.search import discovery as D


@pytest.fixture
def fake(monkeypatch):
    """검색과 관계를 가짜로 바꾼다 — 모델도 DB도 올리지 않는다."""
    def _apply(hits, neighbours, co_views=None):
        import src.search.hybrid as H
        import src.analysis.relations.store as S
        from src.api import usage as U
        monkeypatch.setattr(H, "search", lambda q, s, top_k=10, **kw: hits[:top_k])
        monkeypatch.setattr(S, "neighbours",
                            lambda ds, limit=10, **kw: neighbours.get(ds, [])[:limit])
        # 사용 이력(함께 본 데이터)도 가짜로 — 기본은 없음
        monkeypatch.setattr(U, "co_viewed",
                            lambda ds, user=None, limit=6, **kw: (co_views or {}).get(ds, [])[:limit])
    return _apply


def _hit(i, rank):
    return {"id": f"ds{i}", "title": f"데이터셋{i}", "vec_rank": rank, "kw_rank": rank}


def _nb(target, score=0.9, rtype="KEYWORD_OVERLAP", shared=None):
    return {"target_dataset_id": target, "title": f"데이터셋{target[-1]}",
            "relation_type": rtype, "score": score,
            "evidence": {"shared_keywords": shared or []}}


class TestBundle:
    def test_씨앗과_이웃이_함께_나온다(self, fake):
        fake([_hit(1, 1)], {"ds1": [_nb("ds2")]})
        r = D.discover("목적")
        ids = [b["dataset_id"] for b in r["bundle"]]
        assert "ds1" in ids and "ds2" in ids

    def test_검색_결과가_없으면_빈_묶음(self, fake):
        fake([], {})
        r = D.discover("아무것도 없는 목적")
        assert r["bundle"] == [] and r["note"]

    def test_중복이_합쳐진다(self, fake):
        # 같은 데이터셋이 검색에도 걸리고 이웃으로도 오면 한 행이어야 한다
        fake([_hit(1, 1), _hit(2, 2)], {"ds1": [_nb("ds2")]})
        ids = [b["dataset_id"] for b in D.discover("목적")["bundle"]]
        assert len(ids) == len(set(ids))

    def test_양쪽으로_오면_both로_표시한다(self, fake):
        fake([_hit(1, 1), _hit(2, 2)], {"ds1": [_nb("ds2")]})
        b = next(x for x in D.discover("목적")["bundle"] if x["dataset_id"] == "ds2")
        assert b["reached_by"] == "both"

    def test_이웃으로만_오면_relation이다(self, fake):
        fake([_hit(1, 1)], {"ds1": [_nb("ds9")]})
        b = next(x for x in D.discover("목적")["bundle"] if x["dataset_id"] == "ds9")
        assert b["reached_by"] == "relation"

    def test_상위_K를_지킨다(self, fake):
        fake([_hit(i, i) for i in range(1, 8)], {})
        assert len(D.discover("목적", top_k=3)["bundle"]) == 3


class TestEvidence:
    def test_모든_항목에_근거가_있다(self, fake):
        # 완료 기준: "목적 질의 1건으로 데이터셋 묶음 + 근거 제시"
        fake([_hit(1, 1)], {"ds1": [_nb("ds2", shared=["반도체", "메모리"])]})
        for b in D.discover("목적")["bundle"]:
            assert b["paths"], f"{b['dataset_id']}에 근거가 없다"

    def test_검색으로_온_것은_순위를_남긴다(self, fake):
        fake([_hit(1, 1)], {})
        p = D.discover("목적")["bundle"][0]["paths"][0]
        assert p["how"] == "search" and p["search_rank"] == 1

    def test_관계로_온_것은_경로를_남긴다(self, fake):
        fake([_hit(1, 1)], {"ds1": [_nb("ds2", shared=["반도체"])]})
        b = next(x for x in D.discover("목적")["bundle"] if x["dataset_id"] == "ds2")
        p = next(x for x in b["paths"] if x["how"] == "relation")
        assert p["via"] == "ds1" and p["relation_type"] == "KEYWORD_OVERLAP"
        assert p["shared_keywords"] == ["반도체"]

    def test_사람이_읽을_설명을_만든다(self, fake):
        fake([_hit(1, 1)], {"ds1": [_nb("ds2", shared=["반도체"])]})
        b = next(x for x in D.discover("목적")["bundle"] if x["dataset_id"] == "ds2")
        text = D.explain(b)
        assert "KEYWORD_OVERLAP" in text and "반도체" in text


class TestScoring:
    def test_관계_코사인을_랭킹에_쓰지_않는다(self):
        """검색 RRF(~0.03)와 관계 코사인(~0.9)은 단위가 다르다.

        그냥 더하면 관계가 전부를 압도한다(ADR-018·ADR-010의 함정).
        코사인은 **근거로만** 남기고 랭킹은 순위로 한다 — `scores`에 대입하는
        줄만 본다. 설명에 적힌 것까지 걸면 테스트가 설명을 못 쓰게 만든다.
        """
        import inspect

        assigns = [l for l in inspect.getsource(D.discover).splitlines()
                   if "scores[ds]" in l and "=" in l]
        assert assigns, "점수를 매기는 줄을 못 찾았다"
        for line in assigns:
            assert "score" not in line.split("=", 1)[1].replace("scores", "")
        assert "rrf_k" in " ".join(assigns)

    def test_씨앗_순위가_이웃_점수에_반영된다(self, fake):
        # 1위 씨앗의 이웃과 5위 씨앗의 이웃은 믿을 만한 정도가 다르다
        fake([_hit(1, 1), _hit(2, 2)], {"ds1": [_nb("ds8")], "ds2": [_nb("ds9")]})
        bundle = {b["dataset_id"]: b["score"] for b in D.discover("목적")["bundle"]}
        assert bundle["ds8"] > bundle["ds9"]

    def test_경로가_많아도_선형으로_커지지_않는다(self):
        """2026-11-04 실측: 경로 6개가 선형으로 더해져 관계 기여가 검색의 3배가 됐다.

        기하 감쇠(HOP_DECAY^i)라 합이 수렴해야 한다 —
        경로가 아무리 많아도 `HOP_DECAY/(1-HOP_DECAY)`를 넘지 못한다.
        """
        limit = D.HOP_DECAY / (1 - D.HOP_DECAY)
        total = sum(D.HOP_DECAY ** i for i in range(1, 101))
        assert total < limit + 1e-9

    def test_연결이_많으면_그래도_올라간다(self, fake):
        # 감쇠를 걸되 중심성 신호 자체를 없애지는 않는다
        fake([_hit(1, 1), _hit(2, 2), _hit(3, 3)],
             {"ds1": [_nb("ds9")], "ds2": [_nb("ds9")], "ds3": [_nb("ds8")]})
        b = {x["dataset_id"]: x["score"] for x in D.discover("목적")["bundle"]}
        assert b["ds9"] > b["ds8"]

    def test_한_다리_건넌_것은_할인된다(self):
        assert 0 < D.HOP_DECAY < 1


class TestUsagePath:
    """사용 이력 반영 추천(C2 목표선, 2026-11-11) — 씨앗을 본 사람들이 함께 본 데이터셋."""

    def test_함께_본_데이터가_근거와_함께_들어온다(self, fake):
        fake([_hit(1, 1)], {}, {"ds1": [{"dataset_id": "ds7", "title": "데이터셋7", "people": 3}]})
        r = D.discover("목적", top_k=5)
        item = next(b for b in r["bundle"] if b["dataset_id"] == "ds7")
        assert item["reached_by"] == "usage"
        assert item["paths"][0]["people"] == 3 and item["paths"][0]["via"] == "ds1"
        assert "3명이 함께 봄" in D.explain(item)

    def test_관계와_사용_이력은_경로_순번을_같이_센다(self, fake):
        # 같은 데이터셋이 관계·이력 두 갈래로 와도 감쇠가 이어져 검색 1건 기여를 넘지 않는다
        fake([_hit(1, 1)], {"ds1": [_nb("ds9")]}, {"ds1": [{"dataset_id": "ds9", "title": "데이터셋9", "people": 5}]})
        r = D.discover("목적", top_k=5)
        b = {x["dataset_id"]: x for x in r["bundle"]}
        assert [p["path_index"] for p in b["ds9"]["paths"]] == [1, 2]
        assert b["ds9"]["reached_by"] == "expanded"
        assert b["ds9"]["score"] < b["ds1"]["score"]

    def test_사용_이력을_끌_수_있다(self, fake):
        fake([_hit(1, 1)], {}, {"ds1": [{"dataset_id": "ds7", "title": "t", "people": 3}]})
        r = D.discover("목적", top_k=5, co_views_per_seed=0)
        assert all(b["dataset_id"] != "ds7" for b in r["bundle"])

    def test_사용_이력이_실패해도_묶음은_나온다(self, fake, monkeypatch):
        fake([_hit(1, 1)], {"ds1": [_nb("ds2")]})
        from src.api import usage as U
        monkeypatch.setattr(U, "co_viewed", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db")))
        assert {b["dataset_id"] for b in D.discover("목적", top_k=5)["bundle"]} == {"ds1", "ds2"}
