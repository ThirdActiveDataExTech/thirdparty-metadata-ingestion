# 01. Local Development

> **Last Updated:** 2026-07-28
> **Status:** 실제 개발/서버 환경 기준으로 전면 갱신 — 이전 버전은 `src/` 코드가
> 생기기 전 초안이라 Python 버전·설치 방법·실행 명령이 실제와 달랐다.

---

## 개발 환경

| 항목 | 값 |
|------|-----|
| OS | macOS(로컬 개발) / Linux(서버, `RnD-analyzer01`) |
| Python | **3.9** — `pyproject.toml`의 `requires-python`도 실제 환경에 맞춰 `>=3.9`로 되어 있다(예전엔 `>=3.10`으로 잘못 적혀 있어서 서버에서 `pip install -e .`가 막힌 적 있음, 2026-07-28 수정) |
| DB 접속 | 서버 PostgreSQL NodePort 직접 접속 (<서버-IP>:30433) |
| IDE | VSCode + Claude Code |

---

## 초기 설정

```bash
# 1. 저장소 클론
git clone git@github.com:ThirdActiveDataExTech/metadata-ingestion.git
cd metadata-ingestion

# 2. venv 생성 + 의존성 설치 (requirements.txt 아님 — pyproject.toml 기준)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 값 입력 (05_Secrets_ConfigMaps.md 참고)

# 4. DB 연결 확인
PYTHONPATH=. python -c "from src.database.db import get_conn; get_conn(); print('OK')"
```

**주의**: `src/collectors/youtube_transcript_collector.py`(자체 STT)가 `sentence-
transformers`를 통해 무거운 `torch`를 끌어오는데, 이때 pip가 GPU용 CUDA 패키지까지
같이 받으려 해서 디스크를 수 GB 잡아먹을 수 있다(2026-07-28 `RnD-analyzer01`에서
실측 — root 디스크가 작은 서버라면 특히 주의). 필요한 패키지만 좁혀서 설치하고
싶으면 `pip install -e .` 대신 개별 패키지를 설치할 것.

## 스크립트 실행 시 흔한 함정 — `ModuleNotFoundError: No module named 'src'`

`python scripts/register_dataset.py ...`처럼 **경로로 스크립트를 직접 실행**하면
파이썬이 저장소 루트가 아니라 `scripts/` 디렉토리를 import 기준으로 잡아서 `src`
모듈을 못 찾는다. 저장소 루트에서 실행하는데도 이 에러가 나면 `PYTHONPATH=.`를
앞에 붙일 것:

```bash
PYTHONPATH=. python scripts/register_dataset.py video --title "..." ...
PYTHONPATH=. python -m src.main run <dataset_id>   # -m으로 실행하면 이 문제 없음
```

---

## 실행

```bash
# 데이터셋 하나 수집 실행 (source_type에 따라 알맞은 pipelines/*.py로 자동 위임)
PYTHONPATH=. python -m src.main run <dataset_id>

# 신규 데이터셋 등록 (§6.3 프론트엔드 API 전까지의 실질적 등록 경로)
PYTHONPATH=. python scripts/register_dataset.py video \
    --title "..." --description "..." --subjects <채널ID,...>

# 테스트
PYTHONPATH=. python -m pytest tests/ -q
```

`python src/main.py`(모듈이 아니라 파일 직접 실행)는 동작하지 않는다 — 반드시
`python -m src.main run <dataset_id>` 형태로 실행할 것.

---

*상세 내용(Docker 기반 개발 환경 등)은 아직 없음 — 지금은 서버에 직접 git pull +
venv로 실행하는 방식만 실제로 쓰인다. `02_Deployment.md` 참조.*
