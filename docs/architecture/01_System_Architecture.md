# 01. System Architecture

> **Last Updated:** 2026-07-01
> **Status:** 작성 중 — 개발이 진행되면서 업데이트

---

## 전체 구조

```
Mac (개발)
    ↓ git push
GitHub
    ↓ git pull
Server (Kubernetes)
    ├── Collector (CronJob)
    │       ↓
    │   Raw Data → MinIO
    │       ↓
    │   Preprocess → Extractor
    │       ↓
    │   Metadata → PostgreSQL (datagokr)
    │
    ├── PostgreSQL 17.4 (datagokr)
    ├── MinIO (오브젝트 스토리지)
    └── (예정) Qdrant (벡터 DB)
```

---

## 컴포넌트별 역할

| 컴포넌트 | 역할 | 기술 |
|----------|------|------|
| Collector | 외부 API 호출, Raw Data 수집 | Python |
| Preprocess | 원본 데이터 정제 | Python |
| Extractor | 메타데이터 추출 | Python |
| Storage | MinIO / PostgreSQL 저장 | Python |
| Scheduler | 수집 주기 관리 | K8s CronJob → 추후 Airflow |

---

*상세 내용은 개발 진행에 따라 채워진다.*
