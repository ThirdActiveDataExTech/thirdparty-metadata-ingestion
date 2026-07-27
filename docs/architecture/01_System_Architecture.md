# 01. System Architecture

> **Last Updated:** 2026-07-27
> **Status:** 작성 중 — 개발이 진행되면서 업데이트
>
> 아래 다이어그램은 목표 아키텍처다. 실제로 코드가 존재하는 부분(임베딩, YouTube/쇼핑
> Collector)과 아직 없는 부분(뉴스/블로그/Persona Collector, Airflow)을 상태로
> 구분해뒀다 — `src/`는 YouTube+Naver Shopping 파일럿(§6.1 Phase 1)이 채워졌고,
> `configs/`, `docker/`는 여전히 `.gitkeep`뿐인 빈 폴더다.

---

## 전체 구조

```
Mac (개발)
    ↓ git push
GitHub
    ↓ git pull
Server (Kubernetes)
    ├── Collector (CronJob)                  [🔶 일부 완료 — YouTube+Naver Shopping(src/collectors/,
    │                                          src/pipelines/) 실 API 검증 완료 / 뉴스·블로그·Persona
    │                                          는 아직. metadata-ingestion 네임스페이스는 미생성]
    │       ↓
    │   Raw Data → SeaweedFS (S3 API)        [SeaweedFS 배포·연결 확인 완료 / 현재 버킷 오브젝트 0건 —
    │                                          Collector는 지금 SeaweedFS를 거치지 않고 DB에 직접 저장]
    │       ↓
    │   (Preprocess/Extractor 별도 레이어 없음 — collectors/pipelines 내부 헬퍼로 대체,
    │    03_Component_Architecture.md 참조)
    │       ↓
    │   Metadata → PostgreSQL (datagokr)     [✅ 스키마·데이터 있음 — 현재는 sql/seeds.sql 시드 데이터]
    │       ↓
    │   Embedding → pgvector                 [✅ 운영 중 — scripts/embed_*.py, search_*.py]
    │
    ├── PostgreSQL 17.4 (datagokr) + pgvector 0.8.4
    ├── SeaweedFS (오브젝트 스토리지, Apache 2.0)
    └── (향후, 규모 커지면) Qdrant 전환 — ADR-003 참조
```

> 지금 "동작하는" 부분: PostgreSQL 스키마 + pgvector 임베딩/검색 스크립트, 그리고
> YouTube/Naver Shopping 실제 Collector(`python -m src.main run <dataset_id>`로 수동
> 실행 — Airflow/CronJob 자동화는 아직). 뉴스/블로그/Persona Collector는 아직 코드로
> 존재하지 않는다. DB 데이터는 `youtube_samsung_official`/`naver_shopping_insight`만
> 실제 수집 결과가 섞여 있고, 나머지 데이터셋은 여전히 `sql/seeds.sql` 샘플뿐이다.

---

## 컴포넌트별 역할

| 컴포넌트 | 역할 | 기술 | 상태 |
|----------|------|------|------|
| Collector | 외부 API 호출, Raw Data 수집 | Python | 🔶 일부 완료 — YouTube/Naver Shopping(`src/collectors/`, `src/pipelines/`) 실 검증 완료, 뉴스/블로그/Persona는 미작성 |
| Preprocess/Extractor | 원본 정제·메타데이터 추출 | Python | 별도 레이어 없음(설계 변경) — `collectors`/`pipelines` 내부 헬퍼로 처리, `03_Component_Architecture.md` 참조 |
| Storage (PostgreSQL) | 메타데이터 DB 저장 | Python | ✅ 운영 중 — YouTube/쇼핑 Collector가 직접 씀 |
| Storage (SeaweedFS) | Raw Data 백업 | Python | ⏳ 예정 (인프라는 배포 완료, Collector가 아직 S3에 raw 데이터를 쓰지 않음) |
| Embedding | pgvector 임베딩 생성·검색 | Python | ✅ 운영 중 — `scripts/embed_datasets.py`, `embed_youtube_videos.py`, `embed_naver_news.py` + 대응 `search_*.py` |
| Scheduler | 수집 주기 관리 | K8s CronJob → 추후 Airflow | ⏳ 예정 (`metadata-ingestion` 네임스페이스 미생성, [02_Kubernetes.md](../infrastructure/02_Kubernetes.md) 참조) |

---

*상세 내용은 개발 진행에 따라 채워진다. 데이터 흐름 상세는
[02_Metadata_Flow.md](02_Metadata_Flow.md), 벡터 검색 상세는
[06_VectorDB.md](../infrastructure/06_VectorDB.md) 참조.*
