"""검색 평가 지표 (P0-6).

TREC 관례를 따른다 — qrels는 `{query_id: {doc_id: grade}}`이고 등급은 0(무관)
이상의 정수다. `grade >= 1`을 관련으로 본다(기존 성능평가와 같은 규칙).

**판정되지 않은 문서는 무관으로 간주한다.** 풀링 방식에서 불가피하다 —
코퍼스 전체를 판정할 수 없으므로 후보에 오른 것만 판정하고, 나머지는 0으로
둔다. 이 가정 때문에 **절대값을 과대평가하지 않고 과소평가한다**(판정 안 된
정답이 있으면 점수가 깎인다). 설정 간 **비교**에는 영향이 작다.
"""

import math
from typing import Dict, List, Sequence

#: 이 등급 이상을 "관련"으로 본다. 기존 성능평가 qrels의 `relevant_rule`과 같다.
RELEVANT_GRADE = 1


def recall_at_k(ranked: Sequence[str], relevant: Dict[str, int], k: int) -> float:
    """상위 k 안에 든 관련 문서의 비율.

    관련 문서가 하나도 없는 질의는 **정의되지 않는다** — `float('nan')`을 돌려주고
    호출부가 평균에서 뺀다. 0으로 세면 "답이 없는 질의"가 점수를 끌어내린다.
    """
    gold = {d for d, g in relevant.items() if g >= RELEVANT_GRADE}
    if not gold:
        return float("nan")
    hit = len([d for d in ranked[:k] if d in gold])
    return hit / len(gold)


def mrr(ranked: Sequence[str], relevant: Dict[str, int]) -> float:
    """첫 관련 문서 순위의 역수. 없으면 0."""
    gold = {d for d, g in relevant.items() if g >= RELEVANT_GRADE}
    if not gold:
        return float("nan")
    for i, doc in enumerate(ranked, 1):
        if doc in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: Dict[str, int], k: int) -> float:
    """등급을 반영한 순위 품질. 0~1.

    Recall과 달리 **등급 2(매우 관련)를 1보다 위로 올리는 것**에 점수를 준다.
    기존 qrels가 0/1/2 3단계라 이 구분이 살아 있다.
    """
    gold = {d: g for d, g in relevant.items() if g >= RELEVANT_GRADE}
    if not gold:
        return float("nan")
    dcg = sum((2 ** relevant.get(d, 0) - 1) / math.log2(i + 1)
              for i, d in enumerate(ranked[:k], 1))
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    return dcg / idcg if idcg else float("nan")


def mean(values: Sequence[float]) -> float:
    """nan(정의되지 않은 질의)을 빼고 평균. 전부 nan이면 nan."""
    vals = [v for v in values if not math.isnan(v)]
    return sum(vals) / len(vals) if vals else float("nan")


def evaluate(runs: Dict[str, List[str]], qrels: Dict[str, Dict[str, int]],
             ks: Sequence[int] = (1, 5, 10, 20)) -> Dict[str, float]:
    """질의별 결과를 묶어 지표를 낸다.

    runs: {query_id: [doc_id, ...] 순위 순}
    qrels: {query_id: {doc_id: grade}}
    **qrels에 없는 질의는 건너뛴다** — 라벨이 없으면 채점할 수 없다.
    """
    scored = [q for q in runs if q in qrels]
    out: Dict[str, float] = {"queries": len(scored),
                             "judged": len([q for q in scored if qrels[q]])}
    for k in ks:
        out[f"recall@{k}"] = mean([recall_at_k(runs[q], qrels[q], k) for q in scored])
        out[f"ndcg@{k}"] = mean([ndcg_at_k(runs[q], qrels[q], k) for q in scored])
    out["mrr"] = mean([mrr(runs[q], qrels[q]) for q in scored])
    return out
