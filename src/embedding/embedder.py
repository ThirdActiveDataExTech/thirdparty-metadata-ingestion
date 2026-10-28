"""임베딩 모델 래퍼 — 프로세스당 1개 로딩, 배치 인코딩.

모델은 `paraphrase-multilingual-mpnet-base-v2`(768차원). ADR-003에서 정한 모델로
한국어를 포함한 다국어를 같은 공간에 넣는다.

**max_seq_length는 128이다**(모델 기본값, 2026-10-28 실측 확인). 토큰 128개를
넘는 입력은 잘린다 — 본문을 통째로 넣어도 앞부분만 반영되므로, 호출부가 미리
의미 있는 앞부분을 골라 넘겨야 한다(뉴스·블로그는 본문 앞 500자).

CPU 실측(2026-10-28): batch_size=32에서 약 138건/초. 29,029건이면 3~4분.
GPU가 없는 환경이라 batch_size를 키우는 것이 유일한 가속 수단이다.
"""

import logging
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
MAX_SEQ_LENGTH = 128
BATCH_SIZE = 32

_model = None
_lock = threading.Lock()


def get_model():
    """모델을 지연 로딩한다. 로딩에 5초 남짓 걸리므로 쓸 때만 올린다."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info("임베딩 모델 로딩: %s", MODEL_NAME)
                m = SentenceTransformer(MODEL_NAME)
                m.max_seq_length = MAX_SEQ_LENGTH
                _model = m
    return _model


def encode(texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
    """텍스트 목록을 768차원 벡터 목록으로. 빈 목록이면 모델도 안 올린다."""
    if not texts:
        return []
    vectors = get_model().encode(
        texts, batch_size=batch_size or BATCH_SIZE, show_progress_bar=False
    )
    return [v.tolist() for v in vectors]
