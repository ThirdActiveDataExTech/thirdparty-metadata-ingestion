"""검색 평가셋 — 질의·정답·코퍼스 스냅샷 (P0-6).

## ⚠️ 평가셋은 코퍼스와 함께 고정해야 한다

2026-11-04에 이걸 비싸게 배웠다. `perf_eval/`에 3인이 median-of-3로 판정한
질의 70건·문서 443건짜리 정답지가 있었는데, **현재 코퍼스와 겹치는 문서가
0개였다.** 10-29 재수집 때 데이터셋이 통째로 교체됐기 때문이다.

라벨 자체는 썩지 않는다 — "이 질의에 이 문서가 관련 있다"는 판정은 검색
알고리즘이 바뀌어도 유효하다. 썩는 것은 **문서가 사라졌을 때**다.

그래서 평가셋에 `corpus` 스냅샷을 같이 적는다. 평가를 돌릴 때 현재 코퍼스와
대조해 **얼마나 썩었는지 먼저 알려준다.** 모르고 돌리면 Recall이 떨어진 것이
알고리즘 탓인지 문서가 사라진 탓인지 구분할 수 없다.

## 형식

기존 성능평가(`perf_eval/active_metadata_search_recall`)와 **같은 TREC 형식**을
쓴다. 팀이 이미 아는 모양이고, 그쪽 라벨을 나중에 옮겨 붙일 수 있다.

    queries.json   {"queries": [{"query_id", "query", "source", "kind", ...}]}
    qrels.json     {"qrels": {query_id: {doc_id: grade}}, "_meta": {...}}
    corpus.json    {"source": "video", "doc_ids": [...], "captured_at": ...}

## 두 종류의 질의

| kind | 만드는 주체 | 쓰임 |
|---|---|---|
| `known_item` | 자동 — 문서 본문에서 뽑는다 | **회귀 탐지.** 정답이 자명해 순환이 없다 |
| `topical` | **사람** | 품질 측정. 주제 관련성은 사람만 판정할 수 있다 |

`known_item`을 자동 생성해도 순환이 아닌 이유 — 질의를 **검색 결과가 아니라
문서 원문**에서 뽑기 때문이다. 검색 시스템을 전혀 쓰지 않는다.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

EVAL_ROOT = Path("eval/search")
QUERIES_NAME = "queries.json"
QRELS_NAME = "qrels.json"
CORPUS_NAME = "corpus.json"

RELEVANT_GRADE = 1


@dataclass
class EvalSet:
    source: str                                   # video / news / blog / dataset
    queries: List[Dict[str, Any]] = field(default_factory=list)
    qrels: Dict[str, Dict[str, int]] = field(default_factory=dict)
    corpus_ids: Set[str] = field(default_factory=set)
    corpus_captured_at: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    # ── 저장·적재 ──────────────────────────────────────────────────
    @classmethod
    def load(cls, source: str, root: Path = EVAL_ROOT) -> "EvalSet":
        d = Path(root) / source
        es = cls(source=source)
        if (d / QUERIES_NAME).is_file():
            es.queries = json.loads((d / QUERIES_NAME).read_text(encoding="utf-8"))["queries"]
        if (d / QRELS_NAME).is_file():
            blob = json.loads((d / QRELS_NAME).read_text(encoding="utf-8"))
            es.qrels = blob.get("qrels", {})
            es.meta = blob.get("_meta", {})
        if (d / CORPUS_NAME).is_file():
            blob = json.loads((d / CORPUS_NAME).read_text(encoding="utf-8"))
            es.corpus_ids = set(blob.get("doc_ids", []))
            es.corpus_captured_at = blob.get("captured_at")
        return es

    def save(self, root: Path = EVAL_ROOT) -> Path:
        d = Path(root) / self.source
        d.mkdir(parents=True, exist_ok=True)
        (d / QUERIES_NAME).write_text(
            json.dumps({"queries": self.queries}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        (d / QRELS_NAME).write_text(
            json.dumps({"_meta": self.meta, "qrels": self.qrels},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        (d / CORPUS_NAME).write_text(
            json.dumps({"source": self.source,
                        "captured_at": self.corpus_captured_at,
                        "doc_count": len(self.corpus_ids),
                        "doc_ids": sorted(self.corpus_ids)},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        return d

    # ── 코퍼스 고정 ────────────────────────────────────────────────
    def pin_corpus(self, doc_ids: Set[str]) -> None:
        self.corpus_ids = set(doc_ids)
        self.corpus_captured_at = datetime.now(timezone.utc).isoformat()

    def drift(self, current_ids: Set[str]) -> Dict[str, Any]:
        """평가셋이 얼마나 썩었는지. 평가 전에 **반드시** 본다.

        이걸 건너뛰면 Recall이 떨어진 게 알고리즘 탓인지 문서가 사라진 탓인지
        구분할 수 없다. 2026-11-04에 실제로 겪은 일이다(겹침 0%).
        """
        judged = {d for j in self.qrels.values() for d in j}
        gold = {d for j in self.qrels.values()
                for d, g in j.items() if g >= RELEVANT_GRADE}
        return {
            "corpus_pinned": len(self.corpus_ids),
            "corpus_now": len(current_ids),
            "corpus_overlap": len(self.corpus_ids & current_ids),
            "judged_docs": len(judged),
            "judged_alive": len(judged & current_ids),
            "gold_docs": len(gold),
            "gold_alive": len(gold & current_ids),
            "usable": bool(gold) and len(gold & current_ids) / len(gold) >= 0.8,
        }

    # ── 조회 ──────────────────────────────────────────────────────
    def by_kind(self, kind: str) -> List[Dict[str, Any]]:
        return [q for q in self.queries if q.get("kind") == kind]

    def unlabeled(self) -> List[Dict[str, Any]]:
        """아직 사람 판정이 없는 질의 — 라벨링 대상."""
        return [q for q in self.queries if not self.qrels.get(q["query_id"])]
