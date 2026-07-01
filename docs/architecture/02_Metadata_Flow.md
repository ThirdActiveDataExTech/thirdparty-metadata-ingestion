# 02. Metadata Flow

> **Last Updated:** 2026-07-01
> **Status:** 작성 중 — 수집 코드 개발 완료 후 업데이트

---

## 데이터 흐름 개요

```
외부 API
    ↓
Collector       raw JSON / XML
    ↓
MinIO           raw/{source_type}/{dataset_id}/YYYY/MM/DD/
    ↓
Preprocess      정제 / 정규화
    ↓
Extractor       DCAT 메타데이터 추출
    ↓
PostgreSQL      dcat_dataset, dcat_provenance, meta_*, active_*
```

---

## 메타데이터 레이어

| 레이어 | 테이블 | 설명 |
|--------|--------|------|
| DCAT | `dcat_dataset` | 데이터셋 전반 기술 |
| PROV | `dcat_provenance` | 수집 실행 이력 |
| 운영 | `data_registry` | 저장소 경로, 운영 현황 (예정) |
| 소스별 메타 | `meta_youtube_*`, `meta_naver_*` | Schema.org 기반 (예정) |
| Active Meta | `active_*` | 시계열 증감 지표 (예정) |

---

*상세 흐름은 각 소스별 수집 코드 완성 후 작성.*
