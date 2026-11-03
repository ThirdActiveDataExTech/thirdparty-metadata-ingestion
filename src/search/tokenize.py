"""한국어 형태소 토큰화 — 키워드 검색 채널의 입력을 만든다.

**왜 필요한가.** PostgreSQL 기본 전문검색은 한국어 형태소를 모른다. 공백으로
끊은 어절을 그대로 색인하면 조사가 붙은 채로 들어가 문서빈도가 무너진다.
2026-10-30 실측(docs/adr/018_Search_Relevance_Judgment.md):

    `대역폭을`  0.23%  vs  `대역폭`  15.04%   ← **65배**
    `맨몸으로`  0.28%  vs  `맨몸`     2.65%   ← 9.5배

같은 단어가 조사에 따라 다른 토큰이 되므로, 질의 `대역폭`은 본문의
`대역폭을`에 영원히 걸리지 않는다. 형태소로 끊어야 비로소 만난다.

**왜 DB 확장이 아니라 앱단인가.** pg_bigm·PGroonga는 이미지 재빌드 +
`shared_preload_libraries` 변경 + 재기동이 전제다. 앱단에서 끊어 `simple`
설정 tsvector에 넣으면 확장 없이 `ts_rank_cd`와 `tsquery` 연산자를 그대로
쓴다. 선택지 비교는 [ADR-010](../../docs/adr/010_Korean_Fulltext_Search.md).

⚠️ **질의와 문서는 반드시 같은 토크나이저를 거쳐야 한다.** 둘이 어긋나면
오류가 나지 않고 **리콜이 조용히 0이 된다.** 그래서 저장할 때 `TOKENIZER_VER`을
같이 적어두고, 검색 시작 전에 `assert_tokenizer_match()`로 대조한다.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 토크나이저 버전 ────────────────────────────────────────────────
# 분석기·모델·품사 화이트리스트 **셋 중 하나라도** 바뀌면 같은 문장이 다른
# 토큰을 내므로 전부 버전 문자열에 넣는다. 화이트리스트를 빼먹으면 "같은
# kiwipiepy인데 색인만 조용히 어긋난" 상태를 잡을 수 없다.
_POS_VER = "pos1"

# 저장된 토큰이 어떤 설정에서 나왔는지 식별한다. 불일치 시 검색을 중단시킨다.
# 모델을 적재해야 값이 정해지므로 상수가 아니라 version()으로 꺼낸다 —
# 모듈 import 시점에 Kiwi를 올리지 않기 위해서다.
_ver: Optional[str] = None

# ── 남길 품사 ──────────────────────────────────────────────────────
# 내용어만 남기고 조사(J*)·어미(E*)·기호(S* 일부)·접사는 버린다.
# 버리는 것들은 어느 문서에나 있어서 변별력이 없고, 오히려 조사가 붙은
# 어절이 색인에 남는 위의 문제를 다시 만든다.
_KEEP = frozenset({
    "NNG",  # 일반명사 — 검색어의 대부분
    "NNP",  # 고유명사 — 기관·제품·인명
    "VV",   # 동사 어간 — '올랐다' → '오르'
    "VA",   # 형용사 어간
    "XR",   # 어근 — '깨끗'처럼 단독으로 못 서는 의미 단위
    "SL",   # 외국어 — HBM, quantum
    "SH",   # 한자
    "SN",   # 숫자 — '2026년', '5G'
})

# ⚠️ 길이로 거르지 않는다. 1글자 토큰이 변별력 없어 보이지만, 한국어는 복합어가
# 형태소로 쪼개지면서 1글자 조각이 핵심 의미를 지고 가는 경우가 흔하다.
#
#     `대역폭`  → 대역 + **폭**      (폭을 버리면 '주파수 대역' 기사와 구분 불가)
#     `전기차`  → 전기 + **차**      (차를 버리면 전기 일반 기사와 구분 불가)
#     `맨몸으로` → 맨(XPN) + **몸**  (몸을 버리면 토큰이 **하나도 안 남는다**)
#
# 정작 변별력 없는 1글자('것', '수', '때', '등')는 의존명사(NNB)라 품사 단계에서
# 이미 빠진다. 고빈도 토큰의 가중치 조정은 길이가 아니라 문서빈도로 할 일이다.

# 토큰에 남길 문자. Kiwi는 `©`를 외국어(SL), `%`를 기호(SW)로 태깅하므로 품사만으로는
# 기호가 걸러지지 않는다. 그대로 두면 두 가지가 깨진다 —
#   1. 색인에 `©` 같은 죽은 토큰이 쌓인다
#   2. `to_tsquery`는 `&`·`!`·`:`를 연산자로 해석해 질의가 구문 오류를 낸다
# 그래서 **색인 쪽과 질의 쪽 모두 같은 자리에서** 문자를 걸러 둘이 어긋나지 않게 한다.
_ALLOWED = re.compile(r"[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ]")

_kiwi = None


def _init():
    """Kiwi를 지연 로드한다 — 모델 적재가 1초 안팎이라 안 쓰면 올리지 않는다."""
    global _kiwi, _ver
    if _kiwi is not None:
        return _kiwi
    import kiwipiepy
    import kiwipiepy_model
    from kiwipiepy import Kiwi

    _kiwi = Kiwi()
    _ver = (
        f"kiwi-{kiwipiepy.__version__}"
        f"+model-{getattr(kiwipiepy_model, '__version__', 'unknown')}"
        f"+{_POS_VER}"
    )
    logger.info("토크나이저 적재: %s", _ver)
    return _kiwi


def version() -> str:
    """현재 토크나이저 버전 문자열. 모델을 적재한다."""
    _init()
    return _ver


def tokens(text: str) -> List[str]:
    """형태소로 끊어 내용어만 돌려준다. 소문자로 맞춘다.

    `simple` 설정 tsvector는 스테밍도 소문자화도 하지 않으므로(`array_to_tsvector`를
    쓰지 않는 이유와 같은 맥락), 여기서 직접 낮춰야 `HBM`과 `hbm`이 만난다.
    """
    if not text or not text.strip():
        return []
    kiwi = _init()
    out: List[str] = []
    for t in kiwi.tokenize(text):
        if t.tag not in _KEEP:
            continue
        form = _ALLOWED.sub("", t.form.lower())
        if form:
            out.append(form)
    return out


def token_text(text: str) -> str:
    """`to_tsvector('simple', ...)`에 그대로 넣을 수 있는 공백 구분 문자열.

    ⚠️ `array_to_tsvector(tokens)`를 쓰면 **위치 정보가 없어 `ts_rank_cd`를 쓸 수
    없다.** 반드시 이 함수의 출력을 `to_tsvector('simple', ...)`에 넣는다
    (ADR-010 "구현 시 반드시 지킬 것").
    """
    return " ".join(tokens(text))


def to_tsquery(text: str, mode: str = "or") -> Optional[str]:
    """질의 문자열을 `to_tsquery` 입력으로 조립한다.

    사용자 입력을 `to_tsquery`에 직접 넣지 않는다 — `&`, `!`, `:` 같은 연산자
    문자가 그대로 해석돼 구문 오류나 의도치 않은 질의가 된다. 토큰화 결과만
    쓰므로 화이트리스트가 자연히 성립한다(ADR-010).

    mode='or'  — 하나라도 걸리면 후보(리콜 우선, RRF 결합용 기본값)
    mode='and' — 전부 걸려야 후보(정밀도 우선)

    토큰이 하나도 없으면 None. 호출 측은 키워드 채널을 건너뛴다.
    """
    toks = tokens(text)
    if not toks:
        return None
    joiner = " & " if mode == "and" else " | "
    # tokens()가 이미 걸렀으므로 여기서 더 할 일은 없다 — 색인 쪽과 같은 함수를
    # 거쳤다는 것이 질의·문서 토큰이 일치한다는 보장이다
    return joiner.join(toks)


class TokenizerMismatch(RuntimeError):
    """저장된 토큰과 현재 토크나이저가 다를 때. 리콜이 조용히 0이 되는 것을 막는다."""


def assert_tokenizer_match(stored_versions) -> None:
    """DB에 적재된 `tokenizer_ver` 값들이 현재 버전과 같은지 확인한다.

    ADR-010: "질의·문서 분석기가 불일치하면 조용히 리콜이 0이 되므로, 불일치 시
    기동 실패시킨다." 검색 진입점에서 부른다.

    stored_versions가 비어 있으면(= 아직 토큰이 하나도 없으면) 통과시킨다 —
    백필 전이라는 뜻이고, 그건 검색 결과가 0건인 것으로 드러난다.
    """
    current = version()
    bad = sorted({v for v in stored_versions if v and v != current})
    if bad:
        raise TokenizerMismatch(
            f"저장된 토큰이 다른 토크나이저로 만들어졌다: {bad} (현재 {current}). "
            f"scripts/backfill_tokens.py 로 재토큰화해야 검색이 정상 동작한다."
        )
