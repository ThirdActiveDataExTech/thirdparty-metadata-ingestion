# datagokr DB Schema

> **Last Updated:** 2026-07-01
> PostgreSQL 17.4 (postgres-174) — NodePort 30433

---

## 테이블 목록

| 테이블 | 상태 | DDL | 설명 |
|--------|------|-----|------|
| `dcat_dataset` | 운영 중 | [sql/dcat_dataset.sql](../../sql/dcat_dataset.sql) | 데이터셋 전반 기술 |
| `dcat_provenance` | 운영 중 | [sql/dcat_provenance.sql](../../sql/dcat_provenance.sql) | 수집 실행 이력 |
| `data_registry` | 운영 중 | [sql/data_registry.sql](../../sql/data_registry.sql) | 통합 운영정보 (저장소 위치, 운영 상태) |
| `dcat_dataset_vec` | DDL 작성 완료 | [sql/dcat_dataset_vec.sql](../../sql/dcat_dataset_vec.sql) | 데이터셋 description 임베딩 (pgvector 768차원) |
| `meta_youtube_channel` | 예정 | — | YouTube 채널 메타 |
| `meta_youtube_video` | 예정 | — | YouTube 영상 메타 |
| `meta_naver_shopping` | 예정 | — | Naver 쇼핑 메타 |
| `meta_naver_news` | 예정 | — | Naver 뉴스 메타 |
| `active_youtube_video` | 예정 | — | YouTube 영상 시계열 지표 |
| `active_naver_shopping` | 예정 | — | Naver 쇼핑 시계열 지표 |

---

## 테이블 관계

```
dcat_dataset (1)  ─── "무엇인가" (명세)
    │
    ├──< dcat_provenance (N)  ─── "언제 어떻게 수집했나" (이력, 실행마다 INSERT)
    │
    ├──  data_registry (1)    ─── "지금 어디 있고 상태는" (운영 현황, 실행마다 UPDATE)
    │
    ├──< meta_*       (N)     ─── "개별 항목 메타" (Schema.org) [예정]
    │
    └──< active_*     (N)     ─── "시계열 지표" (증감 등) [예정]
```

---

*ERD는 주요 테이블 완성 후 추가.*
