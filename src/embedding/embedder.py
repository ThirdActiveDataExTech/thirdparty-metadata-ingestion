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

from src.common import config

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
MAX_SEQ_LENGTH = 128
BATCH_SIZE = 32

# ⚠️ **디바이스를 CPU로 고정한다.**
#
# SentenceTransformer는 Apple Silicon에서 MPS를 자동 선택하는데, **MPS에서 배치
# 인코딩을 하면 벡터가 망가진다.** 같은 문장을 단건으로 넣었을 때와 배치에 섞어
# 넣었을 때의 코사인 유사도가 1.0이어야 하는데 0.0073이 나온다(2026-10-28 실측).
#
#     [mps] 단건 vs 배치0번: 0.0073    단건 vs 단건재실행: 1.0000
#     [cpu] 단건 vs 배치0번: 1.0000    단건 vs 단건재실행: 1.0000
#
# 단건끼리는 재현되므로 비결정성이 아니라 **배치 패딩/어텐션 마스크 처리 버그**로
# 보인다. 이 때문에 첫 백필 33,875건이 전부 쓸 수 없는 값이었고, 검색하면 질의와
# 무관한 짧은 제목이 상위에 올라왔다(제목이 글자까지 같은 항목이 123위).
#
# 운영 서버는 GPU가 없어(ADR-013) 어차피 CPU다. MPS는 개발용 Mac에서만 잡힌다.
# 다른 가속기를 쓰려면 EMBEDDING_DEVICE로 명시하되, 반드시 self_check()를 통과시킬 것.
DEVICE = config.get_env("EMBEDDING_DEVICE", "cpu")

_model = None
_lock = threading.Lock()


def self_check(model) -> None:
    """배치 인코딩이 단건 인코딩과 같은 벡터를 내는지 확인한다.

    MPS 배치 버그 같은 류를 모델 로딩 시점에 잡는다. 통과 못 하면 그 디바이스로
    만든 임베딩은 전부 버려야 하므로, 조용히 넘어가지 않고 바로 실패시킨다.
    """
    probe = "임베딩 정합성 확인용 문장"
    alone = model.encode([probe])[0]
    batched = model.encode([probe, "다른 문장 하나", "또 다른 문장"])[0]
    import numpy as np

    sim = float(
        np.dot(alone, batched)
        / (np.linalg.norm(alone) * np.linalg.norm(batched))
    )
    if sim < 0.999:
        raise RuntimeError(
            f"임베딩 자가검증 실패 — device={DEVICE!r}에서 배치 인코딩 결과가 "
            f"단건과 다릅니다(코사인 {sim:.4f}, 1.0이어야 정상).\n"
            f"  이 디바이스로 만든 벡터는 쓸 수 없습니다. "
            f"EMBEDDING_DEVICE=cpu로 두세요."
        )


def get_model():
    """모델을 지연 로딩한다. 로딩에 5초 남짓 걸리므로 쓸 때만 올린다."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info("임베딩 모델 로딩: %s (device=%s)", MODEL_NAME, DEVICE)
                m = SentenceTransformer(MODEL_NAME, device=DEVICE)
                m.max_seq_length = MAX_SEQ_LENGTH
                self_check(m)
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
