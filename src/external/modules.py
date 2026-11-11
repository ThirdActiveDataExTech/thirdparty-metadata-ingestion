"""외부 모듈 연계 — 어댑터 규격·등록·실행 (C7 · 4차년도).

연구계획서 4차년도 "외부 모듈 연계 기술": ◦ 외부 모듈 연동 **어댑터 규격** 제공 ◦ 어댑터 **관리** 기능으로
손쉽게 연동 ◦ 외부 모듈을 연계한 **데이터 분석과 메타데이터 수집**. 대상 예: 기존 시스템, (s)LLM, chatGPT.

## 규격

모듈 하나 = `configs/modules/<이름>.yaml` 한 장. 코드를 고치지 않고 모듈을 늘리거나 바꾼다.

    name: local_sllm
    adapter: openai_compat         # openai_compat | http_json | builtin_extractive
    endpoint: {env: LLM_BASE_URL}   # 값 대신 환경변수 이름(자격증명·주소를 저장소에 남기지 않는다)
    model: qwen3-4b-instruct-q4
    auth: {header: Authorization, env: LLM_API_KEY, prefix: "Bearer "}   # 선택
    network: internal               # internal | external
    enabled: false
    tasks: [summarize, keywords, describe, ask]
    timeout_sec: 120
    max_concurrency: 1              # CPU 추론은 동시 요청이 늘면 전체가 느려진다(ADR-013)
    fallback: builtin_extractive    # 실패하면 이 모듈로 대신한다(degrade)

## 지키는 것

- **외부망 모듈은 기본으로 막는다**(ADR-013 외부 LLM API 미사용). `network: external`은 환경변수
  `EXTERNAL_MODULES_ALLOW_EXTERNAL=true`일 때만 동작한다. 규격은 OpenAI 호환이라 정책이 바뀌면 설정만 바꾼다
- **약관상 반출할 수 없는 데이터는 외부망 모듈로 보내지 않는다**(결정 7 `src/export/policy.py` 재사용)
- **모듈이 없어도 기능이 선다** — 실패·비활성이면 `fallback`(내장 추출 요약, 네트워크 없음)으로 결과를 내고
  `degraded: true`와 사유를 붙인다
"""

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

MODULE_ROOT = Path("configs/modules")
ALLOW_EXTERNAL_ENV = "EXTERNAL_MODULES_ALLOW_EXTERNAL"
ADAPTERS = ("openai_compat", "http_json", "builtin_extractive")
TASKS = ("summarize", "keywords", "describe", "ask")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ModuleError(RuntimeError):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def _resolve(value: Any) -> Optional[str]:
    """`{env: NAME}`이면 환경변수 값, 문자열이면 그대로."""
    if isinstance(value, dict) and "env" in value:
        return os.getenv(str(value["env"]), "").strip() or None
    return value or None


@dataclass
class ModuleSpec:
    name: str
    adapter: str
    endpoint: Any = None
    model: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    network: str = "internal"
    enabled: bool = False
    tasks: List[str] = field(default_factory=lambda: list(TASKS))
    timeout_sec: float = 60
    max_concurrency: int = 1
    fallback: Optional[str] = None
    description: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModuleSpec":
        name = str(d.get("name") or "")
        if not _NAME.match(name):
            raise ModuleError(f"모듈 이름이 올바르지 않습니다: {name!r}")
        if d.get("adapter") not in ADAPTERS:
            raise ModuleError(f"{name}: 모르는 어댑터 {d.get('adapter')!r} (가능: {ADAPTERS})")
        if d.get("network", "internal") not in ("internal", "external"):
            raise ModuleError(f"{name}: network는 internal|external")
        bad = [t for t in d.get("tasks", TASKS) if t not in TASKS]
        if bad:
            raise ModuleError(f"{name}: 모르는 작업 {bad} (가능: {TASKS})")
        for key in ("endpoint",):
            v = d.get(key)
            if isinstance(v, str) and ("@" in v.split("//")[-1].split("/")[0]):
                raise ModuleError(f"{name}: 주소에 계정 정보를 넣지 마세요 — 환경변수로 주세요")
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def public(self) -> Dict[str, Any]:
        """관리 화면용 — 주소·키 값은 내보내지 않고 설정됐는지만."""
        endpoint_set = self.adapter == "builtin_extractive" or bool(_resolve(self.endpoint))
        return {"name": self.name, "adapter": self.adapter, "model": self.model, "network": self.network,
                "enabled": self.enabled, "tasks": self.tasks, "fallback": self.fallback,
                "description": self.description, "endpoint_configured": endpoint_set,
                "blocked_reason": blocked_reason(self)}


def blocked_reason(spec: ModuleSpec) -> Optional[str]:
    if not spec.enabled:
        return "비활성 모듈입니다"
    if spec.network == "external" and os.getenv(ALLOW_EXTERNAL_ENV, "").lower() != "true":
        return "외부망 모듈은 정책상 사용할 수 없습니다(ADR-013)"
    if spec.adapter != "builtin_extractive" and not _resolve(spec.endpoint):
        return "모듈 주소가 설정되지 않았습니다"
    return None


def load_all(root: Optional[Path] = None) -> Dict[str, ModuleSpec]:
    root = Path(root or MODULE_ROOT)
    out: Dict[str, ModuleSpec] = {}
    for p in sorted(root.glob("*.yaml")):
        spec = ModuleSpec.from_dict(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
        if spec.name != p.stem:
            raise ModuleError(f"{p.name}: 파일 이름과 name이 다릅니다")
        out[spec.name] = spec
    return out


# ── 어댑터 ──────────────────────────────────────────────────────────────────

_PROMPTS = {
    "summarize": "다음 데이터셋 메타데이터를 3문장 이내 한국어로 요약하세요. 원문에 없는 사실은 쓰지 마세요.",
    "keywords": "다음 데이터셋을 대표하는 한국어 키워드 10개를 쉼표로 구분해 한 줄로만 쓰세요.",
    "describe": "다음 데이터셋의 설명문을 2~4문장 한국어로 쓰세요. 원문에 없는 사실은 쓰지 마세요.",
    "ask": "다음 데이터셋 메타데이터만 근거로 질문에 한국어로 답하세요. 근거가 없으면 모른다고 답하세요.",
}


def _context_text(ctx: Dict[str, Any]) -> str:
    parts = [f"제목: {ctx.get('title') or ''}", f"설명: {ctx.get('description') or ''}"]
    if ctx.get("keywords"):
        parts.append("키워드: " + ", ".join(ctx["keywords"]))
    if ctx.get("samples"):
        parts.append("항목 예시:\n- " + "\n- ".join(ctx["samples"]))
    return "\n".join(parts)


def _headers(spec: ModuleSpec) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if spec.auth:
        val = _resolve({"env": spec.auth.get("env")}) if spec.auth.get("env") else None
        if val:
            h[str(spec.auth.get("header", "Authorization"))] = f"{spec.auth.get('prefix', '')}{val}"
    return h


def run_openai_compat(spec: ModuleSpec, task: str, ctx: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    base = _resolve(spec.endpoint).rstrip("/")
    user = _context_text(ctx) + (f"\n\n질문: {question}" if task == "ask" else "")
    body = {"model": spec.model or "default", "temperature": 0.2,
            "messages": [{"role": "system", "content": _PROMPTS[task]}, {"role": "user", "content": user}]}
    r = requests.post(f"{base}/v1/chat/completions", json=body, headers=_headers(spec), timeout=spec.timeout_sec)
    if r.status_code != 200:
        raise ModuleError(f"모듈이 HTTP {r.status_code}을 돌려주었습니다", 502)
    text = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    text = text.strip()
    if not text:
        raise ModuleError("모듈이 빈 응답을 돌려주었습니다", 502)
    return {"text": text, **({"keywords": [k.strip() for k in re.split(r"[,\n]", text) if k.strip()][:20]}
                             if task == "keywords" else {})}


def run_http_json(spec: ModuleSpec, task: str, ctx: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    """기존 시스템 연계 — 메타데이터를 JSON으로 보내고 JSON 결과를 받는다(분석 도구·사내 서비스)."""
    base = _resolve(spec.endpoint)
    r = requests.post(base, json={"task": task, "question": question, "dataset": ctx},
                      headers=_headers(spec), timeout=spec.timeout_sec)
    if r.status_code != 200:
        raise ModuleError(f"모듈이 HTTP {r.status_code}을 돌려주었습니다", 502)
    data = r.json()
    if not isinstance(data, dict):
        raise ModuleError("모듈 응답이 JSON 객체가 아닙니다", 502)
    return data


def run_builtin(spec: ModuleSpec, task: str, ctx: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    """내장 추출 요약 — 네트워크·모델 없이(A2 최소선 재사용). 원문에 없는 내용을 만들지 않는다."""
    from src.ai_meta import extractive
    from src.search import tokenize

    docs = [ctx.get("description") or ""] + list(ctx.get("samples") or [])
    tokens = [tokenize.tokens(d) for d in docs]
    idf = extractive.corpus_idf(tokens)
    if task == "keywords":
        # 키워드는 명사만, 한 글자는 뺀다(A2 runner와 같은 기준 — 동사 어간·영문 조각이 섞이지 않게)
        nouns = [[t for t in tokenize.tokens(d, keep=tokenize.NOUNS) if len(t) >= 2] for d in docs]
        flat = [t for ts in nouns for t in ts]
        return {"keywords": extractive.keywords(flat, extractive.corpus_idf(nouns) or idf, top_n=10)}
    if task in ("summarize", "describe"):
        text = " ".join(d for d in docs if d)
        summary = extractive.summarize(text, idf, tokenize.tokens)
        return {"text": summary or (ctx.get("description") or "")[:300]}
    raise ModuleError("내장 모듈은 질문 답변(ask)을 하지 않습니다 — 생성형 모듈이 필요합니다")


RUNNERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "openai_compat": run_openai_compat, "http_json": run_http_json, "builtin_extractive": run_builtin}

_SEMAPHORES: Dict[str, threading.BoundedSemaphore] = {}
_SEM_LOCK = threading.Lock()


def _semaphore(spec: ModuleSpec) -> threading.BoundedSemaphore:
    with _SEM_LOCK:
        if spec.name not in _SEMAPHORES:
            _SEMAPHORES[spec.name] = threading.BoundedSemaphore(max(1, int(spec.max_concurrency)))
        return _SEMAPHORES[spec.name]


def invoke(specs: Dict[str, ModuleSpec], name: str, task: str, ctx: Dict[str, Any],
           question: str = "", export_allowed: bool = True, _depth: int = 0) -> Dict[str, Any]:
    """모듈 하나를 부른다. 막혔거나 실패하면 fallback으로 대신하고 사유를 남긴다."""
    spec = specs.get(name)
    if spec is None:
        raise ModuleError(f"등록되지 않은 모듈입니다: {name}", 404)
    if task not in spec.tasks:
        raise ModuleError(f"{name} 모듈은 '{task}' 작업을 하지 않습니다(가능: {spec.tasks})")
    reason = blocked_reason(spec)
    if reason is None and spec.network == "external" and not export_allowed:
        reason = "약관상 외부로 보낼 수 없는 데이터라 외부망 모듈을 쓰지 않았습니다"
    t0 = time.time()
    if reason is None:
        sem = _semaphore(spec)
        if not sem.acquire(timeout=spec.timeout_sec):
            reason = "모듈이 바빠 대기 시간을 넘겼습니다"
        else:
            try:
                out = RUNNERS[spec.adapter](spec, task, ctx, question)
                return {"module": name, "task": task, "ok": True, "degraded": False,
                        "elapsed_sec": round(time.time() - t0, 2), "output": out}
            except (requests.RequestException, ValueError, ModuleError) as e:
                reason = f"모듈 호출 실패: {type(e).__name__}" if not isinstance(e, ModuleError) else str(e)
                logger.warning("외부 모듈 %s 실패 → 대체: %s", name, reason)
            finally:
                sem.release()
    if spec.fallback and spec.fallback != name and _depth < 2:
        res = invoke(specs, spec.fallback, task, ctx, question, export_allowed, _depth + 1)
        res.update({"requested_module": name, "degraded": True, "degraded_reason": reason})
        return res
    return {"module": name, "task": task, "ok": False, "degraded": True, "degraded_reason": reason,
            "elapsed_sec": round(time.time() - t0, 2), "output": None}
