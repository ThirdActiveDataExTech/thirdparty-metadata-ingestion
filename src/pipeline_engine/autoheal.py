"""원천 형식 변화에 따른 파이프라인 자동 구성 변경 (C4 목표선 · 4차년도).

연구계획서 4차년도: "메타데이터(데이터 스키마, 형식, 소스)의 변화를 분석하여 **자동으로 파이프라인을 구성
및 변경**하는 기술". 드리프트 감지(`drift.py`)는 "스펙이 읽는 경로가 지금 안 온다"와 대체 후보까지 낸다.
여기서는 그 후보 중 **확실한 것만** 골라 매핑을 고친다.

## 확실하다고 보는 것 (둘 중 하나)

1. **잎 이름이 같다** — `snippet.publishedAt`이 `snippet.published_at`이나 `meta.publishedAt`으로 옮겨 감
   (대소문자·밑줄 무시). 이름까지 같으면 같은 값을 다른 자리로 옮긴 것으로 본다
2. **후보가 하나뿐이고 전체 경로 유사도 0.8 이상**

둘 다 아니면 고치지 않는다 — 의미가 같은지는 사람이 봐야 한다(`drift.suggest` 머리말과 같은 원칙).
고른 후보도 **이미 다른 매핑이 읽는 경로면 쓰지 않는다**(두 컬럼에 같은 값이 들어간다).

## 모드 — 스펙의 `auto_remap`

    propose (기본)  고친 매핑과 고친 스펙(YAML)을 결과로 돌려준다. 이번 수집은 원래 매핑대로
    apply           이번 수집부터 고친 매핑으로 정규화한다(해당 컬럼이 조용히 비는 것을 막는다).
                    스펙 파일은 바꾸지 않는다 — 제안 YAML을 사람이 확인해 반영한다
    off             아무것도 하지 않는다
"""

import copy
import difflib
from typing import Any, Dict, List, Optional

import yaml

from src.pipeline_engine import drift

MODES = ("off", "propose", "apply")
STRONG_RATIO = 0.8


def _leaf(path: str) -> str:
    return drift._key(path.split(".")[-1].replace(drift.LIST_MARK, ""))


def to_dig(path: str) -> str:
    """관측 표기(`items[].title`) → 스펙 표기(`items.0.title`)."""
    return path.replace(drift.LIST_MARK + ".", ".0.").replace(drift.LIST_MARK, ".0")


def pick(broken: str, candidates: List[str]) -> Optional[str]:
    """깨진 경로 하나의 확실한 대체 경로. 없으면 None."""
    same_leaf = [c for c in candidates if _leaf(c) == _leaf(broken)]
    if len(same_leaf) == 1:
        return same_leaf[0]
    if len(same_leaf) > 1:
        return None                                # 같은 이름이 여러 곳 — 고르지 않는다
    if len(candidates) == 1:
        r = difflib.SequenceMatcher(None, drift._key(broken), drift._key(candidates[0])).ratio()
        if r >= STRONG_RATIO:
            return candidates[0]
    return None


def plan(source_spec: Dict[str, Any], drift_result: Dict[str, Any]) -> Dict[str, Any]:
    """드리프트 결과로 고칠 매핑을 정한다. {"changes": [...], "unresolved": [...], "spec": 고친 스펙 | None}"""
    broken = drift_result.get("broken_mappings") or []
    suggestions = drift_result.get("suggestions") or {}
    if not broken:
        return {"changes": [], "unresolved": [], "spec": None}
    fields: Dict[str, Any] = dict(source_spec.get("fields") or {})
    in_use = {drift.normalize_spec_path(v) for v in fields.values() if isinstance(v, str)}
    changes, unresolved = [], []
    new_spec = copy.deepcopy(source_spec)
    for path in broken:
        choice = pick(path, suggestions.get(path, []))
        if choice is None or choice in in_use:
            unresolved.append({"path": path, "candidates": suggestions.get(path, []),
                               "reason": "이미 다른 매핑이 읽는 경로" if choice else "확실한 후보 없음"})
            continue
        new_path = to_dig(choice)
        for target, src in fields.items():
            if isinstance(src, str) and drift.normalize_spec_path(src) == path:
                new_spec["fields"][target] = new_path
                changes.append({"field": target, "from": src, "to": new_path})
        idf = source_spec.get("id_field")
        if isinstance(idf, str) and drift.normalize_spec_path(idf) == path:
            new_spec["id_field"] = new_path
            changes.append({"field": "id_field", "from": idf, "to": new_path})
        in_use.add(choice)
    return {"changes": changes, "unresolved": unresolved, "spec": new_spec if changes else None}


def apply_to_adapter(adapter: Any, new_spec: Dict[str, Any]) -> None:
    """어댑터의 매핑만 바꾼다(이번 실행 메모리 안). 스펙 파일은 건드리지 않는다."""
    adapter.spec = new_spec
    if hasattr(adapter, "_fields"):
        adapter._fields = dict(new_spec.get("fields") or {})
    if hasattr(adapter, "_id_field"):
        adapter._id_field = new_spec.get("id_field")


def heal(adapter: Any, mode: str, drift_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """러너가 부른다. 고칠 것이 없으면 None."""
    if mode not in MODES:
        raise ValueError(f"auto_remap은 {MODES} 중 하나여야 합니다: {mode!r}")
    if mode == "off" or not drift_result.get("broken_mappings"):
        return None
    p = plan(getattr(adapter, "spec", {}) or {}, drift_result)
    out = {"mode": mode, "changes": p["changes"], "unresolved": p["unresolved"], "applied": False}
    if p["spec"] is not None:
        out["proposed_spec_yaml"] = yaml.safe_dump(p["spec"], allow_unicode=True, sort_keys=False)
        if mode == "apply":
            apply_to_adapter(adapter, p["spec"])
            out["applied"] = True
    return out
