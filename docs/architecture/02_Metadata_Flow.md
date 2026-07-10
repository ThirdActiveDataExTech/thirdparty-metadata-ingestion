# 02. Metadata Flow

> **Last Updated:** 2026-07-10
> **Status:** 작성 중 — 수집 코드(Collector/Preprocess/Extractor)는 아직 미작성.
> 아래 표의 "예정"은 코드가 아니라 테이블 상태 기준이며, 대부분의 테이블은
> 이미 스키마 생성이 끝나 있다 — 자세한 상태는
> [datagokr_schema.md](../database/datagokr_schema.md) 참조.

---

## 데이터 흐름 개요

```
외부 API
    ↓
Collector       raw JSON / XML                                        [⏳ 예정]
    ↓
SeaweedFS       raw/{source_type}/{dataset_id}/YYYY/MM/DD/  (S3 API)  [배포 완료, 연동 코드 없음]
    ↓
Preprocess      정제 / 정규화                                          [⏳ 예정]
    ↓
Extractor       DCAT 메타데이터 추출                                    [⏳ 예정]
    ↓
PostgreSQL      dcat_dataset, dcat_provenance, meta_*, active_*        [✅ 스키마 운영 중, 현재는 시드 데이터]
    ↓
Embedding       scripts/embed_*.py                                     [✅ 운영 중]
    ↓
pgvector        dcat_dataset_vec, meta_youtube_video_vec,
                meta_naver_news_vec                                    [✅ 운영 중, 검색 테스트 완료]
```

> Collector~Extractor 코드가 없어 위 흐름은 아직 실제로 자동 실행되지 않는다.
> PostgreSQL 이하(스키마, 시드 데이터, 임베딩)만 지금 동작하는 부분이다.

---

## 메타데이터 레이어

| 레이어 | 테이블 | 설명 | 상태 |
|--------|--------|------|------|
| DCAT | `dcat_dataset` | 데이터셋 전반 기술 | ✅ 운영 중 |
| PROV | `dcat_provenance` | 수집 실행 이력 | ✅ 운영 중 |
| 운영 | `data_registry` | 저장소 경로, 운영 현황 | ✅ 운영 중 |
| 소스별 메타 | `meta_youtube_*`, `meta_naver_*` | Schema.org 기반 | ✅ 생성 완료 (YouTube/뉴스/쇼핑/페르소나) |
| Active Meta | `active_*` | 시계열 증감 지표 | ✅ 생성 완료 |
| 벡터 임베딩 | `dcat_dataset_vec`, `meta_youtube_video_vec`, `meta_naver_news_vec` | pgvector 768차원 | ✅ 운영 중 |
| AI 생성 메타 | `meta_youtube_video_ai`, `meta_naver_news_ai` | LLM 요약·키워드·개체명 | ⏳ 예정 / 미설계 |

---

*Collector/Preprocess/Extractor 코드 완성 후 실제 흐름 다이어그램으로 갱신할 것.*
