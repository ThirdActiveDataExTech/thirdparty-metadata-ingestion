# 01. System Architecture

> **Last Updated:** 2026-07-28
> **Status:** §6.1(5개 소스 Collector) + SeaweedFS raw/JSON-LD export 전부 완료,
> 실 서버(`RnD-analyzer01`)에도 배포·검증 완료. 남은 건 §6.2(Airflow — 지금은
> 수동 CLI 트리거)와 §6.3(프론트엔드 등록 API — 지금은 `scripts/register_dataset.py`),
> §5(AI 생성 메타데이터 — 아직 설계 단계).

---

## 전체 구조

```
Mac (개발)
    ↓ git push
GitHub
    ↓ git pull
Server (RnD-analyzer01 등)
    ├── Collector (수동 CLI, `python -m src.main run <dataset_id>`)
    │                                          [✅ 완료 — YouTube/뉴스/블로그/쇼핑/Persona
    │                                           5개 소스 전부 src/collectors/, src/pipelines/
    │                                           로 구현, 실 API 검증 완료. Airflow(§6.2)로
    │                                           스케줄 자동화하는 것만 아직 안 됨]
    │       ↓
    │   Raw Data → SeaweedFS (S3 API)        [✅ 완료 — 아이템별 raw 파일(YouTube 트랜스크립트
    │                                           JSON, 뉴스/블로그 본문 txt, 쇼핑/Persona CSV)
    │                                           전부 실제로 저장됨, 05_Object_Storage_Export.md]
    │       ↓
    │   (Preprocess/Extractor 별도 레이어 없음 — collectors/pipelines 내부 헬퍼로 대체,
    │    03_Component_Architecture.md 참조)
    │       ↓
    │   Metadata → PostgreSQL (datagokr)     [✅ 운영 중 — 실 수집 데이터]
    │       ↓
    │   Metadata → SeaweedFS (JSON-LD)       [✅ 완료 — 데이터셋당 1개, dcat_dataset+아이템+
    │                                           active metadata 통합]
    │       ↓
    │   Embedding → pgvector                 [✅ 운영 중(수동 실행) — scripts/embed_*.py,
    │                                           search_*.py. 파이프라인 자동 연결·증분화는 미완]
    │
    ├── PostgreSQL 17.4 (datagokr) + pgvector 0.8.4
    ├── SeaweedFS (오브젝트 스토리지, Apache 2.0) — `metadata-ingestion` K8s 네임스페이스 생성 완료
    └── (향후, 규모 커지면) Qdrant 전환 — ADR-003 참조
```

> 지금 "동작하는" 부분: PostgreSQL 스키마 + pgvector 임베딩/검색 스크립트,
> YouTube/뉴스/블로그/쇼핑/Persona 전체 Collector(`python -m src.main run
> <dataset_id>`로 수동 실행 — Airflow/CronJob 자동화는 아직), SeaweedFS raw/JSON-LD
> 저장(YouTube 트랜스크립트는 자체 STT). 안 되는 건: Airflow 스케줄링(§6.2),
> 프론트엔드 등록 API(§6.3, 지금은 `scripts/register_dataset.py`로 대체), AI
> 생성 메타데이터(§5, 아직 설계 단계).

---

## 컴포넌트별 역할

| 컴포넌트 | 역할 | 기술 | 상태 |
|----------|------|------|------|
| Collector | 외부 API 호출, Raw Data 수집 | Python | ✅ 완료 — 5개 소스(`src/collectors/`, `src/pipelines/`) 실 검증 완료 |
| Preprocess/Extractor | 원본 정제·메타데이터 추출 | Python | 별도 레이어 없음(설계 변경) — `collectors`/`pipelines` 내부 헬퍼로 처리, `03_Component_Architecture.md` 참조 |
| Storage (PostgreSQL) | 메타데이터 DB 저장 | Python | ✅ 운영 중 |
| Storage (SeaweedFS) | Raw Data + JSON-LD 저장 | Python | ✅ 완료 — `src/storage/`(s3_client/raw_export/jsonld_export), 실 서버 검증 완료. YouTube 트랜스크립트는 `src/collectors/youtube_transcript_collector.py`(자체 STT) |
| Embedding | pgvector 임베딩 생성·검색 | Python | ✅ 운영 중(수동) — `scripts/embed_datasets.py`, `embed_video.py`, `embed_news.py`, `embed_blog.py` + 대응 `search_*.py`. 파이프라인 자동 연결·증분화는 미완(NEXT_STEPS.md §4) |
| AI 생성 메타 | 트랜스크립트/본문 → 요약·키워드·개체명 등 | Python | ⏳ 설계 단계 — 필드 후보만 정리됨(`datagokr_schema.md`), 착수 예정 |
| Scheduler | 수집 주기 관리 | K8s CronJob → 추후 Airflow | ⏳ 미착수 — `metadata-ingestion` K8s 네임스페이스는 생성 완료, DAG·Executor 방식은 아직(§6.2) |

---

*상세 내용은 개발 진행에 따라 채워진다. 데이터 흐름 상세는
[02_Metadata_Flow.md](02_Metadata_Flow.md), SeaweedFS raw/JSON-LD 설계는
[05_Object_Storage_Export.md](05_Object_Storage_Export.md), 벡터 검색 상세는
[06_VectorDB.md](../infrastructure/06_VectorDB.md) 참조.*
