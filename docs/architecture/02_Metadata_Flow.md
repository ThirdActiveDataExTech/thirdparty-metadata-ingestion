# 02. Metadata Flow

> **Last Updated:** 2026-07-28
> **Status:** 5개 source_type(YouTube/뉴스/블로그/쇼핑/Persona) 전부 실제로 동작 중
> (§6.1 완료, 실 서버·실 API 검증 완료). Airflow(§6.2)만 아직 없어서 `python -m
> src.main run <dataset_id>`로 수동 트리거하는 것만 자동화가 안 된 부분이다.

---

## 데이터 흐름 개요

```
외부 API
    ↓
Collector       raw JSON (src/collectors/)                          [✅ 운영 중, 5개 소스]
    ↓
SeaweedFS       raw/{source_type}/{dataset_id}/{item_key}.json|txt|csv  (S3 API)  [✅ 운영 중]
    ↓
(Preprocess/Extractor 별도 레이어 없음 — collectors/pipelines 내부 헬퍼로 처리,
 03_Component_Architecture.md 참조)
    ↓
PostgreSQL      dcat_dataset, dcat_provenance, meta_*, active_*      [✅ 운영 중, 실 수집 데이터]
    ↓
SeaweedFS       jsonld/{source_type}/{dataset_id}/{dataset_id}.jsonld [✅ 운영 중 — dcat_dataset+
                아이템+active metadata 통합, architecture/05_Object_Storage_Export.md]
    ↓
Embedding       scripts/embed_*.py                                   [✅ 운영 중, 수동 실행 —
                아직 파이프라인에 자동 연결 안 됨, 증분화도 미완(NEXT_STEPS.md §4)]
    ↓
pgvector        dcat_dataset_vec, meta_video_vec,
                meta_news_vec, meta_blog_vec              [✅ 운영 중, 검색 테스트 완료]
```

> **YouTube만 추가 경로가 하나 더 있다**: 신규 영상 발견 시 `yt-dlp`로 오디오
> 다운로드 → `faster-whisper`로 로컬 STT(자체, 레거시의 비공식 API 직접 호출
> 방식은 IP 차단 확인돼 채택 안 함) → 세그먼트 JSON을 SeaweedFS raw에 저장.
> 상세: [05_Object_Storage_Export.md](05_Object_Storage_Export.md) §4.

**아직 자동 실행 안 되는 것**: 위 흐름 전체가 Airflow가 아니라 `python -m
src.main run <dataset_id>` **수동 트리거**로만 동작한다(§6.2 미착수). 신규
데이터셋도 `scripts/register_dataset.py`로 수동 등록해야 한다(§6.3 프론트엔드
API 미착수). AI 생성 메타데이터(`meta_*_ai`, 아래 표)는 아직 설계 단계.

---

## 메타데이터 레이어

| 레이어 | 테이블 | 설명 | 상태 |
|--------|--------|------|------|
| DCAT | `dcat_dataset` | 데이터셋 전반 기술 | ✅ 운영 중 |
| PROV | `dcat_provenance` | 수집 실행 이력 | ✅ 운영 중 |
| 운영 | `data_registry` | 저장소 경로(`s3_raw_prefix`/`s3_jsonld_prefix` 포함), 운영 현황 | ✅ 운영 중 |
| 소스별 메타 | `meta_video`, `meta_news`, `meta_blog`, `meta_shopping_insight`, `meta_persona_insight` | Schema.org 기반 | ✅ 운영 중, 실 수집 데이터 |
| Active Meta | `active_*` | 시계열 증감 지표 | ✅ 운영 중 |
| 벡터 임베딩 | `dcat_dataset_vec`, `meta_video_vec`, `meta_news_vec`, `meta_blog_vec` | pgvector 768차원 | ✅ 운영 중(수동 실행) |
| AI 생성 메타 | `meta_video_ai`, `meta_news_ai`, `meta_blog_ai` | LLM 요약·키워드·개체명 등 | ⏳ 설계 단계(필드 후보만, `datagokr_schema.md` 참조) |

---

*자세한 파이프라인 실행 로직(신규/기존 분기, 삭제 감지, 스케줄링)은
[04_Collection_Pipeline_Operations.md](04_Collection_Pipeline_Operations.md),
SeaweedFS raw/JSON-LD 저장 상세 설계는
[05_Object_Storage_Export.md](05_Object_Storage_Export.md) 참조.*
