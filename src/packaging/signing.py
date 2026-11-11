"""패키지 공개키 서명 (Ed25519) — 받는 쪽이 **비밀 없이** 출처를 확인한다.

**왜 HMAC만으로는 부족한가.** HMAC은 같은 공유키를 가진 사람만 검증할 수 있다. 외부 수신자에게
키를 주면 그 사람도 서명을 만들 수 있으므로 "우리가 만들었다"는 증명이 안 된다(연구계획서
3차년도 "디지털 서명을 이용하여 데이터의 출처를 보장"). Ed25519는 비밀키로 서명하고 공개키로만
검증하므로, 공개키를 누구에게 줘도 위조할 수 없다.

## 신뢰의 근거는 공개키를 **어디서** 받았는가다

패키지 안에도 공개키(`signer.pub.pem`)를 넣지만, 그것만으로는 "패키지 안의 키와 서명이 서로
맞는다"는 것만 증명된다 — 위조자는 키와 서명을 함께 바꿔 넣을 수 있다. 그래서 검증 결과를
두 단계로 나눈다.

- `--pubkey`로 공식 경로(API `/v1/packaging/public-key`, 문서)에서 받은 키를 주면 **출처 확인**
- 주지 않으면 **무결성만 확인**하고, 대조할 지문(fingerprint)을 보여 준다

## 키 관리

비밀키는 PEM(PKCS#8) 문자열로 환경변수 `PACKAGE_SIGNING_ED25519_KEY`에만 둔다(K8s Secret).
만드는 것은 사람이 한다: `python scripts/package_dataset.py keygen --out <디렉터리>`.
"""

import base64
import hashlib
import os
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PRIVATE_KEY_ENV = "PACKAGE_SIGNING_ED25519_KEY"
SIGNATURE_NAME = "manifest.ed25519.sig"
PUBLIC_KEY_NAME = "signer.pub.pem"
ALGORITHM = "ed25519"


class SigningError(RuntimeError):
    """키 형식이 틀렸거나 서명을 만들 수 없다."""


def load_private_key(pem: str) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except (ValueError, TypeError) as e:
        raise SigningError("Ed25519 비밀키 형식이 올바르지 않습니다(PEM PKCS#8이어야 합니다)") from e
    if not isinstance(key, Ed25519PrivateKey):
        raise SigningError("Ed25519 키가 아닙니다")
    return key


def private_key_from_env() -> Optional[Ed25519PrivateKey]:
    """환경변수의 비밀키. 없으면 None. (`\\n`으로 이어 붙인 한 줄 값도 받는다)"""
    raw = os.getenv(PRIVATE_KEY_ENV, "").strip()
    if not raw:
        return None
    return load_private_key(raw.replace("\\n", "\n"))


def load_public_key(pem: bytes) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as e:
        raise SigningError("공개키 형식이 올바르지 않습니다(PEM이어야 합니다)") from e
    if not isinstance(key, Ed25519PublicKey):
        raise SigningError("Ed25519 공개키가 아닙니다")
    return key


def public_pem(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def fingerprint(key: Ed25519PublicKey) -> str:
    """공개키 지문 — 원시 32바이트의 SHA-256 앞 16바이트를 hex로(사람이 대조하기 쉬운 길이)."""
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    h = hashlib.sha256(raw).hexdigest()[:32]
    return ":".join(h[i:i + 4] for i in range(0, 32, 4))


def sign(data: bytes, key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.sign(data)).decode("ascii")


def verify(data: bytes, signature_b64: str, key: Ed25519PublicKey) -> bool:
    try:
        key.verify(base64.b64decode(signature_b64.strip(), validate=True), data)
        return True
    except (InvalidSignature, ValueError):
        return False


def generate() -> Tuple[bytes, bytes]:
    """새 키 쌍(비밀 PEM, 공개 PEM). **사람이 keygen 명령으로만** 부른다."""
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    return private, public_pem(key.public_key())
