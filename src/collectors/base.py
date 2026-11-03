"""수집기 공통 계약 (A1).

**왜 필요한가.** 지금은 원천이 하나 늘 때마다 수집기·파이프라인·DB 헬퍼를
새로 쓴다(`src/collectors/*.py` 5종). 3차년도 과업 "확장 가능한 수집"과
C3(템플릿 파이프라인)·C4(자동 구성)·A3(정형 저장)이 전부 이 공통 계약 위에 선다.

계약은 셋이다.

    fetch(cursor)        원천에서 raw 항목을 읽어온다
    normalize(raw)       meta_* 에 넣을 모양으로 바꾼다
    detect_removed(ids)  더 이상 없는 항목을 가려낸다

---

## ⚠️ `detect_removed`의 기본값이 "판정 불가"인 이유

여기가 이 모듈에서 가장 중요한 부분이다. 2026-07-28에 실제로 당한 사고다.

뉴스 수집에 YouTube와 같은 "검색 결과에 없으면 삭제" 방식을 썼는데,
뉴스 검색은 `sort=date` **슬라이딩 윈도우**라 몇 분 만에도 상위 N건 밖으로
밀려난다. 실측에서 기존 기사 **146건이 "부재"로 나왔는데 91건(62%)이 실제로는
살아 있었다.** 지웠으면 데이터가 조용히 사라졌을 것이다.

그래서 원칙을 세웠다(04_Collection_Pipeline_Operations.md §6.1):

> **검색 결과 부재만으로 삭제 판정 금지 — URL을 직접 재확인한다.**

새 어댑터가 이 교훈을 모르고 같은 사고를 반복하지 않도록, **기본값을
`RemovalPolicy.UNSUPPORTED`로 둔다.** 삭제 감지를 켜려면 스펙에 명시해야 하고,
"결과에 없으면 삭제"(`ABSENT_MEANS_REMOVED`)는 **원천이 전수 목록을 주는 경우에만**
쓴다(YouTube `playlistItems`처럼).
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Iterable, Iterator, List, Optional

logger = logging.getLogger(__name__)


class RemovalPolicy(str, Enum):
    """삭제 감지를 어떻게 할 것인가."""

    UNSUPPORTED = "unsupported"
    """판정하지 않는다(기본). 원천이 전수 목록을 주지 않거나 알 수 없을 때."""

    ABSENT_MEANS_REMOVED = "absent_means_removed"
    """조회 결과에 없으면 삭제로 본다. **원천이 전수 목록을 줄 때만** 안전하다."""

    VERIFY_EACH = "verify_each"
    """부재 항목을 하나씩 직접 확인한다. 404/410이 확정될 때만 삭제로 본다.
    검색형 원천(뉴스·블로그)이 이 방식이어야 한다."""


class CollectorError(RuntimeError):
    """수집기 계약 위반. 설정이 틀렸다는 뜻이라 조용히 넘기지 않는다."""


class BaseCollector(ABC):
    """원천 하나를 읽어오는 수집기.

    구현체는 `fetch`와 `normalize`만 채우면 된다. `detect_removed`는 기본이
    "판정 불가"이고, 켜려면 `removal_policy`를 명시해야 한다.
    """

    #: 원천 식별자. 스펙 파일명과 같게 둔다.
    source: str = ""

    #: 삭제 감지 방식. 기본은 판정하지 않는다 — 위 머리말 참조.
    removal_policy: RemovalPolicy = RemovalPolicy.UNSUPPORTED

    @abstractmethod
    def fetch(self, cursor: Optional[Any] = None) -> Iterator[Dict[str, Any]]:
        """원천에서 raw 항목을 읽는다.

        `cursor`는 증분 수집의 시작점이다(마지막 수집 시각·마지막 id 등).
        None이면 처음부터 읽는다. 제너레이터로 돌려줘 큰 결과를 한 번에
        메모리에 올리지 않는다.
        """

    @abstractmethod
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """raw 항목을 `meta_*` 컬럼 이름에 맞춘 평평한 dict로 바꾼다.

        반환에는 반드시 원천 고유 식별자가 들어 있어야 한다 — 중복 판정의 기준이다.
        """

    def item_id(self, normalized: Dict[str, Any]) -> str:
        """정규화된 항목의 원천 고유 식별자. 기본은 `id` 키."""
        value = normalized.get("id")
        if value is None:
            raise CollectorError(
                f"{self.source}: normalize() 결과에 식별자가 없다. "
                f"item_id()를 재정의하거나 'id' 키를 채워라."
            )
        return str(value)

    def verify_exists(self, item_id: str) -> Optional[bool]:
        """항목이 아직 살아 있는지 직접 확인한다.

        `VERIFY_EACH` 정책이면 반드시 재정의해야 한다.
        반환 True=존재, False=확실히 없음(404/410), None=알 수 없음.
        **None이면 삭제하지 않는다** — 네트워크 오류로 데이터를 지우면 안 된다.
        """
        return None

    def detect_removed(self, known_ids: Iterable[str],
                       seen_ids: Iterable[str]) -> List[str]:
        """더 이상 없는 항목의 id 목록.

        known_ids: DB에 있는 것 / seen_ids: 이번 수집에서 본 것
        """
        policy = self.removal_policy
        if policy == RemovalPolicy.UNSUPPORTED:
            # 모르면 아무것도 지우지 않는다. 조용히 지우는 것보다 남는 쪽이 낫다.
            return []

        missing = [i for i in known_ids if i not in set(seen_ids)]
        if not missing:
            return []

        if policy == RemovalPolicy.ABSENT_MEANS_REMOVED:
            return missing

        # VERIFY_EACH — 하나씩 직접 확인한다. 2026-07-28 뉴스 사고의 교훈:
        # 부재 146건 중 91건(62%)이 실제로는 살아 있었다.
        removed = []
        for item_id in missing:
            alive = self.verify_exists(item_id)
            if alive is False:
                removed.append(item_id)
            elif alive is None:
                logger.debug("%s: %s 생존 확인 불가 — 보존한다", self.source, item_id)
        if len(missing) != len(removed):
            logger.info("%s: 부재 %d건 중 %d건만 삭제 확정 (나머지는 보존)",
                        self.source, len(missing), len(removed))
        return removed
