"""외부 모듈 관리 API (C7) — 등록된 모듈 목록·상태 확인·실행. 관리자 전용."""

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.auth import require_admin
from src.api.db_scope import ReleaseDbRoute
from src.external import modules as X
from src.external import service

router = APIRouter(prefix="/v1/console", tags=["외부 모듈"], route_class=ReleaseDbRoute,
                   dependencies=[Depends(require_admin)])


def _specs():
    try:
        return X.load_all()
    except X.ModuleError as e:
        raise HTTPException(500, f"모듈 설정 오류: {e}")


@router.get("/modules")
def list_modules():
    """등록된 외부 모듈과 쓸 수 있는지(막힌 사유). 주소·키 값은 보여 주지 않습니다."""
    return {"items": [s.public() for s in _specs().values()],
            "adapters": list(X.ADAPTERS), "tasks": list(X.TASKS)}


@router.post("/modules/{name}/run")
def run_module(name: str, body: Dict[str, Any] = Body(...)):
    """데이터셋 하나에 모듈 작업을 실행합니다. 모듈이 막혔거나 실패하면 대체 모듈 결과와 사유를 줍니다.

    body: {"task": summarize|keywords|describe|ask, "dataset_id": "...", "question": "...", "save": false}
    """
    task = body.get("task")
    dataset_id = body.get("dataset_id")
    if task not in X.TASKS:
        raise HTTPException(400, f"작업은 {list(X.TASKS)} 중 하나여야 합니다")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise HTTPException(400, "데이터셋 ID를 보내 주세요")
    question = str(body.get("question") or "")[:1000]
    if task == "ask" and not question:
        raise HTTPException(400, "질문을 보내 주세요")
    try:
        return service.run(name, task, dataset_id, question=question, save=bool(body.get("save")), specs=_specs())
    except X.ModuleError as e:
        raise HTTPException(e.code, str(e))
