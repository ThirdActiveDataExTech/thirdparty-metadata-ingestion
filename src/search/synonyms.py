"""검색 동의어 확장 (C1 · 2026-11-11) — `configs/synonyms.yaml`.

"전기차"로 찾을 때 "EV"만 쓴 문서도 걸리게 한다. **키워드 채널에만** 더한다(ADR-013 "확장어는 키워드 채널에만
OR로 추가한다 — 벡터 채널에 섞으면 주제가 흐려진다"). 더한 낱말은 원래 질의어보다 낮은 가중치(`WEIGHT`)로
IDF 점수에 들어간다 — 원래 표기를 담은 문서가 확장어만 담은 문서보다 앞서야 한다.

비교는 검색 토크나이저가 끊은 **토큰 묶음** 단위다. 표기가 여러 토큰(`생성형 AI`)이면 그 토큰이 질의에
모두 있을 때만 맞는 것으로 본다.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

logger = logging.getLogger(__name__)

PATH = Path("configs/synonyms.yaml")
#: 확장어의 IDF 가중치 배율
WEIGHT = 0.7

_lock = threading.Lock()
_groups: Optional[List[List[Tuple[str, ...]]]] = None


def _load(tokenize_fn) -> List[List[Tuple[str, ...]]]:
    if not PATH.is_file():
        return []
    raw = yaml.safe_load(PATH.read_text(encoding="utf-8")) or {}
    groups = []
    for g in raw.get("groups") or []:
        forms = [tuple(tokenize_fn(str(x))) for x in g if str(x).strip()]
        forms = [f for f in dict.fromkeys(forms) if f]
        if len(forms) >= 2:
            groups.append(forms)
    logger.info("동의어 묶음 %d개", len(groups))
    return groups


def groups(tokenize_fn) -> List[List[Tuple[str, ...]]]:
    global _groups
    if _groups is None:
        with _lock:
            if _groups is None:
                _groups = _load(tokenize_fn)
    return _groups


def reset() -> None:
    global _groups
    _groups = None


def expand(terms: Sequence[str], tokenize_fn) -> Dict[str, float]:
    """질의 토큰 → {추가할 토큰: 가중치}. 원래 질의에 있는 토큰은 넣지 않는다."""
    have = set(terms)
    extra: Dict[str, float] = {}
    for forms in groups(tokenize_fn):
        if not any(set(f) <= have for f in forms):
            continue
        for f in forms:
            if set(f) <= have:
                continue
            for t in f:
                if t not in have:
                    extra[t] = max(extra.get(t, 0.0), WEIGHT)
    return extra
