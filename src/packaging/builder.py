"""패키지 zip 생성 (C5).

구조:

    <dataset>_<version>.zip
      manifest.json          ← 파일 목록 + SHA-256 + 출처 + 기술통계 + (1.1) 이력·레퍼런스·점검·복원 정보
      manifest.ed25519.sig   ← manifest.json의 Ed25519 서명(base64) — 공개키로 누구나 검증
      signer.pub.pem         ← 서명 공개키(편의용 — 출처 확인은 공식 경로의 키와 대조해야 한다)
      manifest.sig           ← manifest.json의 HMAC-SHA256 (hex) — 공유키가 있을 때만
      data/…                 ← 실제 파일들
      recovery/data/….parity ← 블록 XOR 패리티(손상 블록 복원)

`manifest.json`을 **먼저 확정한 뒤** 서명한다. 순서가 바뀌면 서명이 다른 내용을 가리킨다.
서명은 Ed25519·HMAC 중 **하나 이상** 있어야 한다 — 서명 없는 패키지는 만들지 않는다.
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common import config
from src.packaging import manifest as M
from src.packaging import quality, recovery, signing

logger = logging.getLogger(__name__)


def collect_files(root: Path) -> List[Dict[str, Any]]:
    """디렉터리를 훑어 manifest의 files 항목을 만든다.

    경로는 **패키지 안에서의 상대 경로**다. 절대 경로를 넣으면 만든 사람의
    디렉터리 구조가 패키지에 새어 나가고, 받는 쪽에서 의미도 없다.
    """
    out: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        out.append({
            "path": f"{M.DATA_DIR}/{rel}",
            "sha256": M.sha256_file(path),
            "bytes": path.stat().st_size,
        })
    return out


def build_package(dataset_id: str, source_dir: Path, out_path: Path,
                  source: Optional[Dict[str, Any]] = None,
                  features: Optional[Dict[str, Any]] = None,
                  version: Optional[str] = None,
                  key: Optional[str] = None,
                  ed25519_key: Optional[signing.Ed25519PrivateKey] = None,
                  context: Optional[Dict[str, Any]] = None,
                  with_recovery: bool = True,
                  expected_rows: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """`source_dir`의 파일들을 서명된 zip 패키지로 묶는다. 반환: manifest.

    key: HMAC 공유키(없으면 환경변수 PACKAGE_SIGNING_KEY) / ed25519_key: Ed25519 비밀키(없으면
    환경변수 PACKAGE_SIGNING_ED25519_KEY). 둘 다 없으면 만들지 않는다.
    context: `lineage`·`reference` 절 / expected_rows: {상대경로: 기대 행 수} — 점검에 쓴다
    """
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise M.ManifestError(f"원본 디렉터리가 없다: {source_dir}")

    hmac_key = key or config.get_env(M.SIGNING_KEY_ENV)
    ed_key = ed25519_key or signing.private_key_from_env()
    if not hmac_key and not ed_key:
        raise M.ManifestError(
            f"서명 키가 없다. 환경변수 {signing.PRIVATE_KEY_ENV}(Ed25519, 권장) 또는 "
            f"{M.SIGNING_KEY_ENV}(HMAC)를 설정하라. 키 만들기: package_dataset.py keygen")

    files = collect_files(source_dir)
    extra: Dict[str, Any] = dict(context or {})
    extra["quality"] = quality.profile(source_dir, M.DATA_DIR, expected_rows)

    parity_blobs: Dict[str, bytes] = {}
    if with_recovery:
        rec = recovery.info()
        for f in files:
            data = (source_dir / f["path"][len(M.DATA_DIR) + 1:]).read_bytes()
            if not data:
                continue
            meta, ppath, parity = recovery.entry(f["path"], data)
            rec["files"][f["path"]] = meta
            parity_blobs[ppath] = parity
        extra["recovery"] = rec

    algorithms = (["ed25519"] if ed_key else []) + (["hmac-sha256"] if hmac_key else [])
    extra["signer"] = {"algorithms": algorithms}
    if ed_key:
        extra["signer"]["ed25519_fingerprint"] = signing.fingerprint(ed_key.public_key())

    man = M.build(dataset_id, files, source=source, features=features, version=version, extra=extra)
    M.validate(man)
    body = M.canonical_bytes(man)               # ← manifest를 확정한 뒤에 서명한다

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(M.MANIFEST_NAME,
                   json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True))
        if hmac_key:
            z.writestr(M.SIGNATURE_NAME, M.sign(man, hmac_key))
        if ed_key:
            z.writestr(signing.SIGNATURE_NAME, signing.sign(body, ed_key))
            z.writestr(signing.PUBLIC_KEY_NAME, signing.public_pem(ed_key.public_key()))
        for f in files:
            rel = f["path"][len(M.DATA_DIR) + 1:]
            z.write(source_dir / rel, f["path"])
        for ppath, blob in parity_blobs.items():
            z.writestr(ppath, blob)

    logger.info("패키지 생성: %s (%d파일 · %d바이트 · 서명 %s)",
                out_path, man["file_count"], man["total_bytes"], "+".join(algorithms))
    return man
