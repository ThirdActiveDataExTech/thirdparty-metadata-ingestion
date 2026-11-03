"""패키지 zip 생성 (C5).

구조:

    <dataset>_<version>.zip
      manifest.json        ← 파일 목록 + SHA-256 + 출처 + 기술통계
      manifest.sig         ← manifest.json의 HMAC-SHA256 (hex)
      data/…               ← 실제 파일들

`manifest.json`을 **먼저 확정한 뒤** 서명한다. 순서가 바뀌면 서명이 다른
내용을 가리킨다.
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.packaging import manifest as M

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
                  key: Optional[str] = None) -> Dict[str, Any]:
    """`source_dir`의 파일들을 서명된 zip 패키지로 묶는다. 반환: manifest."""
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise M.ManifestError(f"원본 디렉터리가 없다: {source_dir}")

    files = collect_files(source_dir)
    man = M.build(dataset_id, files, source=source, features=features, version=version)
    M.validate(man)
    signature = M.sign(man, key)          # ← manifest를 확정한 뒤에 서명한다

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(M.MANIFEST_NAME,
                   json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True))
        z.writestr(M.SIGNATURE_NAME, signature)
        for f in files:
            rel = f["path"][len(M.DATA_DIR) + 1:]
            z.write(source_dir / rel, f["path"])

    logger.info("패키지 생성: %s (%d파일 · %d바이트)",
                out_path, man["file_count"], man["total_bytes"])
    return man
