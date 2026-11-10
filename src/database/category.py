"""dcat_dataset.category — 공통 분류 **추천** (임베딩 zero-shot).

⚠️ **2026-11-02부터 이 모듈은 분류를 확정하지 않는다**
([ADR-020](../../docs/adr/020_Category_Suggestion_Not_Assignment.md)).
추천 상위 5개를 `meta_feature(feature_name='suggested_category')`에 쌓고,
`dcat_dataset.category`는 **사람이 등록 화면에서 고른 값**만 들어간다.

와이즈넛은 정형에 **언어 모델**로 부여하고, 응답이 없거나 표 밖의 값만 나오면
**데이터셋 요약 임베딩과 가장 가까운 중분류 1개**를 넣는다고 정의했다.

우리는 [ADR-013](../../docs/adr/013_No_External_LLM_API.md)으로 외부 LLM을 쓰지
않으므로 **그 폴백 경로를 주 경로로 쓴다.** 같은 분류표·같은 형식·같은 개수 규칙을
지키므로 결과는 상호 운용된다.

방식:
  1. 분류표 76개를 각각 임베딩한다(한 번 계산 후 프로세스 내 재사용)
  2. 데이터셋 텍스트(제목 + 설명 + 키워드 + theme)를 임베딩한다
  3. 코사인 유사도 상위 N개를 고른다. 단 **임계값 미만은 버린다** —
     억지로 3개를 채우면 관련 없는 분류가 붙는다

⚠️ 분류 품질은 임베딩 모델 성능에 직접 묶인다. 현재 모델
(`paraphrase-multilingual-mpnet-base-v2`)은 검색용으로 학습된 것이 아니라
짧은 라벨 ↔ 짧은 텍스트 비교에는 그나마 맞지만, 전환을 검토 중인
`multilingual-e5-base`로 바꾸면 **분류 결과가 달라진다. 모델 교체 시 재부여가 필요하다.**
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.common import config
from src.common.category_taxonomy import ALL_CATEGORIES, DECISION_FEATURE, MAX_PER_DATASET, is_valid
from src.database.db import get_conn
from src.embedding import embedder

logger = logging.getLogger(__name__)

# 이 값 미만이면 **추천 목록에서도** 빼낸다.
#
# **0.0 = 거르지 않는다.** 임계값 방식 자체가 성립하지 않기 때문이다 — e5 계열은
# 유사도가 0.7~1.0에 몰려 틀린 답에도 0.82~0.85가 나온다(ADR-018과 같은 현상).
#
# 2026-10-29에는 "틀린 분류가 섞이더라도 일단 채워 둔다"는 결정이었다. 비워 두면
# 포털 전체 필터링이 성립하지 않는다는 이유였다. **2026-11-02에 뒤집었다**
# (ADR-020) — 틀린 분류로 채운 필터는 동작하는 척할 뿐이고, 사람이 등록 화면에서
# 고르면 필터가 더 정확한 값으로 채워진다. 기존 25건은 지우지 않고
# `category_source='auto'`로 표시해 잠정값임을 드러낸다.
#
# ⚠️ **현재 분류 품질은 신뢰할 수 없다.** 사람이 본 정답과 비교한 실측:
#      현 모델 Top-1 3/8, e5-base Top-1 3/8 (모델 교체로 해결되지 않는다)
#      '패션의류 검색 트렌드' → '문화 > 공예', 'HBM 뉴스' → '문화 > 방송·미디어'
#      '치질 수술 안내' → '의료 > 치의학'  ("치" 한 글자에 끌렸다)
#    더 근본적으로 분류 76종은 학술·공공 체계라 **소비재 영역이 아예 없다.**
#    패션·화장품·식품·디지털가전은 무엇을 골라도 틀린다(ADR-020 §남은 과제).
MIN_SIMILARITY = float(config.get_env("CATEGORY_MIN_SIMILARITY", "0.0"))

_label_vecs: Optional[np.ndarray] = None


def _get_label_vectors() -> np.ndarray:
    """분류표 76개의 임베딩. 프로세스당 한 번만 계산한다."""
    global _label_vecs
    if _label_vecs is None:
        logger.info("분류표 임베딩 생성 (%d개)", len(ALL_CATEGORIES))
        _label_vecs = np.array(embedder.encode(ALL_CATEGORIES))
    return _label_vecs


def _dataset_text(row: Dict) -> str:
    """분류 판단에 쓸 데이터셋 요약 텍스트.

    theme(원천 분류)을 넣는 이유: 'Health', '패션의류' 같은 원천 분류가 공통 분류와
    어휘적으로 가까워 신호가 세다. 없으면 제목·설명·키워드만 쓴다.
    """
    parts = [row.get("title") or "", row.get("description") or ""]
    for col in ("keywords", "theme"):
        v = row.get(col) or []
        if isinstance(v, str):
            v = json.loads(v)
        if v:
            parts.append(", ".join(str(x) for x in v))
    return ". ".join(p for p in parts if p)


#: 등록 화면에 제시할 추천 개수. 3개가 아니라 5개다 — `HBM 뉴스`의 적합한 분류가
#: 3위였고 1~5위 점수 차가 0.007에 불과해(잡음 수준) 3개로 자르면 밀려난다(ADR-020).
SUGGEST_N = 5


def classify(text: str, top_n: int = MAX_PER_DATASET) -> List[Tuple[str, float]]:
    """텍스트에 가장 가까운 분류를 (값, 유사도) 목록으로. 임계값 미만은 제외.

    ⚠️ **이 점수로 분류를 확정하지 않는다.** 2026-11-02 전수 확인에서 상위 5개가
    0.042 폭에 몰리고 1위와 3위 차이가 0.0055였다 — 순서 차이가 잡음이다.
    어휘 유사도에도 끌린다(`치질` → `의료 > 치의학`, `화장품` → `의료 > 의약품`).
    용도는 **사람에게 보여줄 추천 목록**뿐이다([ADR-020](../../docs/adr/020_Category_Suggestion_Not_Assignment.md)).
    """
    if not text.strip():
        return []
    labels = _get_label_vectors()
    # 데이터셋 텍스트를 '질의'로, 분류 라벨을 '문서'로 둔다 — 짧은 라벨에서
    # 긴 텍스트를 찾는 게 아니라 그 반대가 이 작업의 모양이다.
    v = np.array(embedder.encode_query(text))
    sims = labels @ v / (np.linalg.norm(labels, axis=1) * np.linalg.norm(v))
    order = np.argsort(-sims)[:top_n]
    return [(ALL_CATEGORIES[i], float(sims[i])) for i in order
            if sims[i] >= MIN_SIMILARITY]


def sync_category(dataset_id: str) -> List[str]:
    """분류 **추천**을 다시 계산해 meta_feature에 저장한다. 반환: 추천 목록.

    **`dcat_dataset.category`를 덮어쓰지 않는다.** 그 컬럼은 사람이 확정한 값이고,
    자동 분류는 추천까지만 한다([ADR-020](../../docs/adr/020_Category_Suggestion_Not_Assignment.md)).

    이전에는 수집할 때마다 상위 3개를 확정값으로 집어넣었다. 그 결과
    `HBM 뉴스`에 `문화 > 방송·미디어`·`문화 > 스포츠`가, `화장품`에 `의료 > 의약품`이,
    `치질`에 `의료 > 치의학`이 붙었다. **틀린 분류는 빈 분류보다 나쁘다** —
    조용히 틀린 채로 남아 검색·관계·통계를 전부 오염시킨다.

    추천을 `meta_feature`에 두는 이유는 두 가지다.
    1. "계산된 것"과 "확정된 것"이 테이블 수준에서 갈린다. 재계산이 자유롭다.
    2. 사람이 추천 몇 위를 골랐는지(또는 아무것도 안 골랐는지) 비교할 수 있다 —
       그게 분류기 개선의 유일한 근거이고, 검색 평가셋(P0-6)의 씨앗이다.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT dataset_id, title, description, keywords, theme
                 FROM dcat_dataset WHERE dataset_id = %s""",
            (dataset_id,),
        )
        row = cur.fetchone()
        if row is None:
            return []
        names = [d[0] for d in cur.description]
        scored = classify(_dataset_text(dict(zip(names, row))), top_n=SUGGEST_N)
        valid = [(c, sc) for c, sc in scored if is_valid(c)]
        if not valid:
            logger.info("분류 추천 없음 (텍스트 없음): %s", dataset_id)
            return []

        suggestions = [{"category": c, "score": round(sc, 4), "rank": i}
                       for i, (c, sc) in enumerate(valid, 1)]
        cur.execute(
            """INSERT INTO meta_feature
                   (dataset_id, scope, target, feature_name, value, method)
               VALUES (%s, 'dataset', '', 'suggested_category', %s, %s)
               ON CONFLICT (dataset_id, scope, target, feature_name) DO UPDATE
               SET value = EXCLUDED.value, method = EXCLUDED.method, computed_at = now()""",
            (dataset_id, json.dumps(suggestions, ensure_ascii=False),
             f"cosine/{embedder.MODEL_NAME}"),
        )
        conn.commit()
        cats = [c for c, _ in valid]
        logger.info("분류 추천 %d건: %s", len(cats), ", ".join(cats[:3]))
        return cats
    finally:
        conn.close()


# ── 등록 전 추천 · 확정 기록 (ADR-020 §4) ──────────────────────────────────

def suggest_for_text(title: str, description: str = "", keywords: Optional[List[str]] = None
                     ) -> List[Dict[str, object]]:
    """등록 **전** 화면용 추천 — 아직 DB에 데이터셋이 없으므로 입력값으로 계산하고 쓰지 않는다.

    `sync_category`와 같은 텍스트 구성(`_dataset_text`)을 쓴다. 다르면 등록 때 본 추천과
    첫 수집 뒤 추천이 입력이 같아도 달라져 "추천이 바뀌었습니다"가 거짓으로 뜬다.
    """
    text = _dataset_text({"title": title, "description": description, "keywords": keywords or []})
    scored = classify(text, top_n=SUGGEST_N)
    return [{"category": c, "score": round(sc, 4), "rank": i}
            for i, (c, sc) in enumerate([(c, s) for c, s in scored if is_valid(c)], 1)]




def latest_suggestions(cur, dataset_id: str) -> List[Dict[str, object]]:
    cur.execute("SELECT value FROM meta_feature WHERE dataset_id=%s AND scope='dataset' "
                "AND target='' AND feature_name='suggested_category'", (dataset_id,))
    row = cur.fetchone()
    v = row[0] if row else None
    if isinstance(v, str):
        v = json.loads(v)
    return v or []


def record_decision(cur, dataset_id: str, previous: List[str], chosen: List[str],
                    shown: Optional[List[Dict[str, object]]], actor: str, role: str) -> Dict[str, object]:
    """분류 확정 1건을 이력에 **덧붙인다**(커밋은 호출자가 — 분류 UPDATE와 같은 트랜잭션).

    남기는 것: 그때 보여 준 추천 목록, 고른 값, 이전 값, 누가(역할 포함).
    이게 있어야 "사람이 추천 몇 위를 골랐나 / 추천 밖에서 골랐나"를 셀 수 있다 —
    분류기 개선과 D-1(공통 분류를 비정형에 쓸 것인가) 판단의 근거다.

    `shown`이 None이면 지금 저장된 최신 추천을 보여 준 것으로 본다(관리자 상세 화면).
    """
    if shown is None:
        shown = latest_suggestions(cur, dataset_id)
    ranks = {s["category"]: s.get("rank") for s in shown if isinstance(s, dict)}
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": actor, "role": role,
        "previous": previous, "chosen": chosen,
        "shown": [s.get("category") for s in shown if isinstance(s, dict)],
        # 고른 값 각각이 추천 몇 위였나. 추천 밖이면 None
        "chosen_ranks": [ranks.get(c) for c in chosen],
    }
    cur.execute(
        """INSERT INTO meta_feature (dataset_id, scope, target, feature_name, value, method)
           VALUES (%s, 'dataset', '', %s, %s::jsonb, 'human')
           ON CONFLICT (dataset_id, scope, target, feature_name) DO UPDATE
           SET value = meta_feature.value || EXCLUDED.value, computed_at = now()""",
        (dataset_id, DECISION_FEATURE, json.dumps([entry], ensure_ascii=False)))
    return entry
