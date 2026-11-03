# ══════════════════════════════════════════════════════════════════════
# metadata-ingestion — 수집·임베딩·검색 실행 이미지 (P0-3)
#
# 왜 필요한가: Dockerfile이 없어 C3·C4(파이프라인 자동화·스케줄링)가 구조적으로
# 막혀 있었다. 지금은 서버에서 사람이 CLI를 직접 쳐야만 수집이 된다 — 그 결과
# 2026-11-02 기준 18개 데이터셋이 수집 예정일을 2~3일 넘겼고, 발견형 소스의
# 시계열 관측일이 1일뿐이다(docs/database/metadata_quality_probe.md).
#
# 사내 정책: Docker Hub 이미지는 registry.example.com/hub 경유, `latest` 금지,
#            원본 주소는 지우지 않고 주석으로 남긴다.
#
# 빌드 (레지스트리가 닿는 곳에서):
#   docker build -f docker/Dockerfile -t registry.example.com/metadata-ingestion:0.1.0 .
#   docker push  registry.example.com/metadata-ingestion:0.1.0
#
# ⚠️ 빌드 시점에 네트워크가 필요하다 — 임베딩 모델을 **이미지에 굽는다**.
#    런타임에 HuggingFace를 받으러 가지 않게 하려는 것이고, 04_Implementation_Methods
#    §1.3이 "폐쇄망 다운로드 실패가 최대 운영 리스크"로 지목한 바로 그 지점이다.
# ══════════════════════════════════════════════════════════════════════

# ── 1단계: 의존성 설치 ────────────────────────────────────────────────
# image: python:3.11.9-slim
FROM registry.example.com/hub/python:3.11.9-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psycopg2-binary·ctranslate2는 휠로 오지만, 일부 패키지가 빌드 도구를 요구한다.
# 최종 이미지에는 안 남는다(이 단계는 통째로 버려진다).
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
# 소스는 복사하지 않는다 — 코드만 바뀌었을 때 이 레이어를 재사용하기 위해서다.
# 그래서 `pip install .`이 아니라 **의존성 목록만** 꺼내 설치한다. 이 저장소는
# 패키지로 설치해 쓰지 않고 PYTHONPATH=/app 으로 돌린다(개발 환경과 동일).
# tomllib는 3.11 표준 라이브러리라 추가 의존성이 없다.
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
 && /opt/venv/bin/pip install -r /tmp/requirements.txt

# ── 2단계: 모델 굽기 ──────────────────────────────────────────────────
# 런타임에 외부로 나가지 않도록 가중치를 이미지에 포함한다.
# kiwipiepy는 모델을 패키지에 동봉하므로 여기서 받을 것이 없다(ADR-010 선정 이유 중 하나).
FROM builder AS models

ENV HF_HOME=/opt/hf
RUN /opt/venv/bin/python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-base', device='cpu')" \
 && /opt/venv/bin/python -c "from kiwipiepy import Kiwi; Kiwi()"

# ── 3단계: 실행 이미지 ────────────────────────────────────────────────
# image: python:3.11.9-slim
FROM registry.example.com/hub/python:3.11.9-slim AS runtime

# ffmpeg: yt-dlp가 오디오를 뽑을 때 쓴다(YouTube 자막 STT).
# libgomp1: ctranslate2(faster-whisper)가 링크한다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=models  /opt/hf   /opt/hf

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    EMBEDDING_DEVICE=cpu \
    TZ=UTC
# HF_HUB_OFFLINE=1 — 모델을 이미 구웠으므로 외부로 나갈 이유가 없다. 켜 두면
#   폐쇄망에서 "조용히 느려지다 타임아웃"이 아니라 **즉시 명확한 실패**가 난다.
# EMBEDDING_DEVICE=cpu — ADR-016. 다른 값을 주면 self_check()가 막는다.

WORKDIR /app
COPY src/     /app/src/
COPY scripts/ /app/scripts/
COPY sql/     /app/sql/

# 루트로 돌지 않는다. 쓰기는 /tmp만 필요하다(모델·코드는 읽기 전용).
RUN useradd --create-home --uid 10001 ingest \
 && chown -R ingest:ingest /app
USER ingest

# 기본은 스케줄러 틱 — CronJob이 이 이미지를 인자 없이 돌린다.
#   수동 1건   : docker run ... python -m src.main run <dataset_id>
#   토큰 백필  : docker run ... python scripts/backfill_tokens.py
ENTRYPOINT ["python"]
CMD ["scripts/scheduler_tick.py"]
