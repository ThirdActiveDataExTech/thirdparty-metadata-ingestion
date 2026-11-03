"""패키지 검증 (C5) — **DB도 네트워크도 필요 없다.**

완료 기준이 "**타 환경에서** 체크섬·서명 검증 통과"다. 받는 쪽이 우리 DB에
접근할 수 없으므로, zip 하나와 공유키만으로 끝나야 한다.

검증은 세 단계이고 **전부 통과해야 한다.**

    1. 형식   manifest가 아는 버전·필수 키를 갖췄는가
    2. 서명   manifest가 손대지지 않았는가 (HMAC)
    3. 내용   파일들이 manifest의 체크섬과 맞는가 (SHA-256)

**2번을 먼저 한다.** manifest를 믿을 수 없으면 거기 적힌 체크섬도 믿을 수 없다.
"""

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.packaging import manifest as M


class VerifyResult:
    def __init__(self):
        self.manifest: Optional[Dict[str, Any]] = None
        self.signature_ok = False
        self.files_ok = False
        self.problems: List[str] = []

    @property
    def ok(self) -> bool:
        return self.signature_ok and self.files_ok and not self.problems

    def __repr__(self):
        return (f"<VerifyResult ok={self.ok} 서명={self.signature_ok} "
                f"파일={self.files_ok} 문제={len(self.problems)}>")


def verify_package(path: Path, key: Optional[str] = None) -> VerifyResult:
    """zip 패키지를 검증한다. 어디가 틀렸는지 `problems`에 남긴다."""
    r = VerifyResult()
    path = Path(path)
    if not path.is_file():
        r.problems.append(f"파일이 없다: {path}")
        return r

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for required in (M.MANIFEST_NAME, M.SIGNATURE_NAME):
            if required not in names:
                r.problems.append(f"{required}이 패키지에 없다")
        if r.problems:
            return r

        man = json.loads(z.read(M.MANIFEST_NAME).decode("utf-8"))
        signature = z.read(M.SIGNATURE_NAME).decode("utf-8").strip()
        r.manifest = man

        # 1. 형식
        try:
            M.validate(man)
        except M.ManifestError as e:
            r.problems.append(str(e))
            return r

        # 2. 서명 — manifest를 믿을 수 있는지부터 본다
        try:
            r.signature_ok = M.verify_signature(man, signature, key)
        except M.ManifestError as e:
            r.problems.append(str(e))
            return r
        if not r.signature_ok:
            r.problems.append("서명 불일치 — manifest가 변조됐거나 키가 다르다")
            return r

        # 3. 내용
        listed = {f["path"] for f in man["files"]}
        packed = {n for n in names if n.startswith(M.DATA_DIR + "/")}
        for extra in sorted(packed - listed):
            # manifest에 없는 파일이 끼어 있으면 체크섬 사슬 밖이다
            r.problems.append(f"manifest에 없는 파일: {extra}")
        for missing in sorted(listed - packed):
            r.problems.append(f"패키지에 없는 파일: {missing}")

        for f in man["files"]:
            if f["path"] not in packed:
                continue
            got = hashlib.sha256(z.read(f["path"])).hexdigest()
            if got != f["sha256"]:
                r.problems.append(f"체크섬 불일치: {f['path']}")

        r.files_ok = not r.problems
    return r
