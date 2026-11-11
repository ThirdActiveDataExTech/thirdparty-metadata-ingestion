"""패키지 검증·복원 (C5) — **DB도 네트워크도 필요 없다.**

완료 기준이 "**타 환경에서** 체크섬·서명 검증 통과"다. 받는 쪽이 우리 DB에
접근할 수 없으므로, zip 하나와 공개키(또는 공유키)만으로 끝나야 한다.

검증은 세 단계이고 **전부 통과해야 한다.**

    1. 형식   manifest가 아는 버전·필수 키를 갖췄는가
    2. 서명   manifest가 손대지지 않았는가 (Ed25519 / HMAC — 있는 것은 전부 맞아야 하고, 하나 이상 확인돼야 한다)
    3. 내용   파일들이 manifest의 체크섬과 맞는가 (SHA-256) — 틀리면 복원 정보로 되살릴 수 있는지도 본다

**2번을 먼저 한다.** manifest를 믿을 수 없으면 거기 적힌 체크섬도 믿을 수 없다.

### 출처 확인과 무결성 확인은 다르다

패키지에 든 공개키로 서명이 맞으면 "manifest가 그 키 주인 이후로 바뀌지 않았다"(무결성)까지다.
**공식 경로에서 받은 공개키**(`pubkey`)로 맞아야 "우리가 만들었다"(출처)가 된다. 결과의
`signer_trusted`가 그 구분이다.
"""

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.packaging import manifest as M
from src.packaging import recovery, signing

#: 패키지 안에 있어도 되는 메타 파일
_META_FILES = {M.MANIFEST_NAME, M.SIGNATURE_NAME, signing.SIGNATURE_NAME, signing.PUBLIC_KEY_NAME}


class VerifyResult:
    def __init__(self):
        self.manifest: Optional[Dict[str, Any]] = None
        self.signature_ok = False
        self.files_ok = False
        self.problems: List[str] = []
        self.signatures: Dict[str, str] = {}     # 방식 → "ok" | "fail" | "unchecked"(키 없음)
        self.signer_trusted = False              # 공식 공개키로 확인했는가
        self.signer_fingerprint: Optional[str] = None
        self.repairable: List[str] = []          # 손상됐지만 복원 정보로 되살릴 수 있는 파일
        self.unrepairable: List[str] = []

    @property
    def ok(self) -> bool:
        return self.signature_ok and self.files_ok and not self.problems

    def __repr__(self):
        return (f"<VerifyResult ok={self.ok} 서명={self.signature_ok} "
                f"파일={self.files_ok} 문제={len(self.problems)}>")


def _check_signatures(r: VerifyResult, z: zipfile.ZipFile, names: set, man: Dict[str, Any],
                      key: Optional[str], pubkey_pem: Optional[bytes]) -> None:
    body = M.canonical_bytes(man)

    if signing.SIGNATURE_NAME in names:
        try:
            if pubkey_pem is not None:
                pub = signing.load_public_key(pubkey_pem)
                r.signer_trusted = True
            elif signing.PUBLIC_KEY_NAME in names:
                pub = signing.load_public_key(z.read(signing.PUBLIC_KEY_NAME))
            else:
                pub = None
                r.problems.append("Ed25519 서명이 있지만 검증할 공개키가 없다")
            if pub is not None:
                r.signer_fingerprint = signing.fingerprint(pub)
                want = (man.get("signer") or {}).get("ed25519_fingerprint")
                good = signing.verify(body, z.read(signing.SIGNATURE_NAME).decode("ascii"), pub)
                if good and want and want != r.signer_fingerprint:
                    good = False
                    r.problems.append("서명 공개키 지문이 manifest에 적힌 것과 다르다")
                r.signatures["ed25519"] = "ok" if good else "fail"
                if not good and pubkey_pem is not None:
                    r.problems.append("Ed25519 서명 불일치 — 주어진 공개키로 만든 패키지가 아니거나 manifest가 변조됐다")
                elif not good:
                    r.problems.append("Ed25519 서명 불일치 — manifest가 변조됐다")
        except (signing.SigningError, UnicodeDecodeError) as e:
            r.signatures["ed25519"] = "fail"
            r.problems.append(str(e))

    if M.SIGNATURE_NAME in names:
        sig = z.read(M.SIGNATURE_NAME).decode("utf-8").strip()
        try:
            good = M.verify_signature(man, sig, key)
            r.signatures["hmac-sha256"] = "ok" if good else "fail"
            if not good:
                r.problems.append("서명 불일치 — manifest가 변조됐거나 키가 다르다")
        except M.ManifestError:
            r.signatures["hmac-sha256"] = "unchecked"     # 공유키가 없는 수신자 — 다른 서명으로 판단한다

    if not r.signatures:
        r.problems.append(f"{M.SIGNATURE_NAME} 또는 {signing.SIGNATURE_NAME}이 패키지에 없다")
    elif not any(v == "ok" for v in r.signatures.values()) and not r.problems:
        r.problems.append(f"확인할 수 있는 서명이 없다 — HMAC 공유키({M.SIGNING_KEY_ENV})가 필요하다")
    r.signature_ok = any(v == "ok" for v in r.signatures.values()) and \
        not any(v == "fail" for v in r.signatures.values())


def verify_package(path: Path, key: Optional[str] = None,
                   pubkey_pem: Optional[bytes] = None) -> VerifyResult:
    """zip 패키지를 검증한다. 어디가 틀렸는지 `problems`에 남긴다.

    key: HMAC 공유키(없으면 환경변수) / pubkey_pem: 공식 경로에서 받은 Ed25519 공개키(PEM)
    """
    r = VerifyResult()
    path = Path(path)
    if not path.is_file():
        r.problems.append(f"파일이 없다: {path}")
        return r

    if not zipfile.is_zipfile(path):
        r.problems.append("zip 형식이 아니다 — 암호화 패키지(*.zip.enc)라면 먼저 decrypt 하라")
        return r

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if M.MANIFEST_NAME not in names:
            r.problems.append(f"{M.MANIFEST_NAME}이 패키지에 없다")
            return r

        man = json.loads(z.read(M.MANIFEST_NAME).decode("utf-8"))
        r.manifest = man

        # 1. 형식
        try:
            M.validate(man)
        except M.ManifestError as e:
            r.problems.append(str(e))
            return r

        # 2. 서명 — manifest를 믿을 수 있는지부터 본다
        _check_signatures(r, z, names, man, key, pubkey_pem)
        if not r.signature_ok:
            return r

        # 3. 내용
        rec_files = (man.get("recovery") or {}).get("files") or {}
        parity_paths = {m["parity"] for m in rec_files.values()}
        listed = {f["path"] for f in man["files"]}
        packed = {n for n in names if n.startswith(M.DATA_DIR + "/")}
        for extra in sorted(names - _META_FILES - listed - parity_paths):
            # manifest에 없는 파일이 끼어 있으면 체크섬 사슬 밖이다
            r.problems.append(f"manifest에 없는 파일: {extra}")
        for missing in sorted(listed - packed):
            r.problems.append(f"패키지에 없는 파일: {missing}")

        for f in man["files"]:
            if f["path"] not in packed:
                continue
            data = z.read(f["path"])
            if hashlib.sha256(data).hexdigest() == f["sha256"]:
                continue
            r.problems.append(f"체크섬 불일치: {f['path']}")
            meta = rec_files.get(f["path"])
            parity = z.read(meta["parity"]) if meta and meta["parity"] in names else None
            try:
                recovery.try_repair(man, f["path"], data, parity)
                r.repairable.append(f["path"])
            except recovery.RecoveryError:
                r.unrepairable.append(f["path"])

        for p, meta in rec_files.items():
            if meta["parity"] not in names:
                r.problems.append(f"복원 정보가 없다: {meta['parity']}")
            elif hashlib.sha256(z.read(meta["parity"])).hexdigest() != meta["parity_sha256"]:
                r.problems.append(f"복원 정보 체크섬 불일치: {meta['parity']}")

        r.files_ok = not r.problems
    return r


def repair_package(path: Path, out_path: Path, key: Optional[str] = None,
                   pubkey_pem: Optional[bytes] = None) -> VerifyResult:
    """손상된 데이터 파일을 복원 정보로 되살려 새 zip을 쓴다. 반환: 새 zip의 검증 결과.

    manifest와 서명은 그대로 옮긴다 — 복원한 파일이 원래 체크섬과 같으므로 서명도 그대로 유효하다.
    서명이 맞지 않는 패키지는 복원하지 않는다(무엇이 원본인지 믿을 근거가 없다).
    """
    before = verify_package(path, key, pubkey_pem)
    if not before.signature_ok:
        raise recovery.RecoveryError("서명을 확인할 수 없는 패키지는 복원하지 않습니다")
    if before.unrepairable:
        raise recovery.RecoveryError("복원할 수 없는 파일이 있습니다: " + ", ".join(before.unrepairable))
    man = before.manifest
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zo:
        for name in zi.namelist():
            data = zi.read(name)
            if name in before.repairable:
                meta = man["recovery"]["files"][name]
                data = recovery.try_repair(man, name, data, zi.read(meta["parity"]))
            zo.writestr(name, data)
    return verify_package(out_path, key, pubkey_pem)
