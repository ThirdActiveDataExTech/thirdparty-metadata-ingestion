"""추출 요약과 키워드 — 아이템 단위 (A2 최소선).

[ADR-013](../../docs/adr/013_No_External_LLM_API.md)이 외부 LLM을 금지했고
원칙은 **"LLM이 없어도 기능이 성립해야 한다"**였다. 그래서 문장을 **생성하지
않고 고른다.** hallucination이 없고, 뽑힌 문장이 원문 어디서 왔는지 추적된다.

## B1과 무엇이 다른가 — 단위

| | B1 (`meta_feature`) | A2 (여기) |
|---|---|---|
| 단위 | 데이터셋 | **영상 1건** |
| IDF 코퍼스 | 데이터셋 25개 | **같은 데이터셋의 영상 수백~수천 건** |
| 요약 용도 | 임베딩 입력 (순서 무관) | **사람이 읽는다 (원문 순서 유지)** |

코퍼스가 25개에서 수백 건으로 늘어 IDF 해상도가 훨씬 세밀해진다. B1에서
`MAX_DF_RATIO=0.5` 같은 보조 장치가 필요했던 이유가 "문서 25개로는 IDF가
덜 눌린다"였는데, 여기서는 그 문제가 작다.

## 요약 문장을 고르는 방법

문장 점수 = **그 문장이 담은 토큰들의 IDF 합 ÷ √(문장 길이)**

길이로 나누는 이유 — 안 나누면 그냥 긴 문장이 이기는데, 긴 문장은 대개 여러
주제가 섞여 대표성이 떨어진다. √을 쓰는 것은 짧은 문장이 과도하게 유리해지는
것을 막기 위해서다(완전히 나누면 한 단어짜리가 이긴다).

고른 뒤 **원문 순서로 되돌린다.** 점수 순으로 이으면 사람이 읽을 수 없다.
"""

import logging
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

#: 요약에 넣을 문장 수
SUMMARY_SENTENCES = 3

#: 영상당 남길 키워드 수
TOP_KEYWORDS = 10

#: 이보다 짧은 입력은 요약하지 않는다. 제목 한 줄에서 "요약"을 만들어 봐야
#: 원문과 같은 말이고, 받는 쪽이 요약이 있다고 믿게 만드는 쪽이 더 나쁘다.
MIN_SOURCE_CHARS = 120

#: 문장 경계. 줄바꿈도 경계로 본다 — 영상 설명란은 마침표 없이 줄로 끊는다
_SPLIT = re.compile(r"(?<=[.!?])\s+|[\n\r]+")

#: 본문이 아니라 채널이 모든 영상에 붙이는 문구. 요약에 들어가면 전부 같은
#: 요약이 된다. chunker._BOILERPLATE와 같은 목적이고 영상 쪽 표현을 담았다.
_BOILERPLATE = re.compile(
    r"구독|좋아요|алерт|알림\s*설정|더보기|문의\s*:|협찬|광고\s*문의"
    r"|저작권|무단\s*전재|재배포|홈페이지|인스타|블로그\s*:|카카오톡"
    r"|▶|☞|▷|■\s*$|facebook|instagram|youtube\.com/|http",
    re.IGNORECASE,
)


def sentences(text: str) -> List[str]:
    """요약 후보 문장. 정형 안내 문구는 뺀다."""
    out = []
    for raw in _SPLIT.split(text or ""):
        s = raw.strip()
        if len(s) >= 10 and not _BOILERPLATE.search(s):
            out.append(s)
    return out


def corpus_idf(docs_tokens: Sequence[Sequence[str]]) -> Dict[str, float]:
    """아이템 묶음에서 토큰별 IDF를 만든다. `ln(N/df)`.

    코퍼스는 **같은 데이터셋의 다른 영상들**이다. 데이터셋 밖까지 넓히면
    "이 영상을 같은 채널의 다른 영상과 구별 짓는 말"이 아니라
    "이 영상을 전체 코퍼스와 구별 짓는 말"이 되어, 채널 공통어가 전부 살아남는다.
    """
    n = len(docs_tokens)
    if n == 0:
        return {}
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    return {t: math.log(n / c) for t, c in df.items()}


def keywords(tokens: Sequence[str], idf: Dict[str, float],
             top_n: int = TOP_KEYWORDS, min_tf: int = 1) -> List[str]:
    """이 아이템을 특징짓는 상위 토큰."""
    tf = Counter(tokens)
    scored = [(t, c * idf.get(t, 0.0)) for t, c in tf.items() if c >= min_tf]
    scored = [(t, s) for t, s in scored if s > 0]
    scored.sort(key=lambda p: (-p[1], p[0]))
    return [t for t, _ in scored[:top_n]]


def summarize(text: str, idf: Dict[str, float], tokenize_fn,
              n: int = SUMMARY_SENTENCES) -> Optional[str]:
    """추출 요약. 입력이 너무 짧으면 None(= 만들지 않는다).

    tokenize_fn: 문자열 → 토큰 목록 (ADR-010의 Kiwi 토크나이저를 주입받는다.
    여기서 직접 import하지 않는 이유는 테스트에서 모델을 올리지 않기 위해서다)
    """
    if not text or len(text) < MIN_SOURCE_CHARS:
        return None
    sents = sentences(text)
    # 같은 문장이 여러 번 나오면 한 번만 쓴다. 영상 설명란은 같은 안내를
    # 반복하는 경우가 흔하고, 그대로 두면 요약이 한 문장의 반복이 된다.
    seen, uniq = set(), []
    for s in sents:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    sents = uniq
    if not sents:
        return None
    if len(sents) <= n:
        return " ".join(sents)

    scored: List[Tuple[int, float]] = []
    for i, s in enumerate(sents):
        toks = tokenize_fn(s)
        if not toks:
            continue
        # 길이로 나눈다 — 안 나누면 긴 문장이 그냥 이긴다
        scored.append((i, sum(idf.get(t, 0.0) for t in toks) / math.sqrt(len(toks))))
    if not scored:
        return None

    scored.sort(key=lambda p: -p[1])
    chosen = sorted(i for i, _ in scored[:n])   # ← 원문 순서로 되돌린다
    return " ".join(sents[i] for i in chosen)
