"""파이프라인 러너 — 스펙(YAML) 하나로 수집부터 적재까지 (C3 최소선).

**근거**: 연구개발계획서 2차년도 "템플릿 기반 파이프라인 구성"

    configs/pipelines/<이름>.yaml
      source_spec:  configs/sources/<원천>.yaml   ← A1 어댑터 스펙
      dataset_id:   urn:…
      target:       테이블·컬럼 매핑·충돌 키
      steps:        [collect, normalize, store, postprocess]

파이프라인을 **코드가 아니라 선언으로** 만든다. 기존 `src/pipelines/*.py` 5종은
그대로 둔다 — 점진 이관이 목표선이고, 지금 갈아치우면 검증된 것을 잃는다.

---

## 단계를 고정한다

최소선은 **4단계 고정**이다. 조합 자유화·조건 분기는 목표선이다.
지금 자유화하면 스펙이 작은 프로그래밍 언어가 되고, 그걸 디버깅하는 비용이
파이프라인을 손으로 쓰는 비용보다 커진다.

## 실패는 단계 단위로 기록한다

어느 단계에서 멈췄는지가 남지 않으면, 0건이 나왔을 때 원천이 빈 것인지
매핑이 틀린 것인지 알 수 없다.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.collectors.adapters.file_source import adapter_from_file
from src.pipeline_engine import drift, steps

logger = logging.getLogger(__name__)

PIPELINE_ROOT = Path("configs/pipelines")

#: 최소선의 고정 단계. 스펙이 일부만 고르는 것은 허용하되 **순서는 바꾸지 않는다** —
#: normalize 없이 store하면 원천 모양이 그대로 들어가고, store 없이 postprocess하면
#: 빈 데이터셋을 임베딩한다.
STEP_ORDER = ["collect", "normalize", "store", "postprocess"]

#: 원천 스키마 드리프트 감지를 단계로 만들지 않는다. 데이터를 옮기는 일이 아니라
#: **수집 결과를 재는 일**이고, 단계로 두면 스펙이 그걸 끌 수 있게 된다 —
#: 끌 수 있는 감지기는 결국 꺼져 있다. 스펙의 `drift: false`로만 뺀다.
DRIFT_DEFAULT = True


class PipelineError(RuntimeError):
    pass


def load(name_or_path: str) -> Dict[str, Any]:
    """파이프라인 스펙을 읽는다. 이름만 주면 `configs/pipelines/`에서 찾는다."""
    p = Path(name_or_path)
    if not p.is_file():
        p = PIPELINE_ROOT / f"{name_or_path}.yaml"
    if not p.is_file():
        raise PipelineError(f"파이프라인 스펙이 없다: {name_or_path}")
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    for key in ("source_spec", "dataset_id", "target"):
        if not spec.get(key):
            raise PipelineError(f"{p}: 스펙에 {key}가 없다")
    target = spec["target"]
    for key in ("table", "columns", "conflict_key"):
        if not target.get(key):
            raise PipelineError(f"{p}: target에 {key}가 없다")
    bad = [s for s in spec.get("steps", STEP_ORDER) if s not in STEP_ORDER]
    if bad:
        raise PipelineError(f"{p}: 알 수 없는 단계 {bad} (가능: {STEP_ORDER})")
    return spec


def run(name_or_path: str, limit: Optional[int] = None,
        dry_run: bool = False) -> Dict[str, Any]:
    """스펙대로 파이프라인을 돌린다. 단계별 결과를 돌려준다."""
    spec = load(name_or_path)
    dataset_id = spec["dataset_id"]
    target = spec["target"]
    # 스펙이 고른 단계를 **고정 순서로** 정렬한다. 스펙의 나열 순서를 믿지 않는다
    chosen = [s for s in STEP_ORDER if s in spec.get("steps", STEP_ORDER)]

    adapter = adapter_from_file(spec["source_spec"])      # kind: rest_json(기본) | file
    result: Dict[str, Any] = {"pipeline": name_or_path, "dataset_id": dataset_id,
                              "steps": {}, "ok": True}
    raws: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    t0 = time.time()

    for step in chosen:
        started = time.time()
        try:
            if step == "collect":
                raws = steps.collect(adapter, query=spec.get("query"),
                                     limit=limit or spec.get("limit"))
                result["steps"][step] = {"count": len(raws)}
                if spec.get("drift", DRIFT_DEFAULT):
                    result["drift"] = _check_drift(dataset_id, raws, adapter, dry_run)
            elif step == "normalize":
                rows = steps.normalize(adapter, raws)
                result["steps"][step] = {"count": len(rows)}
            elif step == "store":
                result["steps"][step] = steps.store(
                    rows, dataset_id, target["table"], target["columns"],
                    target["conflict_key"], target.get("defaults"), dry_run=dry_run)
            elif step == "postprocess":
                result["steps"][step] = steps.postprocess(
                    dataset_id, spec.get("source_type", ""),
                    spec.get("postprocess", []), dry_run=dry_run)
        except Exception as e:                    # noqa: BLE001
            # 어느 단계에서 멈췄는지 남긴다. 없으면 0건이 나왔을 때
            # 원천이 빈 것인지 매핑이 틀린 것인지 알 수 없다
            logger.error("[%s] %s 단계 실패: %s", name_or_path, step, e)
            result["steps"][step] = {"error": str(e)[:500]}
            result["ok"] = False
            break
        finally:
            result["steps"].setdefault(step, {})["seconds"] = round(time.time() - started, 2)

    result["seconds"] = round(time.time() - t0, 2)
    return result


def _check_drift(dataset_id: str, raws: List[Dict[str, Any]],
                 adapter: Any, dry_run: bool) -> Dict[str, Any]:
    """원천 모양을 재서 기록한다 (C4).

    **감지 실패가 수집을 무효로 만들지 않는다.** 데이터는 이미 손에 있다 —
    여기서 예외를 올리면 "원천 모양을 못 쟀다"는 이유로 멀쩡한 수집이 버려진다.
    """
    try:
        return drift.check(dataset_id, raws, getattr(adapter, "spec", {}) or {},
                           dry_run=dry_run)
    except Exception as e:                        # noqa: BLE001
        logger.warning("드리프트 감지 실패(수집은 유효): %s", e)
        return {"status": "error", "severity": "none", "error": str(e)[:300]}


def available() -> List[str]:
    """쓸 수 있는 파이프라인 이름."""
    if not PIPELINE_ROOT.is_dir():
        return []
    return sorted(p.stem for p in PIPELINE_ROOT.glob("*.yaml"))
