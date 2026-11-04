"""평가 실행 — 설정별로 검색해 지표를 낸다 (P0-6).

비교 대상은 `CONFIGS`에 모아 둔다. 새 설정을 재려면 여기 한 줄 추가한다.
`vector`를 남겨 두는 이유 — **개선을 주장하려면 기준선이 있어야 한다.**
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from src.eval import metrics
from src.search import hybrid

logger = logging.getLogger(__name__)

#: 평가할 검색 설정. 이름 → (설명, 검색 함수)
#: 함수는 (query, source, top_k) -> [doc_id, ...]
CONFIGS: Dict[str, Dict[str, Any]] = {}


def register(name: str, desc: str):
    def _wrap(fn):
        CONFIGS[name] = {"desc": desc, "fn": fn}
        return fn
    return _wrap


@register("vector", "벡터 단독 (예전 방식, 기준선)")
def _vector(query: str, source: str, top_k: int) -> List[str]:
    from scripts.search_demo import search_vector_only
    return [str(r["id"]) for r in search_vector_only(query, source, top_k)]


@register("hybrid", "벡터 + 키워드, RRF k=60")
def _hybrid(query: str, source: str, top_k: int) -> List[str]:
    return [str(r["id"]) for r in hybrid.search(query, source, top_k, rrf_k=60)]


def _rrf_config(k: int):
    def _fn(query: str, source: str, top_k: int) -> List[str]:
        return [str(r["id"]) for r in hybrid.search(query, source, top_k, rrf_k=k)]
    return _fn


# ADR-010이 평가 항목으로 정해 둔 스윕. 정답지가 없어 미뤄 뒀던 것이다.
for _k in (10, 20, 30):
    CONFIGS[f"hybrid_k{_k}"] = {"desc": f"벡터 + 키워드, RRF k={_k}",
                                "fn": _rrf_config(_k)}


def run_config(name: str, queries: List[Dict[str, Any]], source: str,
               top_k: int = 20) -> Dict[str, List[str]]:
    """설정 하나로 전 질의를 검색해 {query_id: [doc_id,...]}를 만든다."""
    fn: Callable = CONFIGS[name]["fn"]
    runs: Dict[str, List[str]] = {}
    for q in queries:
        try:
            runs[q["query_id"]] = fn(q["query"], source, top_k)
        except Exception as e:                    # noqa: BLE001
            # 질의 하나가 실패해도 나머지는 잰다. 빈 결과로 두면 그 질의는
            # 0점이 되는데, 그게 "못 찾았다"는 사실 그대로다
            logger.warning("%s / %s 실패: %s", name, q["query_id"], e)
            runs[q["query_id"]] = []
    return runs


def compare(queries: List[Dict[str, Any]], qrels: Dict[str, Dict[str, int]],
            source: str, configs: Optional[List[str]] = None,
            top_k: int = 20) -> Dict[str, Dict[str, float]]:
    """여러 설정을 같은 질의·같은 정답지로 비교한다."""
    out = {}
    for name in (configs or list(CONFIGS)):
        runs = run_config(name, queries, source, top_k)
        out[name] = metrics.evaluate(runs, qrels)
        logger.info("%s: recall@10=%.4f mrr=%.4f",
                    name, out[name]["recall@10"], out[name]["mrr"])
    return out
