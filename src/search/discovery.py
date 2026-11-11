"""활용 목적 기반 자동 탐색 — 질의 하나로 데이터셋 **묶음**을 만든다 (C2).

**근거**: 연구개발계획서 2차년도 "활용 목적 기반 자동 탐색" /
SW 모듈 "데이터 검색·탐색 모듈(모비젠)"

검색은 "이 질의에 맞는 것 하나하나"를 돌려준다. 그런데 사람이 데이터를 찾는
이유는 대개 **무언가를 하기 위해서**이고, 그러려면 한 건이 아니라 **함께 쓸
것들**이 필요하다. 이 모듈이 그 간극을 메운다.

    자연어 목적
      → 카탈로그 하이브리드 검색        (C1)  씨앗 데이터셋
      → 관계 1-hop 확장                (B3)  이웃 데이터셋
      → 중복 제거·랭킹·근거 동봉             묶음

---

## 점수를 더하지 않는다 — 순위를 쓴다

검색 점수(RRF 약 0.03)와 관계 점수(코사인 약 0.9)는 **단위가 다르다.**
그냥 더하면 관계 점수가 모든 것을 압도한다. 정규화하려면 분포 통계가 필요한데
데이터셋이 수십 개뿐이라 그 통계를 믿을 수 없다 — [ADR-018](../../docs/adr/018_Search_Relevance_Judgment.md)과
[ADR-010](../../docs/adr/010_Korean_Fulltext_Search.md)에서 두 번 겪은 함정이다.

그래서 여기서도 **RRF**를 쓴다. 순위만 보므로 분포를 몰라도 된다.

    직접 검색된 것   1 / (k + 검색순위)
    이웃으로 온 것   HOP_DECAY / (k + 씨앗순위 + 이웃순위)

이웃 쪽에 **씨앗 순위를 더하는 것**이 핵심이다. 1위 씨앗의 이웃과 10위 씨앗의
이웃은 믿을 만한 정도가 다른데, 이웃 순위만 보면 둘이 같아진다.

## 여러 경로로 도달하면 합산하되, **감쇠를 건다**

여러 씨앗과 이어진 데이터셋은 그 묶음의 **중심에 가깝다.** 최대값을 쓰면 그
정보가 사라지므로 합산한다.

그런데 **그냥 더하면 안 된다.** 2026-11-04 실측에서 관계 기여가 검색 기여의
**3배**가 됐다 — 경로 6개가 선형으로 더해졌기 때문이다. 그러면 "목적에 맞는
것"이 아니라 **"많이 연결된 것"**이 1등이 되어, 사용자의 의도가 그래프 구조에
밀린다.

그래서 **i번째 경로에 `HOP_DECAY^i`**를 건다. 첫 경로 0.5, 둘째 0.25,
셋째 0.125 … 등비급수라 합이 `HOP_DECAY/(1-HOP_DECAY) = 1`로 수렴한다.
연결이 많을수록 올라가되 **한 건의 검색 기여를 크게 넘지 못한다.**

## 근거를 반드시 함께 돌려준다

완료 기준이 "목적 질의 1건으로 데이터셋 묶음 **+ 근거** 제시"다.
근거가 없으면 사람이 묶음을 믿을 수도, 틀린 것을 걸러낼 수도 없다.
각 데이터셋마다 **어떻게 도달했는지**(직접 검색 / 무엇을 통해 어떤 관계로)를 담는다.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: RRF 상수. 검색 쪽과 같은 값을 쓴다 — 다르게 둘 근거가 없다.
DEFAULT_RRF_K = 60

#: 한 다리 건넌 것에 매기는 할인. 직접 검색된 것보다는 약한 신호다.
#: 1.0으로 두면 이웃이 씨앗을 밀어내고, 0에 가까우면 확장이 무의미해진다.
HOP_DECAY = 0.5

#: 씨앗으로 쓸 검색 결과 수. 너무 많으면 묶음이 주제를 잃는다.
DEFAULT_SEEDS = 5

#: 씨앗당 가져올 이웃 수.
DEFAULT_NEIGHBOURS = 5

#: 사용 이력 경로(2026-11-11, C2 목표선 "사용 이력 반영 추천") — 씨앗을 본 사람들이 함께 본 데이터셋.
#: 관계(B3)와 같은 자리에 같은 감쇠로 들어간다. 사람 2명 이상이 함께 본 것만(usage.co_viewed).
#: 관계 경로와 경로 순번을 함께 센다 — 둘 다 "씨앗에서 한 다리"이고, 따로 세면 같은 데이터셋이
#: 두 갈래 등비급수를 받아 검색 기여를 넘을 수 있다.
DEFAULT_CO_VIEWS = 3


def discover(purpose: str, top_k: int = 10,
             seeds: int = DEFAULT_SEEDS,
             neighbours_per_seed: int = DEFAULT_NEIGHBOURS,
             rrf_k: int = DEFAULT_RRF_K,
             hop_decay: float = HOP_DECAY,
             co_views_per_seed: int = DEFAULT_CO_VIEWS,
             user: Any = None) -> Dict[str, Any]:
    """자연어 목적으로 데이터셋 묶음을 만든다.

    반환: {"purpose", "seeds": [...], "bundle": [{dataset_id, title, score,
           reached_by, paths: [...]}]}
    """
    from src.analysis.relations import store as rel_store
    from src.search import hybrid

    hits = hybrid.search(purpose, "dataset", top_k=seeds)
    if not hits:
        return {"purpose": purpose, "seeds": [], "bundle": [],
                "note": "검색에 걸린 데이터셋이 없다"}

    # 후보별 점수와 도달 경로를 모은다
    scores: Dict[str, float] = {}
    paths: Dict[str, List[Dict[str, Any]]] = {}
    titles: Dict[str, str] = {}

    seed_info = []
    for rank, hit in enumerate(hits, 1):
        ds = str(hit["id"])
        titles[ds] = hit["title"]
        scores[ds] = scores.get(ds, 0.0) + 1.0 / (rrf_k + rank)
        paths.setdefault(ds, []).append({
            "how": "search", "search_rank": rank,
            "vec_rank": hit.get("vec_rank"), "kw_rank": hit.get("kw_rank"),
        })
        seed_info.append({"dataset_id": ds, "title": hit["title"], "rank": rank})

    # 데이터셋별로 관계 경로가 몇 번째인지 센다 — 감쇠에 쓴다
    path_count: Dict[str, int] = {}
    for seed in seed_info:
        for hop, nb in enumerate(
                rel_store.neighbours(seed["dataset_id"], limit=neighbours_per_seed), 1):
            ds = nb["target_dataset_id"]
            titles.setdefault(ds, nb["title"])
            path_count[ds] = path_count.get(ds, 0) + 1
            # 씨앗 순위를 더한다 — 1위 씨앗의 이웃과 10위 씨앗의 이웃은 다르다.
            # 경로 순번에 기하 감쇠를 걸어 합이 수렴하게 한다(위 머리말 참조)
            weight = hop_decay ** path_count[ds]
            scores[ds] = scores.get(ds, 0.0) + weight / (rrf_k + seed["rank"] + hop)
            ev = nb.get("evidence") or {}
            paths.setdefault(ds, []).append({
                "how": "relation",
                "via": seed["dataset_id"], "via_title": seed["title"],
                "via_rank": seed["rank"],
                "relation_type": nb["relation_type"],
                "relation_score": round(float(nb["score"]), 4),
                "hop_rank": hop,
                "shared_keywords": (ev.get("shared_keywords") or [])[:6],
                "path_index": path_count[ds],
            })

    # 사용 이력 — 씨앗을 본 사람들이 함께 본 것(기록 테이블이 없거나 실패하면 건너뛴다)
    if co_views_per_seed > 0:
        try:
            from src.api import usage
            for seed in seed_info:
                for hop, cv in enumerate(usage.co_viewed(seed["dataset_id"], user=user,
                                                         limit=co_views_per_seed) or [], 1):
                    ds = cv["dataset_id"]
                    titles.setdefault(ds, cv["title"])
                    path_count[ds] = path_count.get(ds, 0) + 1
                    weight = hop_decay ** path_count[ds]
                    scores[ds] = scores.get(ds, 0.0) + weight / (rrf_k + seed["rank"] + hop)
                    paths.setdefault(ds, []).append({
                        "how": "usage", "via": seed["dataset_id"], "via_title": seed["title"],
                        "via_rank": seed["rank"], "people": cv["people"], "hop_rank": hop,
                        "path_index": path_count[ds]})
        except Exception as e:                    # noqa: BLE001
            logger.warning("사용 이력 경로 건너뜀: %s", type(e).__name__)

    ordered = sorted(scores, key=lambda d: -scores[d])[:top_k]
    bundle = []
    for ds in ordered:
        ways = {p["how"] for p in paths[ds]}
        bundle.append({
            "dataset_id": ds,
            "title": titles.get(ds, ds),
            "score": round(scores[ds], 6),
            # 직접 검색과 확장(관계·사용 이력) 양쪽으로 왔으면 그 사실이 가장 강한 신호다
            "reached_by": ("both" if "search" in ways and len(ways) > 1
                           else ways.pop() if len(ways) == 1 else "expanded"),
            "paths": paths[ds],
        })
    logger.info("목적 %r → 씨앗 %d · 묶음 %d", purpose, len(seed_info), len(bundle))
    return {"purpose": purpose, "seeds": seed_info, "bundle": bundle}


def explain(bundle_item: Dict[str, Any]) -> str:
    """한 데이터셋이 왜 묶음에 들어왔는지 사람이 읽을 한 줄."""
    reasons = []
    for p in bundle_item["paths"]:
        if p["how"] == "search":
            reasons.append(f"검색 {p['search_rank']}위")
        elif p["how"] == "usage":
            reasons.append(f"'{p['via_title'][:18]}'를 본 {p['people']}명이 함께 봄")
        else:
            via = p["via_title"][:18]
            kw = f" ({', '.join(p['shared_keywords'][:3])})" if p.get("shared_keywords") else ""
            reasons.append(f"'{via}'와 {p['relation_type']}{kw}")
    return " · ".join(reasons[:3])
