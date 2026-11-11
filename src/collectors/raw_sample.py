"""수집 중 원천 응답 표본을 모은다 — 정기 수집 경로의 드리프트 감지용 (C4, 2026-11-11).

드리프트 감지(`src/pipeline_engine/drift.py`)는 원천 응답 **원본**의 모양을 재야 한다.
정기 수집 파이프라인(`src/pipelines/*`)은 수집기가 원본을 바로 정규화해 넘겨서 원본을
볼 수 없었다. 수집기의 함수 시그니처를 바꾸지 않고, 수집기가 원본을 받는 자리에서
`record()`만 부르게 했다.

- 파이프라인이 `start()`를 부른 동안만 모은다. 안 불렀으면 `record()`는 아무것도 안 한다
  (CLI·테스트·다른 호출부에 영향 없음).
- 표본은 최대 `LIMIT`건 — 저수지 표집(reservoir sampling)으로 수집 전체에서 고르게 뽑는다.
  앞쪽 검색어·채널에만 치우치지 않게 한다.
- 실행 단위는 `contextvars`로 구분한다(스레드·작업마다 따로).
"""

import random
from contextvars import ContextVar
from typing import Any, Iterable, List, Optional

LIMIT = 200


class _Sample:
    def __init__(self, limit: int):
        self.limit, self.seen, self.items = limit, 0, []
        self._rng = random.Random()

    def add(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        self.seen += 1
        if len(self.items) < self.limit:
            self.items.append(raw)
            return
        j = self._rng.randrange(self.seen)
        if j < self.limit:
            self.items[j] = raw


_current: ContextVar[Optional[_Sample]] = ContextVar("raw_sample", default=None)


def start(limit: int = LIMIT) -> None:
    """이번 실행의 표본 모으기를 시작한다(이전 표본은 버린다)."""
    _current.set(_Sample(limit))


def record(raw: Any) -> None:
    s = _current.get()
    if s is not None:
        s.add(raw)


def record_many(raws: Iterable[Any]) -> None:
    s = _current.get()
    if s is not None:
        for r in raws:
            s.add(r)


def stop() -> List[dict]:
    """모으기를 끝내고 표본을 돌려준다. 시작하지 않았으면 빈 목록."""
    s = _current.get()
    _current.set(None)
    return s.items if s is not None else []
