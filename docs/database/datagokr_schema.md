# datagokr DB Schema

> **Last Updated:** 2026-07-10
> PostgreSQL 17.4 (postgres-174) — NodePort 30433

---

## 테이블 목록

| 테이블 | 상태 | DDL | 설명 |
|--------|------|-----|------|
| `dcat_dataset` | ✅ 운영 중 | [sql/dcat_dataset.sql](../../sql/dcat_dataset.sql) | 데이터셋 전반 기술 (admin/user 생성 모두 포함) |
| `dcat_provenance` | ✅ 운영 중 | [sql/dcat_provenance.sql](../../sql/dcat_provenance.sql) | 수집 실행 이력 |
| `data_registry` | ✅ 운영 중 | [sql/data_registry.sql](../../sql/data_registry.sql) | 통합 운영정보 (저장소 위치, 운영 상태) |
| `dcat_dataset_vec` | ✅ 운영 중 | [sql/dcat_dataset_vec.sql](../../sql/dcat_dataset_vec.sql) | 데이터셋 description 임베딩 (pgvector 768차원) |
| `meta_youtube_video` | ✅ 생성 완료 | [sql/meta_youtube_video.sql](../../sql/meta_youtube_video.sql) | YouTube 영상 단위 메타 (Schema.org VideoObject) |
| `meta_youtube_video_vec` | ✅ 생성 완료 | [sql/meta_youtube_video_vec.sql](../../sql/meta_youtube_video_vec.sql) | YouTube 영상 임베딩 (pgvector 768차원) |
| `active_meta_youtube` | ✅ 생성 완료 | [sql/active_meta_youtube.sql](../../sql/active_meta_youtube.sql) | YouTube 영상 시계열 통계 (dataset+video 단위) |
| `meta_youtube_video_ai` | ⏳ 예정 | — | YouTube 영상 AI 생성 메타 (요약·키워드·개체명 등) |
| `meta_naver_news` | ✅ 생성 완료 | [sql/meta_naver_news.sql](../../sql/meta_naver_news.sql) | Naver 뉴스 기사 단위 메타 (Schema.org NewsArticle) |
| `meta_naver_news_vec` | ✅ 생성 완료 | [sql/meta_naver_news_vec.sql](../../sql/meta_naver_news_vec.sql) | Naver 뉴스 기사 임베딩 (pgvector 768차원) |
| `active_meta_naver_news` | ✅ 생성 완료 | [sql/active_meta_naver_news.sql](../../sql/active_meta_naver_news.sql) | Naver 뉴스 기사 시계열 통계 (댓글 수만 수집, [결정 배경](../adr/005_Naver_News_Metrics_Decision.md)) |
| `meta_naver_news_ai` | ⏳ 미설계 | — | Naver 뉴스 기사 AI 생성 메타 |
| `meta_naver_shopping` | ✅ 생성 완료 | [sql/meta_naver_shopping.sql](../../sql/meta_naver_shopping.sql) | 쇼핑인사이트 카테고리 정적 정보 (source_type=shopping_insight) |
| `active_meta_naver_shopping` | ✅ 생성 완료 | [sql/active_meta_naver_shopping.sql](../../sql/active_meta_naver_shopping.sql) | 일별 검색량 지수 (raw/normalized/pseudo_volume, 성별×연령) |
| `meta_naver_persona` | ✅ 생성 완료 | [sql/meta_naver_persona.sql](../../sql/meta_naver_persona.sql) | Persona 카테고리 정적 정보 (source_type=persona_insight) |
| `active_meta_naver_persona` | ✅ 생성 완료 | [sql/active_meta_naver_persona.sql](../../sql/active_meta_naver_persona.sql) | 일별 Persona Index (gender_pv × age_pv, 독립 가정 추정치) |
| `meta_naver_blog` | ✅ 생성 완료 | [sql/meta_naver_blog.sql](../../sql/meta_naver_blog.sql) | Naver 블로그 게시물 단위 메타 (Schema.org BlogPosting) |
| `meta_naver_blog_vec` | ✅ 생성 완료 | [sql/meta_naver_blog_vec.sql](../../sql/meta_naver_blog_vec.sql) | Naver 블로그 게시물 임베딩 (pgvector 768차원) |
| `active_meta_naver_blog` | ⚠️ 잠정 (미검증) | [sql/active_meta_naver_blog.sql](../../sql/active_meta_naver_blog.sql) | 댓글/공감 수집 가능 여부 미검증 — ADR-006 필요, 확정 전까지 수집 코드에서 미사용 |

---

## dcat_dataset — 데이터셋 생성 유형

`dcat_dataset`은 두 가지 방식으로 생성된다:

| `dataset_origin` | 생성 주체 | 생성 방식 | 예시 |
|-----------------|----------|----------|------|
| `'admin'` | 관리자 | 단일 채널/검색어/블로그 등록, 자동 수집 | YouTube 채널 1개, 뉴스 검색어 1개 |
| `'user'` | 사용자 | UI에서 직접 정의. 동일 소스 타입 내에서 복수 채널·영상·검색어 자유 조합 | YouTube: 채널 여러 개 + 개별 영상 선택 |

> **소스 타입 경계:** `dcat_dataset` 1개는 항상 단일 소스 타입(`source_type`)만 담는다.
> YouTube 영상 + 뉴스 기사를 하나의 데이터셋으로 혼합하는 것은 지원하지 않는다.

### source_type 목록

| `source_type` | 설명 | 관련 meta 테이블 |
|--------------|------|----------------|
| `video` | YouTube 영상 | meta_youtube_video |
| `news` | Naver 뉴스 기사 | meta_naver_news |
| `blog` | Naver 블로그 게시물 | meta_naver_blog |
| `shopping_insight` | Naver 쇼핑인사이트 (카테고리별 검색량, anchor+batch 호출) | meta_naver_shopping |
| `persona_insight` | Naver 쇼핑 Persona (성별/연령 독립 API 2종 호출 → persona_index) | meta_naver_persona |

---

## 테이블 관계

```
dcat_dataset (1)  ─── "무엇인가" (명세)
    │   dataset_origin: 'admin' | 'user'
    │
    ├──< dcat_provenance (N)         ─── "언제 어떻게 수집했나" (이력, 실행마다 INSERT)
    │                                     ON DELETE CASCADE
    │
    ├──  data_registry (1)           ─── "지금 어디 있고 상태는" (운영 현황, 실행마다 UPDATE)
    │                                     ON DELETE CASCADE
    │
    ├──  dcat_dataset_vec (1)        ─── "데이터셋 description 임베딩" (데이터셋 레벨 검색)
    │                                     ON DELETE CASCADE
    │
    ├──< meta_youtube_video (N)      ─── "YouTube 영상 단위 메타" (Schema.org VideoObject)
    │        UNIQUE(dataset_id, video_id)   ON DELETE CASCADE
    │        │
    │        ├──< active_meta_youtube (N)    ─── "시계열 통계 스냅샷" (dataset+영상 단위)
    │        │                                    ON DELETE CASCADE
    │        ├──  meta_youtube_video_vec (1) ─── "영상 임베딩" (영상 레벨 검색)
    │        │                                    ON DELETE CASCADE
    │        └──  meta_youtube_video_ai (1)  ─── "AI 생성 메타" (요약·키워드·개체명)
    │                                             ON DELETE CASCADE  [예정]
    │
    ├──< meta_naver_shopping (N)      ─── "쇼핑인사이트 카테고리" (source_type=shopping_insight)
    │        UNIQUE(dataset_id, category_id)   ON DELETE CASCADE
    │        │
    │        └──< active_meta_naver_shopping (N) ─── "일별 검색량 지수"
    │                                               raw/normalized/pseudo_volume × 성별×연령
    │                                               ON DELETE CASCADE
    │
    ├──< meta_naver_persona (N)       ─── "Persona 카테고리" (source_type=persona_insight)
    │        UNIQUE(dataset_id, category_id)   ON DELETE CASCADE
    │        │
    │        └──< active_meta_naver_persona (N) ─── "일별 Persona Index"
    │                                              gender_pv × age_pv (독립 가정 추정치)
    │                                              ON DELETE CASCADE
    │
    ├──< meta_naver_news (N)         ─── "Naver 뉴스 기사 단위 메타" (Schema.org NewsArticle)
    │        UNIQUE(dataset_id, article_url)   ON DELETE CASCADE
    │        │
    │        ├──< active_meta_naver_news (N)  ─── "댓글 시계열 스냅샷"
    │        │                                     is_naver_hosted=TRUE 기사만 행 존재
    │        │                                     ON DELETE CASCADE
    │        └──  meta_naver_news_vec (1)      ─── "기사 임베딩" (기사 레벨 검색)
    │                                               ON DELETE CASCADE
    │
    └──< meta_naver_blog (N)         ─── "Naver 블로그 게시물 단위 메타" (Schema.org BlogPosting)
             UNIQUE(dataset_id, post_url)   ON DELETE CASCADE
             │
             ├──< active_meta_naver_blog (N)  ─── "댓글/공감 시계열 스냅샷" [⚠️ 잠정, ADR-006 필요]
             │                                     ON DELETE CASCADE
             └──  meta_naver_blog_vec (1)      ─── "게시물 임베딩" (게시물 레벨 검색)
                                                    ON DELETE CASCADE
```

### 벡터 검색 2레벨

| 레벨 | 테이블 | 질의 예시 |
|------|--------|---------|
| 데이터셋 레벨 | `dcat_dataset_vec` | "반도체 관련 데이터셋 찾기" (소스 타입 무관) |
| 영상 레벨 | `meta_youtube_video_vec` | "HBM 공정 설명하는 영상 찾기" |
| 기사 레벨 | `meta_naver_news_vec` | "HBM4 관련 최신 기사 찾기" |
| 게시물 레벨 | `meta_naver_blog_vec` | "HBM 반도체 후기 블로그 찾기" |

### active_meta 설계 포인트

같은 영상(video_id)이 Dataset A, Dataset B에 동시에 포함될 수 있다.
`active_meta_youtube`는 `meta_youtube_video.id` (= dataset+video 조합)를 기준으로 추적하므로
각 데이터셋이 독립적인 수집 타임라인과 delta를 갖는다.

```
예시: video_id=abc123 이 두 데이터셋에 포함

meta_youtube_video
  id=1  dataset_id=samsung_ch      video_id=abc123
  id=2  dataset_id=hbm_collection  video_id=abc123

active_meta_youtube
  meta_id=1  collected_at=07-07 월  view_count=10,000  delta=NULL   ← Dataset A 첫 수집
  meta_id=2  collected_at=07-09 수  view_count=10,500  delta=NULL   ← Dataset B 첫 수집 (독립 시작)
  meta_id=1  collected_at=07-14 월  view_count=12,000  delta=+2,000 ← Dataset A 기준 정확한 delta
  meta_id=2  collected_at=07-16 수  view_count=12,800  delta=+2,300 ← Dataset B 기준 정확한 delta
```

---

## AI 메타데이터 파이프라인 (예정)

트랜스크립트 기반 AI 생성 메타데이터. 수집 코드 완성 후 성능 테스트를 거쳐 도입.

### 처리 흐름

```
트랜스크립트 (youtube-transcript-api)
    ↓ 전처리 (타임스탬프 제거, 줄 합치기)
    ↓
Groq API (무료, llama-3.1-8b / gemma2-9b)
    ↓
meta_youtube_video_ai INSERT
```

### 추출 필드 (확정 예정)

| 필드 | 설명 | 입력 소스 |
|------|------|----------|
| `ai_summary` | 3문장 이내 요약 | 트랜스크립트 |
| `ai_keywords` | 핵심 키워드 배열 | 트랜스크립트 |
| `ai_entities` | 등장 기관·인물·제품명 (JSONB) | 트랜스크립트 |
| `ai_content_type` | tutorial / review / presentation / interview / news | 트랜스크립트 |
| `ai_key_points` | 핵심 포인트 bullet 배열 | 트랜스크립트 |

### 인프라 결정 사항

| 항목 | 결정 |
|------|------|
| 처리 방식 | Groq 무료 API (HTTP 호출) |
| 이유 | 서버(RnD-analyzer01) GPU 없음 — 로컬 LLM 실용 불가 |
| NER 전용 모델 미사용 이유 | Product 타입 없음, STT 노이즈에 취약 → LLM이 더 적합 |
| 트랜스크립트 없는 영상 | title + description으로 fallback, ai 테이블 row 없을 수 있음 |

---

## 뷰 (Views)

| 뷰 이름 | DDL | 설명 |
|---------|-----|------|
| `v_meta_youtube_latest` | [sql/views.sql](../../sql/views.sql) | meta_youtube_video + active_meta_youtube 최신 row 결합. 영상별 현재 통계(최신 수집값 + 전회차 증감)를 한 번에 조회 |
| `v_meta_naver_news_latest` | [sql/views.sql](../../sql/views.sql) | meta_naver_news + active_meta_naver_news 최신 row 결합. 기사별 댓글 통계(최신 수집값 + 전회차 증감)를 한 번에 조회. 외부 기사 댓글 컬럼 NULL |

---

## DDL 적용 순서

전체 재구성 시 아래 순서로 실행 (`dcat_dataset.sql`이 CASCADE로 자식 테이블을 먼저 삭제함):

```bash
# 1. 핵심 테이블 생성 (부모 → 자식 순서)
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/dcat_dataset.sql \
  -f sql/dcat_provenance.sql \
  -f sql/data_registry.sql \
  -f sql/dcat_dataset_vec.sql

# 2. YouTube 메타 테이블 생성
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/meta_youtube_video.sql \
  -f sql/active_meta_youtube.sql \
  -f sql/meta_youtube_video_vec.sql

# 3. Naver 뉴스 메타 테이블 생성
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/meta_naver_news.sql \
  -f sql/meta_naver_news_vec.sql \
  -f sql/active_meta_naver_news.sql

# 4. Naver 쇼핑·Persona 메타 테이블 생성
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/meta_naver_shopping.sql \
  -f sql/active_meta_naver_shopping.sql \
  -f sql/meta_naver_persona.sql \
  -f sql/active_meta_naver_persona.sql

# 5. Naver 블로그 메타 테이블 생성 (active_meta_naver_blog는 ADR-006 확정 전까지 미사용)
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/meta_naver_blog.sql \
  -f sql/meta_naver_blog_vec.sql \
  -f sql/active_meta_naver_blog.sql

# 6. 샘플 데이터 삽입 (개발용)
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/seeds.sql

# 7. 뷰 생성
psql -h localhost -p 30433 -U admin -d datagokr \
  -f sql/views.sql

# 8. 임베딩 생성
python scripts/embed_datasets.py         # dcat_dataset_vec
python scripts/embed_youtube_videos.py   # meta_youtube_video_vec
python scripts/embed_naver_news.py       # meta_naver_news_vec
# meta_naver_blog_vec용 임베딩 스크립트는 아직 미작성 (embed_naver_news.py 참고해 추가 필요)
```

---

## 미결정 사항 (2026-07-22 기준)

기본 데이터 설계(dcat_dataset → meta → active_meta → _vec, YouTube/뉴스/쇼핑/Persona/블로그)의
스키마 레벨은 완성됐다 (item_count 도입, source_type/description NOT NULL 포함). 남은 것은
아래 항목들이다.

### 스키마·API 확정 필요

| 항목 | 상태 | 내용 |
|------|------|------|
| `active_meta_naver_blog` 컬럼 확정 | ⚠️ 잠정 | 댓글/공감/조회수 수집 가능 여부 미검증. ADR-005(뉴스)와 동일한 방식의 실제 API 테스트 필요 → ADR-006 (아직 미작성) |
| `meta_naver_blog` 소스 구분 | ⚠️ 확인 필요 | Naver 블로그 검색 API가 blog.naver.com 외 타 플랫폼도 반환하는지 확인 후, 필요 시 news의 `is_naver_hosted`처럼 플랫폼 구분 컬럼 추가 여부 결정 |
| `dcat_dataset.publisher` NOT NULL 여부 | ⚠️ 보류 중 | description/source_type NOT NULL 결정 시 같이 검토하다가 범위 밖이라 보류. title/description과 같은 급의 핵심 속성이라 후보임 |
| `meta_youtube_video_ai` | ⏳ 예정 | 필드는 초안 있음(§AI 메타데이터 파이프라인), DDL 미작성. P03 연구 주제와 직결 |
| `meta_naver_news_ai` / `meta_naver_blog_ai` | ⏳ 미설계 | 필드 초안조차 없음 |

### 임베딩 파이프라인 격차

- `meta_naver_blog_vec`용 `embed_naver_blog.py` 스크립트 없음 (dcat_dataset/youtube/news 3개는 완성·검증됨) — `embed_naver_news.py` 패턴 그대로 이식하면 됨
- `meta_naver_blog` 시드 데이터는 있지만(3건), 실제 서버에 반영 전이라 아직 임베딩 생성 대상이 없음

### 수집 코드 (전부 미작성 — `src/` 비어있음)

`meta_naver_shopping`/`meta_naver_persona`/`meta_naver_blog`도 다른 소스와 마찬가지로
스키마만 있고 실제 API 호출 수집 코드는 없다. 레거시 코드(`3amd/naver_shopping_insight.py`,
`3amd/naver_persona.py`)를 `src/collectors/`로 이식하는 작업이 필요하다.

### 실제 DB 반영 여부 — 아직 미반영

`meta_naver_shopping.sql`/`meta_naver_persona.sql`/블로그 3개 테이블/`dcat_dataset.sql`/
`data_registry.sql` 전부 문법·제약조건은 롤백 트랜잭션으로 여러 차례 검증했지만, 실제
서버 DB에는 한 번도 반영하지 않았다. `dcat_dataset.sql`은 `DROP TABLE ... CASCADE`로
전체 자식 테이블(dcat_provenance, data_registry, dcat_dataset_vec, meta_*, active_meta_*
전부)이 함께 삭제되므로, 재적용 시 순서는:

```
1. DDL 17개 파일 순서대로 재실행 (docs/database/datagokr_schema.md "DDL 적용 순서" 참조)
2. sql/seeds.sql 재실행
3. 임베딩 스크립트 재실행: embed_datasets.py, embed_youtube_videos.py, embed_naver_news.py
   (embed_naver_blog.py는 아직 없음 — 있으면 같이 실행)
```

---

*ERD는 주요 테이블 완성 후 추가.*
