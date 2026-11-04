"""평가 질의 생성 — known-item 자동 생성과 풀링 (P0-6).

## known-item 질의를 자동으로 만들어도 되는 이유

질의를 **검색 결과가 아니라 문서 원문에서** 뽑기 때문이다. 검색 시스템을 전혀
쓰지 않으므로 "시스템을 자기 자신으로 평가하는" 순환이 없다.

측정하는 것은 **"이 문서의 한 구절로 그 문서를 찾아낼 수 있는가"**다.
주제 관련성(topical)은 재지 못하지만, 다음 둘에 쓸 수 있다.

1. **회귀 탐지** — 어제 되던 것이 오늘 안 되면 바로 드러난다
2. **설정 비교** — 벡터 단독 vs 하이브리드, RRF k 스윕

## 풀링 — 사람이 판정할 양을 줄인다

코퍼스 전체를 판정할 수는 없다. 여러 설정으로 검색해 **상위 k를 합친 것만**
사람에게 보여준다. 표준 IR 관행이고, 2026-11-04 기준 코퍼스가 영상 1,549건이라
질의 20건 × 풀 30건 ≈ 600건이면 한나절 작업이다.

풀을 **여러 설정에서 모으는 것이 중요하다.** 한 설정으로만 모으면 그 설정이
놓친 정답은 영원히 판정되지 않아, 그 설정이 유리해 보이는 편향이 생긴다.
"""

import logging
import random
import re
from typing import Any, Dict, List, Sequence, Tuple

logger = logging.getLogger(__name__)

#: known-item 질의로 쓸 구절의 길이 범위(글자). 너무 짧으면 여러 문서에
#: 흔하고, 너무 길면 현실의 질의와 동떨어진다.
MIN_LEN, MAX_LEN = 12, 45

_SPLIT = re.compile(r"[.!?]\s+|[\n\r]+")
_NOISE = re.compile(r"저작권|무단\s*전재|재배포|구독|좋아요|알림\s*설정|문의|홈페이지|▶|☞")


def phrases(text: str) -> List[str]:
    """문서에서 질의로 쓸 만한 구절을 뽑는다.

    정형 안내 문구(`구독`·`좋아요`·`저작권`…)는 뺀다 — 모든 문서에 있어
    정답이 하나로 정해지지 않는다. chunker가 임베딩에서 거르는 것과 같은 이유다.
    """
    out = []
    for raw in _SPLIT.split(text or ""):
        s = raw.strip()
        if MIN_LEN <= len(s) <= MAX_LEN and not _NOISE.search(s):
            out.append(s)
    return out


def known_item_queries(docs: Sequence[Tuple[str, str]], n: int = 30,
                       seed: int = 20261104) -> Tuple[List[Dict[str, Any]],
                                                      Dict[str, Dict[str, int]]]:
    """(doc_id, 본문) 목록에서 known-item 질의와 정답을 만든다.

    **구절이 그 문서에만 있는지 확인한다.** 여러 문서에 걸치면 정답이
    하나로 정해지지 않아 채점이 틀린다 — 찾아낸 게 맞는데 오답 처리된다.

    `seed`를 고정해 **같은 코퍼스면 같은 질의**가 나오게 한다. 평가가
    돌 때마다 달라지면 설정 비교가 불가능하다.
    """
    rng = random.Random(seed)
    candidates: List[Tuple[str, str]] = []
    for doc_id, text in docs:
        for p in phrases(text):
            candidates.append((doc_id, p))
    rng.shuffle(candidates)

    # 구절 → 그 구절을 담은 문서들. 하나뿐인 것만 쓴다
    owners: Dict[str, set] = {}
    for doc_id, text in docs:
        low = (text or "")
        for _, p in candidates:
            if p in low:
                owners.setdefault(p, set()).add(doc_id)

    queries, qrels = [], {}
    used_docs = set()
    for doc_id, phrase in candidates:
        if len(queries) >= n:
            break
        if doc_id in used_docs:
            continue                      # 문서당 1건 — 특정 문서에 쏠리지 않게
        if len(owners.get(phrase, set())) != 1:
            continue                      # 여러 문서에 걸친 구절은 버린다
        qid = f"ki{len(queries):03d}"
        queries.append({"query_id": qid, "query": phrase, "kind": "known_item",
                        "source_doc": doc_id})
        qrels[qid] = {doc_id: 2}
        used_docs.add(doc_id)
    logger.info("known-item 질의 %d건 (후보 구절 %d개)", len(queries), len(candidates))
    return queries, qrels


def pool(runs_by_config: Dict[str, Dict[str, List[str]]], depth: int = 15) -> Dict[str, List[str]]:
    """여러 설정의 상위 depth를 질의별로 합친다 — 사람이 판정할 후보.

    한 설정으로만 모으면 그 설정이 놓친 정답이 영원히 판정되지 않아 편향이 생긴다.
    """
    pooled: Dict[str, List[str]] = {}
    for runs in runs_by_config.values():
        for qid, ranked in runs.items():
            seen = pooled.setdefault(qid, [])
            for doc in ranked[:depth]:
                if doc not in seen:
                    seen.append(doc)
    return pooled
