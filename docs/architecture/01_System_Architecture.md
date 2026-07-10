# 01. System Architecture

> **Last Updated:** 2026-07-10
> **Status:** 작성 중 — 개발이 진행되면서 업데이트
>
> 아래 다이어그램은 목표 아키텍처다. 실제로 코드가 존재하는 부분(임베딩)과
> 인프라만 배포되고 연동 코드가 없는 부분(Collector/Preprocess/Extractor)을
> 상태로 구분해뒀다 — `src/`, `configs/`, `docker/`, `tests/`는 현재 `.gitkeep`뿐인
> 빈 폴더다.

---

## 전체 구조

```
Mac (개발)
    ↓ git push
GitHub
    ↓ git pull
Server (Kubernetes)
    ├── Collector (CronJob)                  [⏳ 예정 — src/collectors/ 코드 없음, metadata-ingestion 네임스페이스도 미생성]
    │       ↓
    │   Raw Data → SeaweedFS (S3 API)        [SeaweedFS 배포·연결 확인 완료 / 현재 버킷 오브젝트 0건]
    │       ↓
    │   Preprocess → Extractor               [⏳ 예정 — src/preprocess/, src/extractor/ 코드 없음]
    │       ↓
    │   Metadata → PostgreSQL (datagokr)     [✅ 스키마·데이터 있음 — 현재는 sql/seeds.sql 시드 데이터]
    │       ↓
    │   Embedding → pgvector                 [✅ 운영 중 — scripts/embed_*.py, search_*.py]
    │
    ├── PostgreSQL 17.4 (datagokr) + pgvector 0.8.4
    ├── SeaweedFS (오브젝트 스토리지, Apache 2.0)
    └── (향후, 규모 커지면) Qdrant 전환 — ADR-003 참조
```

> 즉 지금 "동작하는" 부분은 PostgreSQL 스키마 + pgvector 임베딩/검색 스크립트뿐이다.
> 외부 API를 직접 호출해 데이터를 수집하는 Collector는 아직 코드로 존재하지 않으며,
> DB의 현재 데이터는 전부 `sql/seeds.sql`로 넣은 샘플이다.

---

## 컴포넌트별 역할

| 컴포넌트 | 역할 | 기술 | 상태 |
|----------|------|------|------|
| Collector | 외부 API 호출, Raw Data 수집 | Python | ⏳ 예정 (`src/collectors/` 미작성) |
| Preprocess | 원본 데이터 정제 | Python | ⏳ 예정 (`src/preprocess/` 미작성) |
| Extractor | 메타데이터 추출 | Python | ⏳ 예정 (`src/extractor/` 미작성) |
| Storage | SeaweedFS (S3 API) / PostgreSQL 저장 | Python | ⏳ 예정 (인프라는 배포 완료, 연동 코드는 없음) |
| Embedding | pgvector 임베딩 생성·검색 | Python | ✅ 운영 중 — `scripts/embed_datasets.py`, `embed_youtube_videos.py`, `embed_naver_news.py` + 대응 `search_*.py` |
| Scheduler | 수집 주기 관리 | K8s CronJob → 추후 Airflow | ⏳ 예정 (`metadata-ingestion` 네임스페이스 미생성, [02_Kubernetes.md](../infrastructure/02_Kubernetes.md) 참조) |

---

*상세 내용은 개발 진행에 따라 채워진다. 데이터 흐름 상세는
[02_Metadata_Flow.md](02_Metadata_Flow.md), 벡터 검색 상세는
[06_VectorDB.md](../infrastructure/06_VectorDB.md) 참조.*
