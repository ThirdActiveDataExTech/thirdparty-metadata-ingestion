"""포털 관리 API — 등록·수정·삭제·수집 실행·패키지·추이 (D1 최소선).

portal-mockup의 등록·수정·삭제 화면은 **전부 가짜였다** — 메모리에만 쓰고, 입력한
API Key·Client Secret을 브라우저 콘솔에 찍고, "수집 요청이 접수되었습니다"를 띄웠다.
이 모듈이 그 자리를 실제 동작으로 채운다.

등록 입력 명세는 docs/api/01_Dataset_Registration_Scenario.md를 따른다.
등록 로직은 scripts/register_dataset.py를 **그대로 재사용한다** — 따로 구현하면
CLI 등록과 화면 등록의 결과가 조용히 달라진다.

---

## 권한

등록·수정·삭제·수집 실행·파이프라인·평가·연합은 **관리자만**(`require_admin`, 시제품 로그인 —
ADR-021). 사용자 등록은 `/v1/my`(my.py)가 같은 `register_as`를 부른다.
`dataset_origin`은 요청으로 받지 않고 서버가 정한다 — 사용자가 보낸 값을 믿으면 아무나 관리자 등록이 된다.
추이(`/trend`)와 신뢰 패키지(`/package`)는 사용자 상세에서도 쓰므로 공개 범위로만 거른다.

## 오래 걸리는 일은 별도 프로세스로

수집·파이프라인·평가는 몇 분까지 걸리고 DB를 오래 붙잡는다. API 프로세스 안에서
돌리면 커넥션을 공유하는 다른 요청과 트랜잭션이 섞인다(NEXT_STEPS §6.2, 2026-11-04
실측). 그래서 **자식 프로세스**로 띄우고 결과는 DB(`data_registry`·`dcat_provenance`)와
로그로 본다.

## 비밀값

- 사용자가 넣은 API Key는 `dataset_credentials`에 **pgcrypto로 암호화**해 저장한다.
  `ENCRYPTION_KEY`가 서버에 없으면 **거절한다** — 평문 저장도, 조용히 버리기도 하지 않는다
- 키를 비우면 서버 공유 키로 수집한다(src/database/dcat.py `get_api_key` 폴백)
- 오류 메시지는 `config.mask_secrets`를 거친다
"""

import csv
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.access import ensure_visible
from src.api.auth import User, optional_user, require_admin
from src.common import config
from src.common.category_taxonomy import MAX_PER_DATASET, is_valid
from src.database.db import get_conn
from src.api.db_scope import ReleaseDbRoute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/console", tags=["포털 관리"], route_class=ReleaseDbRoute)

REPO = Path(__file__).resolve().parents[2]

#: 발견형·선언형 — scripts/register_dataset.py와 같은 구분
DISCOVERY = {"video", "news", "blog"}
DECLARATIVE = {"shopping_insight", "persona_insight"}

#: 공개 범위 허용값
VISIBILITY = {"PUBLIC", "ORG", "PRIVATE"}

#: 수집 주기. 백엔드가 실제로 지원하는 형식은 `P{n}D`뿐이다(dcat.py).
_PERIOD = re.compile(r"^P([1-9]\d{0,2})D$")

#: 원천별 자격증명 종류 — dcat.py `_PLATFORM_KEY_ENV`와 같은 이름
CREDENTIALS = {
    "video": ("youtube_api_key",),
    "news": ("naver_client_id", "naver_client_secret"),
    "blog": ("naver_client_id", "naver_client_secret"),
    "shopping_insight": ("naver_client_id", "naver_client_secret"),
    "persona_insight": ("naver_client_id", "naver_client_secret"),
}


def _registrar():
    """등록 로직은 CLI 스크립트의 것을 그대로 쓴다."""
    from scripts import register_dataset as R
    return R


def _rows(cur) -> List[Dict[str, Any]]:
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _clean_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = re.split(r"[,\n]", v)
    return [s.strip() for s in v if isinstance(s, str) and s.strip()]


# ── YouTube 대상 해석 ──────────────────────────────────────────────────────
# 사용자는 채널 ID를 모른다. URL·@핸들을 받아 서버가 ID로 바꾼다.
# 핸들은 바뀔 수 있으므로 **저장은 채널 ID로** 한다(등록 시나리오 §2.2).

_CHANNEL_ID = re.compile(r"^UC[\w-]{22}$")
_VIDEO_ID = re.compile(r"^[\w-]{11}$")


def _youtube_key(user_key: Optional[str]) -> Optional[str]:
    if user_key:
        return user_key
    keys = config.get_youtube_api_keys()
    return keys[0] if keys else None


def _resolve_handle(handle: str, key: str) -> Optional[Dict[str, str]]:
    r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "id,snippet", "forHandle": handle, "key": key}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(502, config.mask_secrets(f"YouTube 핸들을 조회하지 못했습니다(HTTP {r.status_code}): {r.text[:200]}"))
    items = r.json().get("items") or []
    if not items:
        return None
    return {"channel_id": items[0]["id"], "title": items[0]["snippet"]["title"]}


def parse_youtube_target(raw: str) -> Dict[str, str]:
    """입력 한 줄 → {kind: channel|video|handle|invalid, value}. 네트워크를 쓰지 않는다."""
    s = raw.strip()
    m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", s)
    if m or _CHANNEL_ID.match(s):
        return {"kind": "channel", "value": m.group(1) if m else s}
    m = re.search(r"youtube\.com/shorts/([\w-]{11})", s)
    if m:
        return {"kind": "invalid", "value": s, "reason": "Shorts 영상은 수집하지 않습니다"}
    m = re.search(r"(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/)([\w-]{11})", s)
    if m:
        return {"kind": "video", "value": m.group(1)}
    m = re.search(r"youtube\.com/(@[\w.\-가-힣]+)", s) or re.match(r"^(@[\w.\-가-힣]+)$", s)
    if m:
        return {"kind": "handle", "value": m.group(1)}
    if _VIDEO_ID.match(s):
        return {"kind": "video", "value": s}
    return {"kind": "invalid", "value": s,
            "reason": "채널 URL(/channel/UC… 또는 /@핸들), 영상 URL, 영상 ID 중 하나를 입력해 주세요"}


def resolve_youtube_targets(targets: List[str], user_key: Optional[str]) -> Dict[str, Any]:
    channels, videos, resolved, problems = [], [], [], []
    key = None
    for t in targets:
        p = parse_youtube_target(t)
        if p["kind"] == "channel":
            channels.append(p["value"]); resolved.append({"input": t, **p})
        elif p["kind"] == "video":
            videos.append(p["value"]); resolved.append({"input": t, **p})
        elif p["kind"] == "handle":
            key = key or _youtube_key(user_key)
            if not key:
                problems.append({"input": t, "reason": "서버에 YouTube API Key가 없어 핸들을 채널 ID로 변환할 수 없습니다"})
                continue
            hit = _resolve_handle(p["value"], key)
            if not hit:
                problems.append({"input": t, "reason": "해당 핸들의 채널을 찾을 수 없습니다"})
                continue
            channels.append(hit["channel_id"])
            resolved.append({"input": t, "kind": "channel", "value": hit["channel_id"], "title": hit["title"]})
        else:
            problems.append({"input": t, "reason": p.get("reason")})
    return {"channels": list(dict.fromkeys(channels)), "videos": list(dict.fromkeys(videos)),
            "resolved": resolved, "problems": problems}


# ── 등록 전 확인 (화면의 '검증' 버튼) ──────────────────────────────────────

def _subjects_for(body: Dict[str, Any], resolved: Optional[Dict[str, Any]]) -> Any:
    st = body["source_type"]
    if st == "video":
        return {"channels": resolved["channels"], "videos": resolved["videos"]}
    if st in DECLARATIVE:
        return [c.split(":")[0] for c in _clean_list(body.get("categories"))]
    return _clean_list(body.get("queries"))


def _duplicates(source_type: str, subjects: Any) -> List[Dict[str, Any]]:
    """같은 수집 조건으로 이미 등록된 데이터셋. external_ids가 겹치면 중복 후보다."""
    R = _registrar()
    ids = json.loads(R.make_external_ids(source_type, subjects))
    if not ids:
        return []
    cur = get_conn().cursor()
    cur.execute("SELECT dataset_id, title FROM dcat_dataset "
                "WHERE source_type = %s AND external_ids ?| %s", (source_type, ids))
    return _rows(cur)


@router.post("/datasets/check", dependencies=[Depends(require_admin)])
def check_registration(body: Dict[str, Any] = Body(...)):
    """등록 전 확인 — 입력 해석·중복 경고. **아무것도 쓰지 않는다.**

    목업의 '검증'은 0.7초 기다렸다가 무조건 통과시켰다. 여기서는 실제로 URL을 풀고
    핸들을 채널 ID로 바꾸고(YouTube API 1단위), 같은 조건의 기존 데이터셋을 찾는다.
    """
    st = body.get("source_type")
    if st not in DISCOVERY | DECLARATIVE:
        raise HTTPException(400, f"수집 유형은 {sorted(DISCOVERY | DECLARATIVE)} 중 하나여야 합니다")
    out: Dict[str, Any] = {"source_type": st, "problems": []}
    resolved = None
    if st == "video":
        resolved = resolve_youtube_targets(_clean_list(body.get("targets")),
                                           (body.get("credentials") or {}).get("youtube_api_key"))
        out.update(resolved)
        if not resolved["channels"] and not resolved["videos"]:
            out["problems"].append({"input": "", "reason": "수집 대상을 하나도 확인하지 못했습니다. 입력값을 확인해 주세요"})
    subjects = _subjects_for(body, resolved)
    if st != "video" and not subjects:
        out["problems"].append({"input": "", "reason": "검색어(또는 카테고리)를 1개 이상 입력해 주세요"})
    out["subjects"] = subjects
    out["duplicates"] = _duplicates(st, subjects) if subjects else []
    out["ok"] = not out["problems"]
    return out


# ── 등록 ──────────────────────────────────────────────────────────────────

def _store_credentials(dataset_id: str, creds: Dict[str, str]) -> List[str]:
    creds = {k: v.strip() for k, v in (creds or {}).items() if isinstance(v, str) and v.strip()}
    if not creds:
        return []
    enc = config.get_env("ENCRYPTION_KEY")
    if not enc:
        raise HTTPException(
            400, "서버 암호화 설정이 없어 API Key를 안전하게 저장할 수 없습니다. "
                 "키 입력란을 비우면 서버 공용 키로 수집합니다")
    conn = get_conn()
    cur = conn.cursor()
    for ctype, value in creds.items():
        cur.execute("""INSERT INTO dataset_credentials (dataset_id, credential_type, encrypted_value)
                       VALUES (%s, %s, pgp_sym_encrypt(%s, %s))
                       ON CONFLICT (dataset_id, credential_type)
                       DO UPDATE SET encrypted_value = EXCLUDED.encrypted_value, updated_at = now()""",
                    (dataset_id, ctype, value, enc))
    conn.commit()
    return sorted(creds)


@router.post("/datasets", dependencies=[Depends(require_admin)])
def register(body: Dict[str, Any] = Body(...)):
    """데이터셋 등록(관리자). 등록만 하고 **수집은 하지 않는다** — `status='pending'`.

    수집은 `POST /datasets/{id}/run`이나 스케줄러가 한다. 등록 직후 화면은
    '등록 완료'와 '수집 완료'를 구분해 보여줘야 한다(등록 시나리오 §6).
    """
    return register_as(body, origin="admin", owner_id=None)


def parse_category(raw: Any) -> List[str]:
    """분류 입력 검증 — 분류표에 있는 서로 다른 값 1~3개(첫 값이 대표)."""
    cats = _clean_list(raw)
    bad = [c for c in cats if not is_valid(c)]
    if bad:
        raise HTTPException(400, f"분류표에 없는 값입니다: {bad}")
    if not 1 <= len(cats) <= MAX_PER_DATASET or len(set(cats)) != len(cats):
        raise HTTPException(400, f"분류는 서로 다른 값으로 1~{MAX_PER_DATASET}개를 선택해 주세요 (첫 번째 값이 대표 분류)")
    return cats


def register_as(body: Dict[str, Any], origin: str, owner_id: Optional[str]) -> Dict[str, Any]:
    """관리자 등록과 사용자 등록이 **같은 길**을 탄다. 다른 것은 origin·owner_id뿐이다.

    `body.category`(선택): 등록 화면에서 추천을 보고 고른 분류. 고르지 않으면 비워 둔다(ADR-020).
    `body.shown_suggestions`(선택): 그때 화면에 보여 준 추천 목록 — 확정 이력에 함께 남긴다.
    """
    assert origin in ("admin", "user")
    st = body.get("source_type")
    if st not in DISCOVERY | DECLARATIVE:
        raise HTTPException(400, f"수집 유형은 {sorted(DISCOVERY | DECLARATIVE)} 중 하나여야 합니다")
    title, desc = (body.get("title") or "").strip(), (body.get("description") or "").strip()
    if not title or not desc:
        # 설명은 관계 산출(SEMANTICALLY_RELATED)의 판정 근거다 — 비우면 안 된다
        raise HTTPException(400, "제목과 설명은 필수 입력 항목입니다")
    period = body.get("periodicity") or "P1D"
    if not _PERIOD.match(period):
        raise HTTPException(400, "수집 주기는 P{n}D 형식이어야 합니다 (예: P1D 매일, P7D 매주)")
    visibility = body.get("visibility") or "ORG"
    if visibility not in VISIBILITY:
        raise HTTPException(400, f"공개 범위는 {sorted(VISIBILITY)} 중 하나여야 합니다")
    creds = body.get("credentials") or {}
    unknown = set(creds) - set(CREDENTIALS[st])
    if unknown:
        raise HTTPException(400, f"{st} 수집에 사용하지 않는 인증 정보입니다: {sorted(unknown)}")
    chosen = parse_category(body["category"]) if _clean_list(body.get("category")) else []
    if any(isinstance(v, str) and v.strip() for v in creds.values()) and not config.get_env("ENCRYPTION_KEY"):
        # 등록부터 하고 키 저장에서 실패하면 키 없는 데이터셋이 남는다. 먼저 막는다
        raise HTTPException(400, "서버 암호화 설정이 없어 API Key를 안전하게 저장할 수 없습니다. "
                                 "키 입력란을 비우면 서버 공용 키로 수집합니다")

    pre = check_registration(body)
    if not pre["ok"]:
        raise HTTPException(400, "입력값을 확인해 주세요: " + "; ".join(
            f"{p['input']} — {p['reason']}" if p["input"] else p["reason"] for p in pre["problems"]))
    if pre["duplicates"] and not body.get("allow_duplicate"):
        if origin == "user":
            # 사용자에게 남의 데이터셋 제목을 알려 주지 않는다(PRIVATE일 수 있다) — my.check가 가린 목록을 본다
            raise HTTPException(409, f"같은 수집 조건의 데이터셋이 이미 {len(pre['duplicates'])}개 있습니다")
        raise HTTPException(409, "같은 수집 조건의 데이터셋이 이미 있습니다: " +
                            ", ".join(d["title"] for d in pre["duplicates"]))

    R = _registrar()
    kws = _clean_list(body.get("keywords"))
    args = Namespace(source_type=st, title=title, description=desc, origin=origin, owner_id=owner_id,
                     keywords=",".join(kws) if kws else None, periodicity=period, dataset_id=None,
                     subjects=None, videos=None, categories=None,
                     temporal_start=body.get("temporal_start") or None)
    if st == "video":
        args.subjects = ",".join(pre["channels"]) or None
        args.videos = ",".join(pre["videos"]) or None
    elif st in DISCOVERY:
        args.subjects = ",".join(pre["subjects"])
    else:
        cats = _clean_list(body.get("categories"))
        if any(":" not in c for c in cats):
            raise HTTPException(400, "카테고리는 'ID:이름' 형식이어야 합니다 (예: 50000148:패션의류)")
        args.categories = ",".join(cats)
    try:
        dataset_id = R.register_discovery(args) if st in DISCOVERY else R.register_declarative(args)
    except SystemExit as e:
        # 등록 스크립트는 입력 오류를 SystemExit로 알린다(CLI용). 사람이 읽을 사유가 담겨 있다
        raise HTTPException(400, str(e).strip())

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE dcat_dataset SET visibility=%s WHERE dataset_id=%s", (visibility, dataset_id))
    if chosen:
        from src.database.category import record_decision
        cur.execute("UPDATE dcat_dataset SET category=%s::jsonb WHERE dataset_id=%s",
                    (json.dumps(chosen, ensure_ascii=False), dataset_id))
        shown = body.get("shown_suggestions")
        record_decision(cur, dataset_id, previous=[], chosen=chosen,
                        shown=shown if isinstance(shown, list) else [],
                        actor=owner_id or "admin", role=origin)
    conn.commit()
    stored = _store_credentials(dataset_id, creds)
    return {"dataset_id": dataset_id, "status": "pending", "credentials_stored": stored,
            "category": chosen, "visibility": visibility,
            "note": "등록했습니다. 수집은 '지금 수집'을 누르거나 정해진 주기에 자동으로 진행됩니다"}


# ── 수정 ──────────────────────────────────────────────────────────────────

@router.patch("/datasets/{dataset_id:path}", dependencies=[Depends(require_admin)])
def update(dataset_id: str, body: Dict[str, Any] = Body(...), admin: User = Depends(require_admin)):
    """등록 후 바꿀 수 있는 것만 받는다. 수집 대상(subjects)은 바꾸지 않는다 —
    바꾸면 이미 쌓인 아이템과 조건이 어긋난다. 그건 새 데이터셋이다."""
    sets, params = [], []
    for col in ("title", "description"):
        if col in body:
            v = (body[col] or "").strip()
            if not v:
                raise HTTPException(400, f"{col} 항목은 비울 수 없습니다")
            sets.append(f"{col}=%s"); params.append(v)
    if "keywords" in body:
        kws = _clean_list(body["keywords"])
        if not kws:
            raise HTTPException(400, "키워드를 1개 이상 입력해 주세요. 키워드가 없으면 키워드 검색과 관계 분석에서 제외됩니다")
        sets.append("keywords=%s::jsonb"); params.append(json.dumps(kws, ensure_ascii=False))
    if "accrual_periodicity" in body:
        if not _PERIOD.match(body["accrual_periodicity"] or ""):
            raise HTTPException(400, "수집 주기는 P{n}D 형식이어야 합니다")
        sets.append("accrual_periodicity=%s"); params.append(body["accrual_periodicity"])
    if "visibility" in body:
        if body["visibility"] not in VISIBILITY:
            raise HTTPException(400, f"공개 범위는 {sorted(VISIBILITY)} 중 하나여야 합니다")
        sets.append("visibility=%s"); params.append(body["visibility"])
    cats = None
    if "category" in body:
        cats = parse_category(body["category"])
        sets.append("category=%s::jsonb"); params.append(json.dumps(cats, ensure_ascii=False))
    if not sets:
        raise HTTPException(400, "변경할 항목이 없습니다")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT category FROM dcat_dataset WHERE dataset_id=%s", (dataset_id,))
    prev = cur.fetchone()
    if prev is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    cur.execute(f"UPDATE dcat_dataset SET {', '.join(sets)}, updated_at=now() "
                f"WHERE dataset_id=%s RETURNING dataset_id", (*params, dataset_id))
    if cur.fetchone() is None:
        conn.rollback()
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    if cats is not None:
        # 관리자 상세의 '분류 확정' — 그때 저장돼 있던 최신 추천을 보여 준 것으로 기록한다
        from src.database.category import record_decision
        record_decision(cur, dataset_id, previous=prev[0] or [], chosen=cats, shown=None,
                        actor=admin.id, role="admin")
    conn.commit()
    return {"dataset_id": dataset_id, "updated": [s.split("=")[0] for s in sets]}


# ── 삭제 ──────────────────────────────────────────────────────────────────

@router.delete("/datasets/{dataset_id:path}", dependencies=[Depends(require_admin)])
def delete(dataset_id: str, confirm: str = Query(..., description="실수 방지 — dataset_id를 한 번 더")):
    """데이터셋 삭제 — **되돌릴 수 없다.** 아이템·벡터·관계·특징·자격증명이 연쇄 삭제된다.

    `confirm`에 같은 dataset_id를 다시 받는다. 화면에서 이름을 다시 쳐야 지울 수 있게 한다.
    수집 이력(dcat_provenance)은 감사 기록이라 남긴다.
    오브젝트 스토리지 원본은 지운다 — 남기면 고아 객체가 된다(2026-10-29에 2,157개를 정리했다).
    """
    if confirm != dataset_id:
        raise HTTPException(400, "확인용으로 입력한 값이 데이터셋 ID와 다릅니다")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT s3_raw_prefix, s3_jsonld_prefix FROM data_registry WHERE dataset_id=%s", (dataset_id,))
    prefixes = [p for p in (cur.fetchone() or ()) if p]
    try:
        cur.execute("DELETE FROM dcat_dataset WHERE dataset_id=%s RETURNING dataset_id", (dataset_id,))
        if cur.fetchone() is None:
            conn.rollback()
            raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:                        # noqa: BLE001
        conn.rollback()
        logger.warning("데이터셋 삭제 실패 (%s): %s: %s", dataset_id, type(e).__name__,
                       config.mask_secrets(str(e))[:300])
        raise HTTPException(409, "삭제하지 못했습니다. 다른 데이터가 이 데이터셋을 참조하고 있을 수 있습니다")
    removed = {}
    from src.storage import s3_client
    for p in prefixes:
        try:
            removed[p] = s3_client.delete_prefix(p, dataset_id)
        except Exception as e:                    # noqa: BLE001
            removed[p] = f"삭제 실패: {config.mask_secrets(str(e))[:200]}"
    return {"dataset_id": dataset_id, "deleted": True, "storage": removed}


# ── 지금 수집 (자식 프로세스) ──────────────────────────────────────────────

_RUNS: Dict[str, Dict[str, Any]] = {}
_RUNS_LOCK = threading.Lock()
_LOG_DIR = Path(tempfile.gettempdir()) / "thirdeye-runs"


def _spawn(key: str, cmd: List[str]) -> Dict[str, Any]:
    with _RUNS_LOCK:
        cur = _RUNS.get(key)
        if cur and cur["proc"].poll() is None:
            raise HTTPException(409, "이미 실행 중입니다")
        _LOG_DIR.mkdir(exist_ok=True)
        log = _LOG_DIR / (re.sub(r"[^\w.-]", "_", key) + ".log")
        fh = open(log, "w", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(REPO), "TRIGGERED_BY": "portal"}
        proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=fh, stderr=subprocess.STDOUT, env=env)
        _RUNS[key] = {"proc": proc, "log": log, "started_at": datetime.now(timezone.utc).isoformat(), "cmd": cmd[2:]}
        return {"started": True, "pid": proc.pid}


def _run_state(key: str) -> Dict[str, Any]:
    r = _RUNS.get(key)
    if not r:
        return {"running": False, "known": False}
    code = r["proc"].poll()
    tail = ""
    try:
        tail = config.mask_secrets(r["log"].read_text(encoding="utf-8", errors="replace")[-4000:])
    except OSError:
        pass
    return {"known": True, "running": code is None, "returncode": code,
            "started_at": r["started_at"], "log_tail": tail}


@router.post("/datasets/{dataset_id:path}/run", dependencies=[Depends(require_admin)])
def run_now(dataset_id: str):
    """지금 수집. `python -m src.main run`을 자식 프로세스로 띄운다 — 스케줄러와 같은 경로다."""
    cur = get_conn().cursor()
    cur.execute("SELECT 1 FROM data_registry WHERE dataset_id=%s", (dataset_id,))
    if not cur.fetchone():
        raise HTTPException(400, "수집 대상이 아닙니다(외부 포털 연계 데이터셋은 메타데이터만 받아 옵니다)")
    return _spawn(f"run:{dataset_id}", [sys.executable, "-m", "src.main", "run", dataset_id])


@router.get("/datasets/{dataset_id:path}/run", dependencies=[Depends(require_admin)])
def run_status(dataset_id: str):
    return _run_state(f"run:{dataset_id}")


# ── 시계열 추이 ───────────────────────────────────────────────────────────

_TREND = {
    # 발견형: 날짜별 새로 들어온 아이템 + 관측(스냅샷) 수
    "video": ("meta_video", "active_meta_video", "sum(a.view_count)", "조회수 합"),
    "news": ("meta_news", "active_meta_news", "sum(a.comment_count)", "댓글 수 합"),
    "blog": ("meta_blog", "active_meta_blog", "sum(a.reaction_count)", "공감 수 합"),
}
_PERIODIC = {
    "shopping_insight": ("meta_shopping_insight", "active_meta_shopping_insight", "avg(a.normalized_ratio)", "평균 검색 비율"),
    "persona_insight": ("meta_persona_insight", "active_meta_persona_insight", "avg(a.persona_index)", "평균 페르소나 지수"),
}


@router.get("/datasets/{dataset_id:path}/trend")
def trend(dataset_id: str, user: Optional[User] = Depends(optional_user)):
    """수집 추이 — 와이즈넛 화면4 '파일 시점 비교'의 비정형판.

    발견형은 **관측일이 짧다**(2026-11-02 실측 1일). 짧으면 짧은 대로 보여 준다 —
    그게 B2 시계열 공변동이 아직 정의되지 않는 이유이기도 하다.
    """
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    cur.execute("SELECT source_type FROM dcat_dataset WHERE dataset_id=%s", (dataset_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    st = row[0]
    if st in _TREND:
        meta, act, agg, label = _TREND[st]
        cur.execute(f"SELECT collected_at::date AS d, count(*) AS n FROM {meta} "
                    f"WHERE dataset_id=%s GROUP BY 1 ORDER BY 1", (dataset_id,))
        new_items = [{"date": r[0].isoformat(), "value": r[1]} for r in cur.fetchall()]
        cur.execute(f"SELECT a.collected_at::date AS d, count(*) AS n, {agg} AS v "
                    f"FROM {act} a JOIN {meta} m ON m.id=a.meta_id WHERE m.dataset_id=%s "
                    f"GROUP BY 1 ORDER BY 1", (dataset_id,))
        obs = [{"date": r[0].isoformat(), "observations": r[1], "value": float(r[2] or 0)} for r in cur.fetchall()]
        return {"kind": "discovery", "metric": label, "new_items": new_items, "observations": obs}
    if st in _PERIODIC:
        meta, act, agg, label = _PERIODIC[st]
        cur.execute(f"SELECT a.period AS d, {agg} AS v, count(*) AS n FROM {act} a "
                    f"JOIN {meta} m ON m.id=a.meta_id WHERE m.dataset_id=%s GROUP BY 1 ORDER BY 1",
                    (dataset_id,))
        series = [{"date": str(r[0])[:10], "value": float(r[1] or 0), "rows": r[2]} for r in cur.fetchall()]
        return {"kind": "periodic", "metric": label, "series": series}
    return {"kind": "none", "reason": "이 유형은 시계열 데이터를 수집하지 않습니다"}


# ── 신뢰 패키지 (C5) ──────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id:path}/package")
def package(dataset_id: str, background: BackgroundTasks, user: Optional[User] = Depends(optional_user),
            x_usage_session: Optional[str] = Header(None)):
    """아이템 CSV + JSON-LD를 서명된 zip으로 묶어 내려준다(manifest + SHA-256 + HMAC).

    받는 쪽은 `scripts/package_dataset.py verify`로 DB·네트워크 없이 검증한다.
    서명키(PACKAGE_SIGNING_KEY)가 서버에 없으면 만들지 않는다 — 서명 없는 패키지는
    '신뢰 패키지'가 아니다.
    """
    key = config.get_env("PACKAGE_SIGNING_KEY")
    if not key:
        raise HTTPException(503, "서버 서명 설정이 없어 패키지를 만들 수 없습니다. "
                                 "관리자에게 문의해 주세요")
    from scripts import package_dataset as P
    from src.packaging import builder
    from src.storage import jsonld_export
    cur = get_conn().cursor()
    ensure_visible(cur, dataset_id, user)
    cur.execute("SELECT pg_meta_table FROM data_registry WHERE dataset_id=%s", (dataset_id,))
    row = cur.fetchone()
    work = Path(tempfile.mkdtemp(prefix="pkg-"))
    src = work / "src"
    src.mkdir()
    (src / "metadata.jsonld").write_text(
        json.dumps(jsonld_export.build_dataset_jsonld(dataset_id), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    table = row[0] if row else None
    if table and re.match(r"^[a-z][a-z0-9_]*$", table):
        cur.execute(f"SELECT * FROM {table} WHERE dataset_id=%s", (dataset_id,))
        names = [c[0] for c in cur.description]
        with open(src / "items.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(names)
            for r in cur.fetchall():
                w.writerow(["" if v is None else v for v in r])
    source, features = P._context(dataset_id)
    safe = re.sub(r"[^\w.-]", "_", dataset_id)
    out = work / (safe + ".zip")
    builder.build_package(dataset_id, src, out, source=source, features=features, key=key)
    background.add_task(lambda: __import__("shutil").rmtree(work, ignore_errors=True))
    from src.api import usage
    usage.record_server_event("download", dataset_id, user, x_usage_session, detail="package")
    return FileResponse(out, media_type="application/zip", filename=out.name)


# ── 파이프라인 (C3) ───────────────────────────────────────────────────────

@router.get("/pipelines", dependencies=[Depends(require_admin)])
def pipelines():
    from src.pipeline_engine import runner
    out = []
    for name in runner.available():
        s = runner.load(name)
        out.append({"name": name, "dataset_id": s["dataset_id"], "table": s["target"]["table"],
                    "source_spec": s["source_spec"], "steps": s.get("steps", runner.STEP_ORDER),
                    "query": s.get("query"), "limit": s.get("limit")})
    return {"items": out, "state": {i["name"]: _run_state(f"pipeline:{i['name']}") for i in out}}


@router.post("/pipelines/{name}/run", dependencies=[Depends(require_admin)])
def run_pipeline(name: str, dry_run: bool = True, limit: Optional[int] = Query(None, ge=1, le=500)):
    """파이프라인 실행. 기본은 **dry-run**(수집·정규화까지, DB에 쓰지 않음)."""
    from src.pipeline_engine import runner
    if name not in runner.available():
        raise HTTPException(404, f"해당 파이프라인을 찾을 수 없습니다: {name}")
    cmd = [sys.executable, "scripts/run_pipeline.py", name]
    if dry_run:
        cmd.append("--dry-run")
    if limit:
        cmd += ["--limit", str(limit)]
    return _spawn(f"pipeline:{name}", cmd)


@router.get("/pipelines/{name}/run", dependencies=[Depends(require_admin)])
def pipeline_status(name: str):
    return _run_state(f"pipeline:{name}")


# ── 검색 성능 측정 (C1 평가) ───────────────────────────────────────────────

@router.post("/eval/run", dependencies=[Depends(require_admin)])
def run_eval(source: str = Query("video")):
    """평가셋으로 검색 설정들을 측정한다(Recall·MRR·nDCG). 모델을 올리므로 자식 프로세스."""
    return _spawn(f"eval:{source}", [sys.executable, "scripts/eval_search.py", "--source", source, "run"])


@router.get("/eval/run", dependencies=[Depends(require_admin)])
def eval_status(source: str = Query("video")):
    return _run_state(f"eval:{source}")


# ── 외부 포털 연합 (C6) ───────────────────────────────────────────────────

@router.get("/federation", dependencies=[Depends(require_admin)])
def federation():
    cur = get_conn().cursor()
    cur.execute("""SELECT source, count(*) AS datasets, max(updated_at) AS last_update
                   FROM dcat_dataset WHERE dataset_origin='external' GROUP BY 1 ORDER BY 1""")
    return {"portals": _rows(cur), "state": _run_state("federation:ckan")}


@router.post("/federation/ckan/run", dependencies=[Depends(require_admin)])
def run_federation(portal: str = Query("https://open.canada.ca/data"),
                   query: str = Query("*:*"), max_records: int = Query(30, ge=1, le=500)):
    """CKAN 포털에서 메타데이터를 다시 받아 온다. 원본 파일은 복사하지 않는다."""
    code = ("import sys,json;from src.federation import ckan;"
            "rows=ckan.harvest(sys.argv[1],sys.argv[2],int(sys.argv[3]));"
            "print(json.dumps(ckan.store(rows),ensure_ascii=False))")
    return _spawn("federation:ckan", [sys.executable, "-c", code, portal, query, str(max_records)])
