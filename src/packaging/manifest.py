"""패키지 manifest — 무엇을, 어디서, 어떻게 만들었는지 (C5).

**근거**: 연구개발계획서 3·4차년도 "신뢰성 보장 패키징" / "능동형 패키징"
〔SW 모듈 귀속: 모비젠〕

## 신뢰의 사슬

    manifest.sig  ──HMAC─→  manifest.json  ──SHA-256─→  데이터 파일들

서명이 manifest를 보증하고, manifest가 파일 체크섬을 담는다. 파일 하나만
바뀌어도 체크섬이 어긋나고, manifest를 고치면 서명이 깨진다.

## 반드시 지킬 것

**1. 서명은 manifest 안에 넣지 않는다.** 넣으면 "서명을 포함한 상태"를 서명해야
하는 순환이 생긴다. 별도 파일(`manifest.sig`)로 둔다.

**2. 직렬화를 고정한다.** 같은 내용이라도 키 순서나 공백이 달라지면 바이트가
달라져 서명이 깨진다. `canonical_bytes()` 한 곳에서만 직렬화한다.

**3. 공유키는 manifest에 적지 않는다.** 환경변수에서만 읽는다
(NEXT_STEPS §8.6 "자격증명은 환경변수·K8s Secret만").

**4. 검증은 DB 없이 된다.** 완료 기준이 "타 환경에서 체크섬·서명 검증 통과"다.
manifest만으로 출처를 추적할 수 있어야 하므로, 필요한 정보를 전부 담는다.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common import config

#: manifest 형식 버전. 구조가 바뀌면 올린다 — 검증기가 모르는 형식을 만나면
#: 조용히 통과시키는 대신 분명히 거부할 수 있어야 한다.
MANIFEST_VERSION = "1.0"

MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "manifest.sig"
DATA_DIR = "data"

#: HMAC 공유키를 읽을 환경변수. 값은 절대 manifest에 들어가지 않는다.
SIGNING_KEY_ENV = "PACKAGE_SIGNING_KEY"


class ManifestError(RuntimeError):
    """manifest가 규약을 벗어났다. 조용히 넘기면 검증이 무의미해진다."""


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    """파일의 SHA-256. 큰 파일을 통째로 메모리에 올리지 않는다."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def canonical_bytes(manifest: Dict[str, Any]) -> bytes:
    """서명·해시 대상이 되는 **유일한** 직렬화 형태.

    `sort_keys`로 키 순서를 고정하고 구분자에서 공백을 없앤다. 같은 내용이
    항상 같은 바이트가 되어야 서명이 재현된다.
    """
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def manifest_sha256(manifest: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def sign(manifest: Dict[str, Any], key: Optional[str] = None) -> str:
    """manifest에 HMAC-SHA256 서명을 만든다. 키가 없으면 분명히 실패한다."""
    secret = key or config.get_env(SIGNING_KEY_ENV)
    if not secret:
        raise ManifestError(
            f"서명 키가 없다. 환경변수 {SIGNING_KEY_ENV}를 설정하라. "
            f"(예: openssl rand -base64 32)"
        )
    return hmac.new(secret.encode("utf-8"), canonical_bytes(manifest),
                    hashlib.sha256).hexdigest()


def verify_signature(manifest: Dict[str, Any], signature: str,
                     key: Optional[str] = None) -> bool:
    """서명이 맞는지. **`compare_digest`로 비교한다** — 타이밍 공격 방지."""
    expected = sign(manifest, key)
    return hmac.compare_digest(expected, signature)


def build(dataset_id: str, files: List[Dict[str, Any]],
          source: Optional[Dict[str, Any]] = None,
          features: Optional[Dict[str, Any]] = None,
          version: Optional[str] = None) -> Dict[str, Any]:
    """manifest 본문을 만든다.

    files: [{"path": 패키지 내 경로, "sha256": ..., "bytes": ...}, ...]
    source: 출처(제목·발행처·라이선스·수집 기간 등) — 타 환경 추적용
    features: B1 기술통계(`meta_feature`) 일부 — 있으면 담고 없어도 된다
    """
    if not files:
        raise ManifestError("빈 패키지는 만들지 않는다 — 담을 파일이 없다")
    now = datetime.now(timezone.utc)
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id,
        "version": version or now.strftime("%Y%m%dT%H%M%SZ"),
        "created_at": now.isoformat(),
        # 출처 — manifest만으로 "이게 어디서 온 무엇인지" 알 수 있어야 한다
        "source": source or {},
        # B1 산출물. 패키지를 받은 쪽이 열어보지 않고도 규모·구성을 안다
        "features": features or {},
        "files": sorted(files, key=lambda f: f["path"]),
        "total_bytes": sum(f.get("bytes", 0) for f in files),
        "file_count": len(files),
    }


def validate(manifest: Dict[str, Any]) -> None:
    """형식이 규약을 지키는지. 틀리면 예외."""
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError(
            f"모르는 manifest 형식: {manifest.get('manifest_version')!r} "
            f"(이 검증기는 {MANIFEST_VERSION})")
    for key in ("dataset_id", "version", "created_at", "files"):
        if not manifest.get(key):
            raise ManifestError(f"manifest에 {key}가 없다")
    for f in manifest["files"]:
        if not f.get("path") or not f.get("sha256"):
            raise ManifestError(f"파일 항목에 path/sha256이 없다: {f}")
