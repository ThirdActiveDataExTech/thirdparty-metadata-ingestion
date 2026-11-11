"""패키지 오류 검출·복원 — 블록 해시로 손상 위치를 찾고, XOR 패리티로 되살린다.

연구계획서 3차년도 "암호화/오류검출(복원)을 이용한 패키징". SHA-256 체크섬만으로는
"파일이 깨졌다"까지만 알 수 있어 다시 받는 수밖에 없다. 여기서는

1. 파일을 `block_size` 블록으로 나눠 **블록마다 SHA-256**을 manifest에 남긴다 → 어느 블록이 깨졌는지 안다
2. 블록 `group`개마다 **XOR 패리티 블록** 하나를 `recovery/` 아래에 둔다 → 묶음당 1블록까지 복원한다

RAID-5와 같은 원리다. 한 묶음에서 두 블록 이상 깨지거나 파일 길이가 바뀌면 복원할 수 없고,
그 사실을 분명히 알린다(조용히 틀린 값을 만들지 않는다 — 복원 뒤 블록 해시로 다시 확인한다).

용량 부담은 대략 1/group(기본 8 → 12.5%)이다. 블록 하나짜리 작은 파일은 패리티가 원본과 같은
크기라 사실상 사본이 된다(작은 파일이라 부담이 작다).
"""

import hashlib
from typing import Dict, List, Optional, Tuple

BLOCK_SIZE = 256 * 1024
GROUP = 8
RECOVERY_DIR = "recovery"


class RecoveryError(RuntimeError):
    """복원할 수 없다(묶음당 2블록 이상 손상, 길이 변경, 복원 정보 없음 등)."""


def _blocks(data: bytes, block_size: int) -> List[bytes]:
    if not data:
        return []
    return [data[i:i + block_size] for i in range(0, len(data), block_size)]


def _xor(blocks: List[bytes], length: int) -> bytes:
    acc = 0
    for b in blocks:
        acc ^= int.from_bytes(b.ljust(length, b"\0"), "big")
    return acc.to_bytes(length, "big")


def _groups(blocks: List[bytes], group: int) -> List[List[bytes]]:
    return [blocks[i:i + group] for i in range(0, len(blocks), group)]


def build(data: bytes, block_size: int = BLOCK_SIZE, group: int = GROUP) -> Tuple[List[str], bytes]:
    """(블록 해시 목록, 패리티 바이트). 묶음의 패리티 길이 = 그 묶음 첫 블록 길이."""
    blocks = _blocks(data, block_size)
    hashes = [hashlib.sha256(b).hexdigest() for b in blocks]
    parity = b"".join(_xor(g, len(g[0])) for g in _groups(blocks, group))
    return hashes, parity


def damaged_blocks(data: bytes, hashes: List[str], block_size: int) -> List[int]:
    """해시가 맞지 않는 블록 번호. 길이가 달라 블록 수가 다르면 RecoveryError."""
    blocks = _blocks(data, block_size)
    if len(blocks) != len(hashes):
        raise RecoveryError("파일 길이가 바뀌어 블록 위치를 맞출 수 없습니다")
    return [i for i, b in enumerate(blocks) if hashlib.sha256(b).hexdigest() != hashes[i]]


def repair(data: bytes, size: int, hashes: List[str], parity: bytes,
           block_size: int = BLOCK_SIZE, group: int = GROUP) -> bytes:
    """손상된 파일을 복원해 돌려준다. 복원할 수 없으면 RecoveryError."""
    if len(data) != size:
        raise RecoveryError(f"파일 길이가 다릅니다(기대 {size}바이트, 실제 {len(data)}바이트)")
    bad = damaged_blocks(data, hashes, block_size)
    if not bad:
        return data
    blocks = _blocks(data, block_size)
    # 패리티를 묶음별로 자른다 — 묶음 패리티 길이는 그 묶음 첫 블록 길이
    offsets: List[Tuple[int, int]] = []
    pos = 0
    for g in _groups(blocks, group):
        offsets.append((pos, len(g[0])))
        pos += len(g[0])
    if pos != len(parity):
        raise RecoveryError("복원 정보(패리티) 길이가 맞지 않습니다")

    by_group: Dict[int, List[int]] = {}
    for i in bad:
        by_group.setdefault(i // group, []).append(i)
    for gi, idxs in by_group.items():
        if len(idxs) > 1:
            raise RecoveryError(f"한 묶음에서 {len(idxs)}블록이 손상되어 복원할 수 없습니다(묶음당 1블록까지)")
        i = idxs[0]
        start, length = offsets[gi]
        others = [b for j, b in enumerate(blocks[gi * group:(gi + 1) * group], start=gi * group) if j != i]
        fixed = _xor(others + [parity[start:start + length]], length)[:len(blocks[i])]
        if hashlib.sha256(fixed).hexdigest() != hashes[i]:
            raise RecoveryError("복원한 블록의 해시가 맞지 않습니다(패리티도 손상된 것으로 보입니다)")
        blocks[i] = fixed
    return b"".join(blocks)


def entry(path: str, data: bytes, block_size: int = BLOCK_SIZE, group: int = GROUP) -> Tuple[Dict, str, bytes]:
    """manifest `recovery.files[path]` 항목, 패리티 파일 경로, 패리티 바이트."""
    hashes, parity = build(data, block_size, group)
    ppath = f"{RECOVERY_DIR}/{path}.parity"
    return ({"blocks": hashes, "parity": ppath,
             "parity_sha256": hashlib.sha256(parity).hexdigest()}, ppath, parity)


def info(block_size: int = BLOCK_SIZE, group: int = GROUP) -> Dict:
    return {"method": "xor-parity", "block_size": block_size, "group": group, "files": {}}


def try_repair(manifest: Dict, path: str, data: bytes, parity: Optional[bytes]) -> bytes:
    """manifest의 복원 정보로 `path` 파일을 되살린다."""
    rec = manifest.get("recovery") or {}
    meta = (rec.get("files") or {}).get(path)
    if not meta or parity is None:
        raise RecoveryError("이 파일에는 복원 정보가 없습니다")
    if hashlib.sha256(parity).hexdigest() != meta["parity_sha256"]:
        raise RecoveryError("복원 정보(패리티)가 손상되었습니다")
    size = next((f["bytes"] for f in manifest["files"] if f["path"] == path), None)
    if size is None:
        raise RecoveryError("manifest에 파일 크기가 없습니다")
    return repair(data, size, meta["blocks"], parity, rec["block_size"], rec["group"])
