"""컨테이너 CPU 상한에 맞춘 연산 스레드 수.

**왜 필요한가.** torch·CTranslate2(faster-whisper)는 스레드 수를 노드의 코어 수로 잡는다.
K8s의 CPU limit은 코어를 숨기지 않고 **시간 할당(CFS quota)**으로만 막으므로, 2코어 상한
파드에서도 노드 코어 수(운영 서버 8개)만큼 스레드를 띄워 서로 할당 시간을 빼앗는다.

2026-11-11 실측(운영 서버, 수집 이미지, `--cpus=2`, e5-base 임베딩 640청크):

    스레드 8(기본)   17.1청크/초   모델 적재 16.6초
    스레드 2         36.1청크/초   모델 적재  5.3초    ← 2.1배
    스레드 1         19.3청크/초

결과 벡터는 스레드 수와 무관하다(같은 연산을 나눠 돌릴 뿐). 검색 품질에는 영향이 없다.

상한은 cgroup에서 읽는다(v2 `cpu.max`, v1 `cpu.cfs_quota_us`). 상한이 없거나(개발 PC)
읽지 못하면 None — 라이브러리 기본값을 그대로 쓴다.
"""

import math
import os
from pathlib import Path
from typing import Optional

_CGROUP = Path("/sys/fs/cgroup")


def cpu_limit(root: Path = _CGROUP) -> Optional[int]:
    """컨테이너 CPU 상한(올림한 코어 수). 상한이 없거나 모르면 None."""
    try:
        v2 = root / "cpu.max"
        if v2.exists():
            quota, period = v2.read_text().split()[:2]
            if quota == "max":
                return None
            return max(1, math.ceil(int(quota) / int(period)))
        q = root / "cpu" / "cpu.cfs_quota_us"
        p = root / "cpu" / "cpu.cfs_period_us"
        if q.exists() and p.exists():
            quota = int(q.read_text().strip())
            if quota <= 0:
                return None
            return max(1, math.ceil(quota / int(p.read_text().strip())))
    except (OSError, ValueError):
        return None
    return None


def threads(default: int, env: str = "", root: Path = _CGROUP) -> int:
    """쓸 스레드 수. 환경변수(`env`)가 있으면 그 값, 없으면 min(기본값, CPU 상한)."""
    if env:
        raw = os.getenv(env, "").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
    limit = cpu_limit(root)
    return max(1, min(default, limit)) if limit else max(1, default)
