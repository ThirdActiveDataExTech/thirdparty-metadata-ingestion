"""패키지 암호화 봉투 — 비밀번호로 zip 전체를 감싼다 (AES-256-GCM, 스트리밍).

연구계획서 3차년도 "암호화/오류검출(복원)을 이용한 패키징". 서명은 위·변조를 잡지만 내용을 숨기지
않는다. 조직 밖으로 옮길 때 내용까지 보호하려면 암호화한다(선택 기능).

## 형식 (`*.zip.enc`)

    헤더  MAGIC(8) | salt(16) | log2(N)(1) | r(1) | p(1) | nonce_prefix(7) | chunk_size(4)
    본문  청크마다 AES-256-GCM(key, nonce = prefix ‖ 순번(4) ‖ 마지막 표시(1), aad = 헤더)

- 키는 비밀번호에서 scrypt로 만든다(N=2^15, r=8, p=1 — 약 32MB·0.1초). 비밀번호는 저장하지 않는다
- 청크마다 인증 태그가 붙어 **변조·순서 바꿈·잘림**을 모두 잡는다(순번·마지막 표시가 nonce에 들어간다)
- 큰 파일도 메모리에 다 올리지 않는다
"""

import os
import struct
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"MPKGENC1"
CHUNK = 1024 * 1024
_TAG = 16
_HEADER = struct.Struct(">8s16sBBB7sI")
PASSPHRASE_ENV = "PACKAGE_PASSPHRASE"


class EnvelopeError(RuntimeError):
    """복호화할 수 없다(비밀번호가 틀렸거나 파일이 손상·변조됨)."""


def _key(passphrase: str, salt: bytes, log_n: int, r: int, p: int) -> bytes:
    if not passphrase:
        raise EnvelopeError("비밀번호가 비어 있습니다")
    return Scrypt(salt=salt, length=32, n=2 ** log_n, r=r, p=p).derive(passphrase.encode("utf-8"))


def _nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    return prefix + struct.pack(">I", counter) + (b"\x01" if last else b"\x00")


def encrypt_stream(src: BinaryIO, dst: BinaryIO, passphrase: str, chunk: int = CHUNK,
                   log_n: int = 15, r: int = 8, p: int = 1) -> None:
    salt, prefix = os.urandom(16), os.urandom(7)
    header = _HEADER.pack(MAGIC, salt, log_n, r, p, prefix, chunk)
    aead = AESGCM(_key(passphrase, salt, log_n, r, p))
    dst.write(header)
    counter = 0
    cur = src.read(chunk)
    while True:
        nxt = src.read(chunk)
        last = not nxt
        dst.write(aead.encrypt(_nonce(prefix, counter, last), cur, header))
        if last:
            return
        cur, counter = nxt, counter + 1


def decrypt_stream(src: BinaryIO, dst: BinaryIO, passphrase: str) -> None:
    header = src.read(_HEADER.size)
    if len(header) != _HEADER.size:
        raise EnvelopeError("암호화 패키지가 아닙니다(헤더가 짧습니다)")
    magic, salt, log_n, r, p, prefix, chunk = _HEADER.unpack(header)
    if magic != MAGIC:
        raise EnvelopeError("암호화 패키지가 아닙니다(형식 표시가 다릅니다)")
    if not (10 <= log_n <= 22) or chunk <= 0 or chunk > 64 * 1024 * 1024:
        raise EnvelopeError("헤더 값이 허용 범위를 벗어났습니다")
    aead = AESGCM(_key(passphrase, salt, log_n, r, p))
    counter = 0
    cur = src.read(chunk + _TAG)
    if not cur:
        raise EnvelopeError("본문이 없습니다")
    while True:
        nxt = src.read(chunk + _TAG)
        last = not nxt
        try:
            dst.write(aead.decrypt(_nonce(prefix, counter, last), cur, header))
        except InvalidTag as e:
            raise EnvelopeError("복호화 실패 — 비밀번호가 틀렸거나 파일이 손상·변조·절단되었습니다") from e
        if last:
            return
        cur, counter = nxt, counter + 1


def encrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        encrypt_stream(fi, fo, passphrase)


def decrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    tmp = Path(str(dst) + ".part")
    try:
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            decrypt_stream(fi, fo, passphrase)
        tmp.replace(dst)        # 인증을 끝까지 통과한 뒤에만 결과 파일을 남긴다
    finally:
        tmp.unlink(missing_ok=True)
