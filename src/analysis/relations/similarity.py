"""데이터셋 간 관계 산출 — 두 축을 따로 재고 상위 K만 남긴다 (B2).

**근거**: 연구개발계획서 1차년도 "데이터 패턴 모델링 기반 데이터 관계 분석 기술"

합의된 `relation_type_registry`에 비정형에 쓸 수 있는 관계가 2종이다.

    SEMANTICALLY_RELATED  의미 유사   ← 대표 요약 임베딩
    KEYWORD_OVERLAP       키워드 유사 ← 키워드 임베딩

**두 축을 합치지 않는다.** 합치면 왜 비슷한지 설명할 수 없고,
`dcat_dataset_relation.evidence`가 빈 채로 남는다. B2의 완료 기준이
"상위 관련 데이터셋이 **근거 지표와 함께** 재현 가능하게 산출"이다.

---

## 설계가 측정에서 나온 두 가지 (2026-11-02)

**1. 고정 임계값을 쓰지 않는다 — 상위 K만 남긴다.**

청크 최대 유사도로 데이터셋 300쌍을 재 보니 전부 0.8922~0.9921에 뭉쳤다.
가장 무관한 쌍(`양자컴퓨팅 뉴스 ↔ 패션 페르소나`)이 0.8945다. 어떤 값을
골라도 전부 연결하거나 전부 끊는다. [ADR-018](../../../docs/adr/018_Search_Relevance_Judgment.md)이
검색에서 측정한 e5 점수 압축이 관계에서도 같다.

**2. 자카드가 아니라 임베딩으로 잰다.**

별첨은 `KEYWORD_OVERLAP`을 자카드로 정의했으나 실측에서 역전이 나왔다.

    자카드 0.000  패션의류 검색 트렌드 ↔ 패션 전체 검색 트렌드   공유 없음
    자카드 0.200  전기차 충전 블로그   ↔ 캠핑 장비 주간 블로그   공유: 가격 공간 디자인

어휘가 다르면 못 잡고(`의류`≠`패션`), 집합 크기에 휘둘리며(1~2개짜리끼리는
자카드 1.000), 일반어 공유로 거짓 엣지가 선다.
[ADR-019](../../../docs/adr/019_Dataset_Profile_Vectors.md) §회신 2건.

---

## 입력은 B1 산출물이다

등록 메타데이터는 쓰지 않는다 — `description`이 평균 24~36자, `keywords`가
평균 2~3개다. `meta_feature`의 `representative_text`·`top_keywords`를 쓴다.

**벡터를 저장하지 않고 그때그때 만든다.** 데이터셋이 25개뿐이라 몇 초면 끝난다.
영속화 위치(`vec_role`)는 와이즈넛 회신 대기 중이고(ADR-019), 확정되면 이 모듈은
벡터 출처만 바꾸면 된다 — 비교 로직은 그대로다.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.database.db import get_conn
from src.embedding import embedder

logger = logging.getLogger(__name__)

#: 데이터셋당 남길 이웃 수. 상위 K는 **방향이 있다** — A의 top-5와 B의 top-5가
#: 다르므로 양방향 저장이 중복이 아니다. B3의 1-hop 조회가 단순 SELECT가 된다.
TOP_K = 5

#: 축 → (relation_type, 어느 meta_feature를 쓰는가)
AXES = {
    "summary":  ("SEMANTICALLY_RELATED", "representative_text"),
    "keywords": ("KEYWORD_OVERLAP",      "top_keywords"),
}

#: `method` 컬럼의 CHECK 허용값 중 하나. 규칙 기반('rule')이 아니라 임베딩이다.
METHOD = "embedding"

#: 사람 검토 전이라는 뜻. 자동 산출을 확정으로 쓰지 않는 것은
#: [ADR-020](../../../docs/adr/020_Category_Suggestion_Not_Assignment.md)과 같은 태도다.
STATUS = "PENDING"


def _axis_text(feature_name: str, value: Any) -> Optional[str]:
    """meta_feature 값을 임베딩할 한 덩어리 문자열로 만든다."""
    if not value:
        return None
    if feature_name == "representative_text":
        # 대표 문장 목록 — 이어 붙이면 데이터셋의 주제가 담긴 한 문단이 된다
        return " ".join(str(v) for v in value)
    if feature_name == "top_keywords":
        # 키워드는 TF-IDF 순서대로 이어 붙인다. 가중치는 순서에 이미 담겨 있다
        return " ".join(d["term"] for d in value if d.get("term"))
    return None


def load_axis(axis: str) -> Dict[str, str]:
    """축 하나에 대한 {dataset_id: 임베딩할 텍스트}."""
    _, feature = AXES[axis]
    cur = get_conn().cursor()
    cur.execute(
        "SELECT dataset_id, value FROM meta_feature "
        "WHERE scope = 'dataset' AND feature_name = %s",
        (feature,),
    )
    out = {}
    for dataset_id, value in cur.fetchall():
        text = _axis_text(feature, value)
        if text:
            out[dataset_id] = text
    cur.close()
    return out


def rank(texts: Dict[str, str], top_k: int = TOP_K) -> Dict[str, List[Tuple[str, float]]]:
    """각 데이터셋의 상위 K 이웃을 코사인으로 고른다.

    **자기 자신은 뺀다.** 코사인 1.0이라 빼지 않으면 항상 1위를 차지한다.
    """
    ids = sorted(texts)
    if len(ids) < 2:
        return {}

    # 문서 프리픽스를 쓴다 — 질의가 아니라 문서끼리 비교하는 모양이다
    vecs = np.array(embedder.encode([texts[i] for i in ids]))
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0            # 빈 텍스트가 섞여도 0으로 나누지 않는다
    unit = vecs / norms
    sims = unit @ unit.T
    np.fill_diagonal(sims, -np.inf)    # 자기 자신 제외

    out: Dict[str, List[Tuple[str, float]]] = {}
    k = min(top_k, len(ids) - 1)
    for i, src in enumerate(ids):
        order = np.argsort(-sims[i])[:k]
        out[src] = [(ids[j], float(sims[i][j])) for j in order]
    return out


def _evidence(axis: str, src_text: str, dst_text: str, score: float) -> Dict[str, Any]:
    """왜 이 쌍이 묶였는지. 비면 결과를 해석할 수도 고칠 수도 없다."""
    ev: Dict[str, Any] = {"axis": axis, "cosine": round(score, 4),
                          "model": embedder.MODEL_NAME}
    if axis == "keywords":
        a, b = set(src_text.split()), set(dst_text.split())
        shared = sorted(a & b)
        # 공유 키워드는 사람이 결과를 납득하는 가장 빠른 근거다. 다만 **점수의
        # 근거는 아니다** — 임베딩은 겹치지 않는 동의어도 잡는다(`의류`↔`패션`).
        ev["shared_keywords"] = shared[:10]
        ev["shared_count"] = len(shared)
        ev["jaccard"] = round(len(a & b) / len(a | b), 4) if (a | b) else 0.0
    return ev


def build(top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """두 축을 각각 랭크해 `dcat_dataset_relation`에 넣을 행 목록을 만든다."""
    rows: List[Dict[str, Any]] = []
    for axis, (relation_type, feature) in AXES.items():
        texts = load_axis(axis)
        if len(texts) < 2:
            logger.warning("%s 축: 대상 데이터셋이 %d개뿐이라 건너뛴다 (%s 미산출)",
                           axis, len(texts), feature)
            continue
        ranked = rank(texts, top_k)
        for src, neighbours in ranked.items():
            for dst, score in neighbours:
                rows.append({
                    "source_dataset_id": src,
                    "target_dataset_id": dst,
                    "relation_type": relation_type,
                    "score": score,
                    "method": METHOD,
                    "status": STATUS,
                    "evidence": _evidence(axis, texts[src], texts[dst], score),
                })
        logger.info("%s 축: 데이터셋 %d개 → 관계 %d건",
                    axis, len(texts), len(texts) * min(top_k, len(texts) - 1))
    return rows
