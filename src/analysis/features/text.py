"""텍스트 특징 — 데이터셋을 특징짓는 키워드와 대표 문장을 뽑는다 (B1).

**왜 필요한가.** 2026-11-02 실측(docs/database/metadata_quality_probe.md)에서
데이터셋 레벨 텍스트가 너무 빈약하다는 것이 확인됐다 — 등록 키워드가 평균 2~3개,
`description`이 평균 24~36자다. 그 결과 데이터셋 300쌍 중 **22쌍(7.3%)**만
키워드를 공유해서, 키워드 자카드로는 관계 그래프가 서지 않는다.

신호는 데이터셋 레벨이 아니라 **아이템 레벨에 있다** — 뉴스 1,755건, 블로그
1,772건, 영상 1,554건의 본문·제목·태그. 여기서 끌어올려 데이터셋을 대표하게
만드는 것이 이 모듈의 일이고, B2 관계 분석의 입력이 된다.

**토큰은 다시 만들지 않는다.** `*_vec.token_text`에 이미 Kiwi로 형태소 분해한
결과가 들어 있다(ADR-010). 같은 토크나이저를 거친 토큰을 써야 검색 채널과
특징 추출이 같은 어휘를 본다 — 따로 만들면 `대역폭을`/`대역폭` 같은 불일치가
조용히 생긴다.

**요약은 추출식이다.** ADR-013이 외부 LLM을 금지했고, 핵심 원칙은 "LLM이 없어도
기능이 성립해야 한다"였다. 생성 요약 대신 **상위 키워드가 가장 조밀한 청크**를
고른다 — hallucination이 없고 원문 추적이 된다.
"""

import logging
import math
from collections import Counter
from typing import Dict, List, Sequence, Tuple

logger = logging.getLogger(__name__)

#: 데이터셋당 남길 상위 키워드 수. 너무 적으면 B2 관계가 안 서고,
#: 너무 많으면 고빈도 일반어가 섞여 들어와 모든 데이터셋이 비슷해진다.
TOP_K = 30

#: 대표 문장으로 고를 청크 수. summary_embedding의 입력이 된다.
SUMMARY_CHUNKS = 5

#: 이 비율을 넘는 데이터셋에 나타나는 토큰은 버린다.
#:
#: IDF만으로는 부족하다. 문서가 25개뿐이라 해상도가 낮은 데다(df 1→idf 2.56,
#: df 25→idf 0.04), **텍스트가 빈약한 데이터셋이 IDF를 희석시킨다** —
#: 2026-11-02 기준 어휘 1,000토큰 이상을 가진 데이터셋은 25개 중 **14개**뿐이고
#: (shopping/persona 10개는 아이템이 "카테고리"라 본문이 없다), 그래서 모든
#: 본문에 나오는 `있`·`하`·`되`조차 df가 15/25=60%에 그친다.
#:
#: 값은 실측으로 골랐다. 같은 코퍼스에 0.8/0.6/0.5/0.4를 쓸어본 결과:
#:
#:   0.8, 0.6 → `있 하 사용 웨이스트 쓰레기 되 제품 환경`   기능어가 상위에 남음
#:   **0.5**  → `웨이스트 쓰레기 플라스틱 제로웨이스트 실천`  주제어만 남음
#:   0.4      → `웨이스트 쓰레기 플라스틱 제로 비누 코엔자임`  주제어를 잃기 시작
#:              (전기차 블로그에서 `전기`·`충전`·`배터리`가 빠지고 `suv`·`kwh`만 남음)
#:
#: 0.5는 "텍스트를 가진 데이터셋 대부분에 나오는 말"의 경계다(14/25 ≈ 0.56).
#: ⚠️ 데이터셋 구성이 바뀌면(정형 적재, 빈약한 데이터셋 비중 변화) 다시 재야 한다.
#: 별도 불용어 사전은 두지 않는다 — 0.5에서는 df가 전부 잡아내서 필요가 없었다.
MAX_DF_RATIO = 0.5

#: 이 횟수 미만으로 나온 토큰은 버린다. 오탈자·고유명사 파편이 상위에 오는 것을 막는다.
MIN_TF = 3


def tf_by_dataset(rows: Sequence[Tuple[str, str]]) -> Dict[str, Counter]:
    """(dataset_id, token_text) 행들을 데이터셋별 토큰 빈도로 접는다."""
    tf: Dict[str, Counter] = {}
    for dataset_id, token_text in rows:
        if not token_text:
            continue
        tf.setdefault(dataset_id, Counter()).update(token_text.split())
    return tf


def tfidf(tf: Dict[str, Counter], top_k: int = TOP_K,
          max_df_ratio: float = MAX_DF_RATIO,
          min_tf: int = MIN_TF) -> Dict[str, List[dict]]:
    """데이터셋별 상위 키워드를 TF-IDF로 고른다.

    문서 = 데이터셋 하나. "이 데이터셋을 **다른 데이터셋과 구별 짓는** 말"을
    찾는 것이므로 코퍼스는 데이터셋 집합이 맞다.

    ⚠️ **IDF 해상도가 낮다.** 문서가 25개뿐이라 df가 1이면 idf≈2.56,
    25면 ≈0.04로 단 25단계밖에 없다. 그래서 `max_df_ratio`로 고빈도어를
    따로 한 번 더 자른다 — IDF만으로는 덜 눌린다.
    데이터셋이 수백 개가 되면 이 보조 장치는 빼도 된다.

    반환: {dataset_id: [{"term":..., "tf":..., "idf":..., "tfidf":...}, ...]}
    """
    n_docs = len(tf)
    if n_docs == 0:
        return {}

    df = Counter()
    for counter in tf.values():
        df.update(counter.keys())          # 한 데이터셋에서 몇 번 나왔든 df는 1 증가

    df_cap = max_df_ratio * n_docs
    out: Dict[str, List[dict]] = {}
    for dataset_id, counter in tf.items():
        scored = []
        for term, freq in counter.items():
            if freq < min_tf or df[term] > df_cap:
                continue
            # 평활 IDF. df가 n_docs와 같아도 0이 되지 않게 분자에 +1을 둔다
            idf = math.log((1 + n_docs) / (1 + df[term])) + 1.0
            scored.append({"term": term, "tf": freq, "df": df[term],
                           "idf": round(idf, 4), "tfidf": round(freq * idf, 4)})
        scored.sort(key=lambda d: (-d["tfidf"], d["term"]))
        out[dataset_id] = scored[:top_k]
    return out


def representative_chunks(chunks: Sequence[Tuple[str, str]],
                          keywords: Sequence[dict],
                          limit: int = SUMMARY_CHUNKS) -> List[str]:
    """상위 키워드가 가장 조밀한 청크를 골라 대표 문장으로 삼는다 (추출 요약).

    chunks: (embed_text, token_text) 목록 — 한 데이터셋 소속
    keywords: 이 데이터셋의 tfidf 상위 목록

    점수는 **길이로 나눈다.** 안 나누면 그냥 긴 청크가 이기는데, 긴 청크는
    대개 여러 주제가 섞여 있어 대표성이 떨어진다.

    같은 문장이 여러 아이템에 반복되는 경우(정형 안내 문구 등)가 있어 중복을 지운다.
    """
    weight = {k["term"]: k["tfidf"] for k in keywords}
    if not weight:
        return []

    scored = []
    for text, tokens in chunks:
        toks = (tokens or "").split()
        if not toks:
            continue
        hit = sum(weight.get(t, 0.0) for t in toks)
        if hit <= 0:
            continue
        scored.append((hit / math.sqrt(len(toks)), text))

    scored.sort(key=lambda p: -p[0])
    seen, out = set(), []
    for _, text in scored:
        key = text.strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= limit:
            break
    return out
