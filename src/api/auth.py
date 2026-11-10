"""시제품 로그인 — **케이웨어 K4 인증이 오면 바꿔 끼우는 임시 구현** (ADR-021).

## 범위

계정·인증(K4 OAuth2)은 연구개발계획서상 **케이웨어 과업**이다. 이 모듈은 우리 시제품에서
"내 데이터만 고친다·비공개가 정말 가려진다·관리자 페이지는 관리자만"을 실제로 확인하려고
최소로 만든 것이다. 회원가입·비밀번호 찾기·기관/권한 관리는 **만들지 않는다.**
우리 성과(연차보고서)로 잡지 않는다.

## 교체 지점

토큰은 `Authorization: Bearer <JWT(HS256)>` — OAuth2 액세스 토큰과 같은 자리·형식이다.
K4가 오면 `_decode`(검증)와 `login`(발급)만 K4 쪽으로 바꾸면 되고, 라우트들이 쓰는
`optional_user`·`current_user`·`require_admin`과 `User`는 그대로 둔다.

## 계정

- 서버 파일 `AUTH_USERS_FILE`(기본 `configs/auth_users.local.yaml`, **git·이미지 제외**)에
  ID·이름·역할·기관·**비밀번호 해시**만 둔다. DB 테이블을 만들지 않는다.
- 비밀번호는 사람이 정하고 `scripts/auth_setup_users.py`가 해시만 파일에 쓴다.
  해시는 PBKDF2-SHA256(표준 라이브러리, 반복 600,000회 — OWASP 2023 권고).
- 서명 키 `AUTH_SIGNING_KEY`(32자 이상)가 없으면 **로그인을 거절한다**(503) —
  약한 기본 키로 조용히 도는 것보다 낫다.

## 지키는 것

- ID가 없을 때와 비밀번호가 틀릴 때 **같은 응답·비슷한 시간**(없는 ID도 해시를 한 번 계산)
- 같은 ID로 10분 안에 5번 틀리면 10분 동안 거절(429) — 프로세스 메모리 기준(재시작하면 풀린다)
- 비밀번호·토큰을 로그에 남기지 않는다
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, Body, Depends, Header, HTTPException

from src.common import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["로그인 (시제품)"])

REPO = Path(__file__).resolve().parents[2]
TOKEN_TTL_SEC = 8 * 3600
PBKDF2_ITER = 600_000
MAX_FAILS, FAIL_WINDOW_SEC = 5, 600
ROLES = {"admin", "user"}


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: str
    org: str
    org_name: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "role": self.role,
                "org": self.org, "org_name": self.org_name}


# ── 비밀번호 해시 ──────────────────────────────────────────────────────────

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, iterations: int = PBKDF2_ITER) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, dk = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(it))
        return hmac.compare_digest(got, _unb64(dk))
    except (ValueError, TypeError):
        return False


#: 없는 ID에도 해시를 한 번 계산해 응답 시간으로 ID 존재 여부가 드러나지 않게 한다.
#: 임포트 때 만들면 API 기동·테스트마다 0.5초가 들어 처음 쓸 때 만든다.
_dummy_hash: Optional[str] = None


def _dummy() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_hex(8))
    return _dummy_hash


# ── 계정 파일 ──────────────────────────────────────────────────────────────

_accounts_cache: Dict[str, Any] = {"mtime": None, "path": None, "data": None}
_accounts_lock = threading.Lock()


def users_file() -> Path:
    p = Path(config.get_env("AUTH_USERS_FILE", "configs/auth_users.local.yaml"))
    return p if p.is_absolute() else REPO / p


def load_accounts() -> Dict[str, Any]:
    """{"orgs": {코드: 이름}, "users": {id: {...}}}. 파일이 바뀌면 다시 읽는다. 없으면 빈 계정."""
    path = users_file()
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return {"orgs": {}, "users": {}}
    with _accounts_lock:
        c = _accounts_cache
        if c["path"] == path and c["mtime"] == mtime:
            return c["data"]
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        orgs = {str(k): str(v) for k, v in (raw.get("orgs") or {}).items()}
        users = {}
        for u in raw.get("users") or []:
            if u.get("role") not in ROLES or not u.get("id"):
                logger.warning("계정 파일에 잘못된 항목을 건너뜀 (id=%s)", u.get("id"))
                continue
            users[str(u["id"])] = {"name": u.get("name") or u["id"], "role": u["role"],
                                   "org": str(u.get("org") or ""), "password_hash": u.get("password_hash")}
        data = {"orgs": orgs, "users": users}
        c.update(path=path, mtime=mtime, data=data)
        return data


def _user(uid: str) -> Optional[User]:
    acc = load_accounts()
    u = acc["users"].get(uid)
    if not u:
        return None
    return User(id=uid, name=u["name"], role=u["role"], org=u["org"],
                org_name=acc["orgs"].get(u["org"], u["org"]))


def org_members(org: str) -> List[str]:
    """같은 기관 계정 ID 목록 — '기관 내부(ORG)' 공개 범위 판정에 쓴다."""
    if not org:
        return []
    return [uid for uid, u in load_accounts()["users"].items() if u["org"] == org]


# ── 토큰 (JWT HS256) ──────────────────────────────────────────────────────

def _key() -> bytes:
    k = config.get_env("AUTH_SIGNING_KEY") or ""
    if len(k) < 32:
        raise HTTPException(503, "로그인 설정이 완료되지 않아 로그인할 수 없습니다. 관리자에게 문의해 주세요")
    return k.encode()


def make_token(user: User, now: Optional[float] = None) -> Dict[str, Any]:
    now = int(now if now is not None else time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {"sub": user.id, "role": user.role, "org": user.org,
              "iat": now, "exp": now + TOKEN_TTL_SEC, "iss": "thirdeye-prototype"}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_key(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return {"token": f"{header}.{payload}.{sig}", "expires_at": claims["exp"]}


def _decode(token: str, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """서명·만료를 확인한 클레임. 틀리면 None. (K4 교체 지점)"""
    try:
        header, payload, sig = token.split(".")
        want = hmac.new(_key(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(want, _unb64(sig)):
            return None
        if json.loads(_unb64(header)).get("alg") != "HS256":
            return None
        claims = json.loads(_unb64(payload))
        if int(claims.get("exp", 0)) < int(now if now is not None else time.time()):
            return None
        return claims
    except HTTPException:
        raise
    except Exception:                              # noqa: BLE001 — 형식이 틀린 토큰은 전부 무효
        return None


# ── 의존성 (라우트가 쓰는 것) ──────────────────────────────────────────────

def optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """로그인했으면 User, 아니면 None. **토큰이 있는데 틀리면 401** — 만료를 비로그인으로
    조용히 바꾸면 화면이 '데이터가 사라졌다'로 보인다."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "로그인 정보가 올바르지 않습니다. 다시 로그인해 주세요")
    claims = _decode(token.strip())
    if not claims:
        raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인해 주세요")
    user = _user(str(claims.get("sub")))
    if user is None:
        # 계정 파일에서 지워진 사용자 — 토큰이 살아 있어도 막는다
        raise HTTPException(401, "더 이상 사용할 수 없는 계정입니다. 다시 로그인해 주세요")
    return user


def current_user(user: Optional[User] = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "관리자만 이용할 수 있습니다")
    return user


# ── 로그인 ────────────────────────────────────────────────────────────────

_fails: Dict[str, List[float]] = {}
_fails_lock = threading.Lock()


def _locked(uid: str, now: float) -> bool:
    with _fails_lock:
        recent = [t for t in _fails.get(uid, []) if now - t < FAIL_WINDOW_SEC]
        _fails[uid] = recent
        return len(recent) >= MAX_FAILS


def _fail(uid: str, now: float) -> None:
    with _fails_lock:
        _fails.setdefault(uid, []).append(now)


@router.post("/login")
def login(body: Dict[str, Any] = Body(...)):
    uid = str(body.get("username") or "").strip()
    pw = str(body.get("password") or "")
    if not uid or not pw:
        raise HTTPException(400, "아이디와 비밀번호를 입력해 주세요")
    _key()                                  # 서명 키가 없으면 비밀번호를 보기 전에 거절
    now = time.time()
    if _locked(uid, now):
        raise HTTPException(429, "로그인에 여러 번 실패해 잠시 로그인이 제한되었습니다. 10분 후 다시 시도해 주세요")
    acc = load_accounts()["users"].get(uid)
    ok = verify_password(pw, acc["password_hash"] if acc and acc.get("password_hash") else _dummy())
    if not (acc and ok):
        _fail(uid, now)
        # 원인은 서버 로그에만 남긴다(응답은 같게) — 비밀번호 자체는 남기지 않는다
        why = ("없는 아이디" if not acc else "비밀번호 미설정" if not acc.get("password_hash")
               else "비밀번호 불일치")
        logger.warning("로그인 실패 (id=%s, 원인=%s)", uid[:64], why)
        raise HTTPException(401, "아이디 또는 비밀번호가 일치하지 않습니다")
    with _fails_lock:
        _fails.pop(uid, None)
    user = _user(uid)
    logger.warning("로그인 성공 (id=%s, role=%s)", user.id, user.role)
    return {**make_token(user), "user": user.public()}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": user.public()}


def _reset_for_tests() -> None:          # pragma: no cover — 테스트 전용
    with _fails_lock:
        _fails.clear()
    _accounts_cache.update(mtime=None, path=None, data=None)


__all__ = ["User", "optional_user", "current_user", "require_admin", "org_members",
           "hash_password", "verify_password", "make_token", "router"]
