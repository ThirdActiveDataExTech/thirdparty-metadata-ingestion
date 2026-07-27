"""간단한 재시도+백오프 헬퍼.

레거시(3amd) 스크립트들은 재시도 로직이 전혀 없었다(고정 sleep만). 외부 의존성
(tenacity 등) 추가 없이 순수 Python으로 최소한의 재시도만 구현한다 — 일시적
네트워크 오류/5xx에 한해 재시도, 4xx(쿼터 초과 등 클라이언트 오류)는 재시도해도
소용없으므로 즉시 실패시킨다.
"""

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryableError(Exception):
    """일시적 오류 — 재시도 대상."""


def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> T:
    """fn()을 호출하고, RetryableError 발생 시에만 지수 백오프로 재시도한다.

    RetryableError가 아닌 예외는 즉시 전파한다(재시도 무의미한 오류로 간주).
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except RetryableError as e:
            last_error = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt)
                time.sleep(delay)
    raise last_error
