# 06. Object Storage Format Spec — 원본·JSON-LD 저장 형식

> 목적: 메타데이터 수집 플랫폼이 **수집한 원본 데이터**와 **JSON-LD 배포본**을 오브젝트 스토리지에 어떤 **경로·형식**으로 저장하는지 정의한다. (테이블 정의서와 별도의 저장소 산출물 명세 — **현행 구현 기준 확정 명세**)
> 기준: 현재 구현 소스(`src/storage/`). 설계 의도·결정 근거는 [05_Object_Storage_Export.md](05_Object_Storage_Export.md) 참조.
> ※ 스토리지 접속 주소·자격증명 등 내부망 접속정보는 본 문서에서 제외하며 별도 공유한다.

---

## 1. 저장소 개요

| 항목 | 내용 |
|---|---|
| 스토리지 | SeaweedFS (S3 호환 오브젝트 스토리지) |
| 접근 방식 | S3 API (boto3, path-style addressing, signature v4) |
| 버킷 | `metadata-ingestion` |
| 리전 | `us-east-1` (S3 호환 규약상 형식값) |
| 접속 주소·키 | 환경변수(`S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`)로 주입 — **본 문서 비포함** |
| 최상위 구성 | `raw/` (원본) · `jsonld/` (JSON-LD 배포본) 두 prefix |

### 쓰기 정책
- **최신 상태 덮어쓰기**: 수집 주기마다 동일 키(경로)를 다시 써서 덮어쓴다. `raw/.../YYYY/MM/DD/...` 식 **날짜별 스냅샷 누적은 하지 않는다.**
- **JSON-LD는 전체 재생성**: 데이터셋의 "현재 DB 전체 상태"를 매 수집마다 다시 읽어 JSON-LD 1개 파일을 통째로 재생성·업로드한다.
- 업로드 모듈(`s3_client`)은 실패 시 **예외를 전파**한다(무음 처리하지 않음). 수집 자체의 실패 처리 여부는 호출부(파이프라인)가 결정한다.

---

## 2. 디렉토리 구조

```
metadata-ingestion/                         ← SeaweedFS 버킷
├── raw/                                     ← 원본 데이터
│   └── {source_type}/
│       └── {dataset_id}/
│           ├── {item_key}.json | .txt       ← 아이템당 1개 (발견형: video/news/blog)
│           └── {dataset_id}.csv             ← 선언형(shopping_insight/persona_insight), 데이터셋당 1개
└── jsonld/                                  ← JSON-LD 배포본
    └── {source_type}/
        └── {dataset_id}/
            └── {dataset_id}.jsonld          ← 모든 source_type 공통, 데이터셋당 1개
```

- `{source_type}`: `video`, `news`, `blog`, `shopping_insight`, `persona_insight`
- `{dataset_id}`: 데이터셋 식별자(테이블 정의서의 `dataset_id`와 동일)
- 저장 후 `data_registry` 테이블의 `s3_raw_prefix`(`raw/{source_type}/{dataset_id}/`), `s3_jsonld_prefix`(`jsonld/{source_type}/{dataset_id}/`) 컬럼에 prefix를 기록한다.

---

## 3. 원본(Raw) 저장 — 소스 타입별

| source_type | 경로 | 형식 | 내용 | 비고 |
|---|---|---|---|---|
| **video** | `raw/video/{dataset_id}/{video_id}.json` | JSON | STT(자막) 세그먼트 | `video_id`=유튜브 영상 ID. 자막 보유(`has_transcript`) 시에만 |
| **news** | `raw/news/{dataset_id}/{item_id}.txt` | 텍스트 | 기사 본문 | `item_id`=`meta_news` PK. 본문 보유 시에만 |
| **blog** | `raw/blog/{dataset_id}/{item_id}.txt` | 텍스트 | 블로그 본문 | `item_id`=`meta_blog` PK |
| **shopping_insight** | `raw/shopping_insight/{dataset_id}/{dataset_id}.csv` | CSV | 전체 시계열 지표 | 매 수집마다 전체 덮어쓰기. 시계열의 **정본** |
| **persona_insight** | `raw/persona_insight/{dataset_id}/{dataset_id}.csv` | CSV | 전체 시계열 지표 | 상동 |

### 3.1 video 원본 JSON 스키마
```json
{
  "video_id": "dQw4w9WgXcQ",
  "language": "ko",
  "segments": [
    { "start": 0.0, "end": 3.2, "text": "..." }
  ],
  "full_text": "전체 텍스트 ..."
}
```
- `language`: STT(Whisper)가 감지한 실제 언어(고정값 아님).
- 세그먼트별 타임스탬프를 포함하므로 `.txt`가 아닌 `.json`으로 저장.

### 3.2 news / blog 원본 TXT
- 스크래핑한 **본문 텍스트 원문 그대로** (세그먼트 개념 없음) → 평문 `.txt`.

### 3.3 shopping / persona 원본 CSV
- 헤더 + 데이터행(`csv.DictWriter`). 행이 없으면 **헤더만 있는 빈 CSV**를 쓴다.
- 전체 시계열은 CSV가 정본이고, JSON-LD에는 최신 스냅샷 + CSV 참조만 넣어 **중복 저장을 피한다.**

---

## 4. JSON-LD 배포본

- 경로: `jsonld/{source_type}/{dataset_id}/{dataset_id}.jsonld`
- **데이터셋 1개당 JSON-LD 파일 1개.** 데이터셋 레벨 정보 + 아이템 배열(`mi:items`)을 함께 담는다.
- 표준: DCAT(데이터셋), Schema.org(아이템), Dublin Core Terms(기술 속성), 내부 네임스페이스(`mi:`)로 능동형(active) 메타데이터 표현.

### 4.1 @context
```json
{
  "dct":    "http://purl.org/dc/terms/",
  "dcat":   "http://www.w3.org/ns/dcat#",
  "schema": "https://schema.org/",
  "mi":     "https://metadata-ingestion.internal/ns#"
}
```

### 4.2 데이터셋 레벨 (공통)
```json
{
  "@context": { "...": "..." },
  "@id": "mi:dataset/{dataset_id}",
  "@type": "dcat:Dataset",
  "dct:identifier": "{dataset_id}",
  "dct:title": "...",
  "dct:description": "...",
  "dct:publisher": "...",
  "dct:license": "...",
  "dct:accrualPeriodicity": "...",
  "dcat:keyword": ["..."],
  "mi:temporalStart": "2026-01-01T00:00:00",
  "mi:temporalEnd": "2026-06-30T00:00:00",
  "mi:activeMetadata": {
    "status": "...", "itemCount": 0, "rowCount": 0,
    "lastCollectedAt": "...", "nextCollectAt": "..."
  },
  "mi:items": [ ... ]
}
```

### 4.3 아이템(`mi:items`) — source_type별 @type

| source_type | 아이템 `@type` | 본문/원본 참조 필드 |
|---|---|---|
| video | `schema:VideoObject` | `mi:transcriptRef` → `raw/video/{dataset_id}/{video_id}.json` |
| news | `schema:NewsArticle` | `mi:contentRef` → `raw/news/{dataset_id}/{id}.txt` |
| blog | `schema:BlogPosting` | `mi:contentRef` → `raw/blog/{dataset_id}/{id}.txt` |
| shopping_insight | 카테고리 정의 + 최신 스냅샷 | `mi:timeSeriesRef` → `raw/shopping_insight/{dataset_id}/{dataset_id}.csv` |
| persona_insight | 카테고리 정의 + 최신 스냅샷 | `mi:timeSeriesRef` → `raw/persona_insight/{dataset_id}/{dataset_id}.csv` |

> JSON-LD의 참조 필드(`mi:transcriptRef`/`mi:contentRef`/`mi:timeSeriesRef`)는 모두 **버킷 내 raw 원본 경로(상대 키)**를 가리킨다. 즉 JSON-LD만 열어도 어떤 원본 파일을 참조하는지 추적 가능하다.

### 4.4 video 아이템 예시
```json
{
  "@type": "schema:VideoObject",
  "@id": "https://youtube.com/watch?v={video_id}",
  "schema:identifier": "{video_id}",
  "schema:name": "제목",
  "schema:description": "설명",
  "schema:uploadDate": "2026-02-10T09:00:00",
  "schema:author": {
    "@type": "schema:Organization",
    "schema:name": "채널명",
    "schema:identifier": "{channel_id}"
  },
  "schema:keywords": ["태그1", "태그2"],
  "mi:isRemoved": false,
  "mi:activeMetadata": [
    { "collectedAt": "2026-02-10T09:00:00",
      "viewCount": 1000, "likeCount": 50, "commentCount": 5,
      "deltaViews": 100, "deltaLikes": 5, "deltaComments": 1 }
  ],
  "mi:transcriptRef": "raw/video/{dataset_id}/{video_id}.json"
}
```
- `mi:activeMetadata`(아이템 레벨): 수집 시점별 지표 **시계열**(조회/좋아요/댓글 수 + 증분 delta).
- `mi:isRemoved`: 원본 삭제 여부 플래그.

---

## 5. 파일 형식 · 인코딩 규약

| 확장자 | ContentType | 인코딩/옵션 |
|---|---|---|
| `.json` / `.jsonld` | `application/json; charset=utf-8` | UTF-8, `ensure_ascii=false`, `indent=2` (한글 원문 보존, 가독형) |
| `.txt` | `text/plain; charset=utf-8` | UTF-8 |
| `.csv` | `text/plain; charset=utf-8` | UTF-8, 헤더 + 행 |

---

## 6. 설계 근거(참고)
- 이중 저장: **raw**는 원본 보존(타 시스템 이관 용이), **JSON-LD**는 DCAT 표준 배포본(카탈로그 상호운용성).
- 상세 설계·결정 근거: [05_Object_Storage_Export.md](05_Object_Storage_Export.md)
- 저장소 전략(ADR): [../adr/004_ObjectStorage_Strategy.md](../adr/004_ObjectStorage_Strategy.md)
- 인프라(배포·버킷·자격증명): [../infrastructure/04_ObjectStorage.md](../infrastructure/04_ObjectStorage.md)

---

## 7. (예정) 정형데이터 저장소

> **상태: 예정 — 미구현.** 아래는 방향성 기록이며, 세부 경로·네이밍·형식은 확정 후 본 절을 갱신한다.

- **대상**: 공공데이터포털(data.go.kr) 등에서 수집하는 **정형 데이터(엑셀·CSV 등 파일 기반)** 의 원본 저장 구획.
- **필요성**: 현재 `raw/`·`jsonld/` 구조는 영상·뉴스·블로그·인사이트 등 발견형/선언형 소스 중심으로, 정형 파일 원본을 담을 전용 경로가 없다.
- **방향(초안)**:
  - 기존 패턴을 그대로 확장 — 정형 원본을 `raw/structured/{dataset_id}/...` (가칭)에 보관하고, 데이터셋 단위로 JSON-LD/카탈로그를 연계.
  - 파일 형식·인코딩 규약(§5), 덮어쓰기/재생성 정책(§1), `data_registry.s3_raw_prefix`/`s3_jsonld_prefix` 기록 규칙을 **정형에도 동일 적용**하는 방향 검토.
- **연계 설계**: 정형 데이터의 지표·메타 구조(`active_meta_dataset`/`active_meta_file` 등)는 와이즈넛 정형 저장 설계와 함께 확정한다. (로드맵: `docs/NEXT_STEPS.md` §7)

---

*본 문서는 현재 구현 기준이며, 수집 소스·스키마 변경 시 함께 갱신한다.*
