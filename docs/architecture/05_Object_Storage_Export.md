# 05. SeaweedFS Raw/JSON-LD Export — 설계 초안

> **Last Updated:** 2026-07-27
> **Status:** 설계 초안 (구현 전) — 이 문서 안의 세부 항목(파일명 규칙, JSON-LD 스키마 등)은
> 사용자와 계속 논의하며 확정해나간다. 확정된 항목은 아래 각 절에 "(확정)"으로 표시.

인프라(SeaweedFS 배포, 버킷, 자격증명)는 [infrastructure/04_ObjectStorage.md](../infrastructure/04_ObjectStorage.md)
참조. 이 문서는 **그 인프라 위에 실제로 무엇을, 언제, 어떤 형태로 쓰는지**를 다룬다.
지금까지는 인프라만 있고 이 흐름을 실행하는 코드가 전혀 없었다 — `boto3` 의존성도,
S3 클라이언트 모듈도, 파이프라인 안의 쓰기 호출도 전부 미작성.

---

## 1. 왜 필요한가

PostgreSQL은 구조화된 메타데이터(DCAT/시계열)를 담기엔 적합하지만, (a) 아이템 원문
콘텐츠를 DB 밖에 파일로도 보존해두면 재처리(재임베딩, 다른 파이프라인 재사용)나
이관이 쉬워지고, (b) DCAT 표준을 따르는 JSON-LD 배포본은 카탈로그 상호운용성
(외부 데이터 포털 연동, 표준 크롤러 수집 등)을 위해 별도로 필요하다. `data_registry.
s3_raw_prefix`/`s3_jsonld_prefix` 컬럼은 이미 스키마에 있었지만 (2026-07-03 시점) 어느
파이프라인도 채운 적이 없다.

---

## 2. 저장 단위 (확정)

데이터셋(`dcat_dataset.dataset_id`) 1개 = 폴더 1개. 그 안의 형태는 소스 타입에 따라 다르다.

| source_type | 폴더 안 구성 |
|---|---|
| `video` | 영상별 스크립트(자막/트랜스크립트) 파일, 아이템당 1개 |
| `news` | 기사별 본문 파일, 아이템당 1개 |
| `blog` | 게시물별 본문 파일, 아이템당 1개 |
| `shopping_insight` | 데이터셋 전체 시계열을 담은 CSV/Excel 파일 1개 |
| `persona_insight` | 데이터셋 전체 시계열을 담은 CSV/Excel 파일 1개 |

**최신 상태로 덮어쓰기(확정)** — 수집 주기마다 파일을 다시 쓰면 같은 경로를 덮어쓴다.
`raw/{source_type}/{dataset_id}/YYYY/MM/DD/...` 식의 날짜별 스냅샷 누적은 하지 않는다
(기존 `infrastructure/04_ObjectStorage.md`에 있던 초기 초안 방식 — 이번 결정으로
대체됨, §6에서 그 문서도 갱신).

### 2.1 디렉토리 구조 (초안)

```
metadata-ingestion/                              ← SeaweedFS bucket
├── raw/
│   └── {source_type}/
│       └── {dataset_id}/
│           ├── {item_key}.json/.txt    ← video는 세그먼트 JSON(§4.5), news/blog는 본문 txt, 아이템당 1개
│           └── {dataset_id}.csv        ← shopping_insight/persona_insight, 1개뿐
└── jsonld/
    └── {source_type}/
        └── {dataset_id}/
            └── {dataset_id}.jsonld     ← 모든 source_type 공통, 1개뿐
```

**`{item_key}` (확정, 2026-07-27)**:
- `video`: `{video_id}` — YouTube 영상 ID 자체가 이미 사람이 알아볼 수 있는 안정적
  식별자라 그대로 사용 (예: `dQw4w9WgXcQ.json` — §4.5 확정에 따라 세그먼트 JSON이라 `.json`)
- `news`/`blog`: 플랫폼마다 안정적인 사람이 읽는 ID가 항상 있는 게 아님 (`is_naver_hosted`/
  `platform='naver'`가 아니면 `naver_oid`/`blog_id`+`log_no`가 없음) → 각
  `meta_naver_news.id`/`meta_naver_blog.id`(내부 PK, BIGSERIAL)를 파일명으로 사용.
  데이터셋 폴더 안에서 유일함이 보장되고 절대 안 바뀜. 사람이 보기엔 의미 없는 숫자지만,
  폴더가 이미 `{source_type}/{dataset_id}/`로 스코프돼 있어 문제 없다고 판단
- `has_content=FALSE`(본문 스크래핑 실패) 아이템, 트랜스크립트 없는 영상은 raw 파일
  자체를 안 만듦(빈 파일 대신 생략)

---

## 3. JSON-LD 범위 (확정된 방향 + 스키마 초안)

**확정**: 데이터셋 1개당 JSON-LD 파일 1개. 안에는 (a) `dcat_dataset` 레벨 정보,
(b) 아이템 레벨 메타데이터, (c) active metadata(시계열)를 모두 포함.

### 3.1 공통 골격

```jsonc
{
  "@context": {
    "dct": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "schema": "https://schema.org/",
    "mi": "https://metadata-ingestion.internal/ns#"   // 표준에 없는 확장 속성용 임시 네임스페이스
  },
  "@id": "mi:dataset/{dataset_id}",
  "@type": "dcat:Dataset",
  "dct:identifier": "{dataset_id}",
  "dct:title": "...",
  "dct:description": "...",
  "dct:publisher": "...",
  "dct:license": "...",
  "dct:accrualPeriodicity": "...",
  "dcat:keyword": ["..."],
  "mi:temporalStart": "2026-01-01",
  "mi:temporalEnd": null,
  "mi:activeMetadata": {
    "status": "active",
    "itemCount": 1434,
    "rowCount": 28680,
    "lastCollectedAt": "2026-07-27T02:00:00+09:00",
    "nextCollectAt": "2026-07-28T02:00:00+09:00"
  },
  "mi:items": [ /* §3.2 또는 §3.3 */ ]
}
```

`mi:activeMetadata`는 `data_registry`를 그대로 반영 — "지금 이 데이터셋 운영 상태"를
JSON-LD를 열어보는 것만으로 확인 가능하게 하는 목적(사용자가 원한 "active metadata
포함" 요구를 데이터셋 레벨에서 충족).

### 3.2 발견형 (video/news/blog) — 아이템 = 개별 콘텐츠

```jsonc
// video
{
  "@type": "schema:VideoObject",
  "@id": "https://youtube.com/watch?v={video_id}",
  "schema:identifier": "{video_id}",
  "schema:name": "...",
  "schema:description": "...",
  "schema:uploadDate": "...",
  "schema:duration": "PT12M34S",
  "schema:author": {"@type": "schema:Organization", "schema:name": "...", "schema:identifier": "{channel_id}"},
  "schema:keywords": ["..."],
  "mi:isRemoved": false,
  "mi:transcriptRef": "raw/video/{dataset_id}/{video_id}.json",   // §4.5 참조, 없으면 필드 생략
  "mi:activeMetadata": [
    {"collectedAt": "...", "viewCount": 12345, "likeCount": 200, "commentCount": 30, "deltaViews": 50}
    // active_meta_youtube 전체 이력 — 개당 스냅샷 수가 보통 적어(수집 주기만큼) inline 유지
  ]
}

// news
{
  "@type": "schema:NewsArticle",
  "@id": "{article_url}",
  "schema:headline": "...",
  "schema:abstract": "...",
  "schema:publisher": "...",
  "schema:datePublished": "...",
  "mi:searchKeyword": "...",
  "mi:isRemoved": false,
  "mi:contentRef": "raw/news/{dataset_id}/{id}.txt",   // has_content=TRUE일 때만
  "mi:activeMetadata": [
    {"collectedAt": "...", "commentCount": 12, "exposeCount": 10, "replyCount": 2}
    // is_naver_hosted=TRUE인 기사만 값 있음 — 아니면 빈 배열
  ]
}

// blog — news와 동일 골격, schema:BlogPosting + reactionCount/reactionBreakdown
```

### 3.3 선언형 (shopping_insight/persona_insight) — 아이템 = 카테고리 (확정, 2026-07-27)

시계열 포인트 수가 발견형과 비교가 안 될 만큼 크다(카테고리 1개 × 12조합 × 누적
일수 — 1년이면 카테고리당 4,380포인트). **확정: 전체 inline 대신 참조 방식** — CSV가
이미 전체 시계열의 정본이므로, JSON-LD엔 카테고리 정의 + 최신 스냅샷 + CSV 참조만
넣는다. 같은 데이터를 JSON-LD와 CSV 두 파일에 중복 저장하지 않고, 매 수집마다
JSON-LD 전체를 다시 쓰는 비용도 줄인다 (CSV만 전체 갱신, JSON-LD는 최신 스냅샷만
갱신):

```jsonc
{
  "@type": "mi:Category",     // schema.org에 대응 타입 없음 — 자체 확장
  "mi:categoryId": "50000148",
  "mi:categoryName": "식품>음료",
  "mi:isAnchor": true,          // shopping만, persona는 필드 생략
  "mi:timeSeriesRef": "raw/shopping_insight/{dataset_id}/{dataset_id}.csv",
  "mi:timeSeriesSummary": {"periodStart": "2025-07-27", "periodEnd": "2026-07-26", "pointCount": 4380},
  "mi:latestSnapshot": [
    {"period": "2026-07-26", "gender": "f", "age": "30", "pseudoVolume": 118.4, "scaleFactor": 1.13}
    // 가장 최근 period의 12조합(shopping) / 12조합(persona) 전부
  ]
}
```

---

## 4. YouTube 트랜스크립트 수집 (확정: 자체 STT, 2026-07-27)

지금 YouTube 콜렉터는 메타데이터(제목/설명/통계)만 가져오고 자막/트랜스크립트는
전혀 안 가져온다. §2의 raw 저장 설계가 성립하려면 이걸 새로 만들어야 한다.

### 4.1 레거시 방식이 왜 차단당했는지

레거시 `youtube_transcript_extractor.py`는 `yt-dlp`가 아니라 **`youtube-transcript-api`**
라이브러리를 쓴다 — YouTube의 비공식 `timedtext`/`get_transcript` 내부 엔드포인트를
브라우저 없이 순수 HTTP 요청으로 직접 긁는 방식이다. 요청 간 랜덤 딜레이(1~3초) +
20건마다 5분 휴식까지 넣었는데도 40개 만에 차단당한 이유는, 이게 **요청 빈도가 아니라
발신 IP 자체의 평판(클라우드/데이터센터 ASN)을 보고 차단하는 방식**이기 때문 —
얼마나 천천히 요청하든 근본 원인이 안 없어진다.

### 4.2 yt-dlp는 다른 방식인가

다르다. `youtube-transcript-api`가 timedtext 엔드포인트를 최소한의 헤더로 직접 찌르는
것과 달리, `yt-dlp`는 실제 플레이어가 쓰는 innertube API 흐름(클라이언트 컨텍스트,
플레이어 응답 파싱 등)을 흉내 내고 업데이트도 훨씬 빈번해서 상대적으로 더 오래
버틴다는 보고가 많다. 다만 **결국 같은 계열의 비공식 엔드포인트를 쓰는 건 동일**해서
"완전히 다른 방식"은 아니고 "더 견고하게 구현된 같은 방식"에 가깝다 — 이번엔
레거시와 완전히 다른 경로를 원하시므로 1차 후보에서 제외.

### 4.3 무료 대안 비교

| 방식 | 비용 | 비고 |
|---|---|---|
| yt-dlp 자막 다운로드 | 레거시와 유사 계열(§4.2) | **제외** — "레거시와 다른 방식" 조건에 안 맞음 |
| 프록시 구매 + 기존 라이브러리 | 유료 | **제외** — 무료 조건에 안 맞음 |
| 유료 서드파티 트랜스크립트 API | 유료 | **제외** |
| YouTube Data API v3 `captions.download`(공식) | 무료, 공식 | **제외** — 본인 소유 채널만 가능(OAuth), 임의 채널 대상인 우리 콜렉터엔 구조적으로 안 맞음 |
| **자체 STT (오디오 다운로드 + Whisper 등 로컬 전사)** | 무료(자체 서버 연산만 사용) | **채택** |

### 4.4 채택: 자체 STT

`yt-dlp`로 **오디오만** 다운로드(`-x --audio-format mp3` 등 — 이건 자막 스크래핑이
아니라 일반적인 영상/오디오 다운로드 기능이라 timedtext류 엔드포인트를 전혀 안 거침,
차단 사례가 훨씬 적음) → 로컬(수집 코드가 실제로 돌아가는 서버)에서 **Whisper 계열
오픈소스 모델**로 STT 돌려서 텍스트화. YouTube의 자막 제공 여부와 완전히 무관해지므로
(자막 없는 영상도 가능) 이번 차단 문제의 근본 원인 자체를 비켜간다.

**서버 스펙 확인 결과 (2026-07-27, `RnD-analyzer01`, Rocky Linux 9)**: Intel Xeon(Skylake)
CPU **8코어**, GPU 없음(`nvidia-smi` 미설치), RAM 31Gi(19Gi 여유), `/DATA` 488G
여유(모델 가중치+임시 오디오 파일 저장에 충분), **`ffmpeg` 설치 완료** — base/EPEL엔
없어서(라이선스 정책상 제외) CRB 저장소 활성화(`sudo /usr/bin/crb enable`) +
RPM Fusion Free 저장소 추가 후 `ffmpeg-5.1.10` 설치 성공(106개 패키지 포함).

**모델 선택 (확정): `faster-whisper`, `small` 모델, INT8 양자화, CPU 추론.**
GPU가 없으므로 CTranslate2 기반 `faster-whisper`가 원본 `openai-whisper`보다 CPU에서
훨씬 빠르고, INT8 양자화로 메모리·속도를 더 아낄 수 있다. `small`(다국어, 가중치
~500MB)로 시작 — 한국어 정확도가 부족하면 `medium`(~3GB, RAM은 31Gi로 충분히 감당)으로
올리는 걸 다음 단계로 열어둔다. GPU가 없는 만큼 `medium`/`large`는 처리 시간이
크게 늘어 처음부터 쓰기엔 부담.

**처리 전략**: §6 임베딩과 같은 원칙으로 **"전체 재계산"이 아니라 "신규 발견 영상만
증분 처리"** 패턴을 적용한다 — §5 결정대로 `run()`이 신규 영상을 발견하는 그 시점에
STT까지 같이 돌리면, 이 기능이 배포된 이후엔 매 수집 주기마다 그날 새로 올라온
영상 몇 개만 처리하면 되므로 "배치 크기" 자체가 문제되지 않는다.

문제는 **기존에 이미 쌓여있던 백로그**(현재 YouTube 데이터셋 2개, 약 2,000개
영상 — 이 기능 배포 전에 수집된 것들이라 트랜스크립트가 없음)다. `run()`과 별개로
`scripts/backfill_youtube_transcripts.py`(§7.4)로 처리한다.

**실측 완료 (2026-07-28, `RnD-analyzer01` 실 서버, `--limit 5`)**:

| video_id | 길이 | 처리시간 | 배속 |
|---|---|---|---|
| ISW41OTHlhc | 92s | 45.6s | 0.50x (이번 프로세스의 첫 처리 — Whisper 모델 최초 로딩 시간이 섞여 실제보다 느리게 나옴) |
| 9PTRQjP6yAQ | 187s | 51.5s | 0.28x |
| z7AofehqASc | 122s | 22.4s | 0.18x |
| pxaU6Iwezc0 | 86s | 17.2s | 0.20x (세그먼트 0개 — 발화가 거의 없는 영상으로 추정) |

모델 로딩이 끝난 뒤(2~4번째)는 **영상 길이의 약 0.2~0.3배** 시간이 걸린다 — 개발 중
로컬 머신(Apple Silicon)에서 쟀던 것과 비슷한 수준이라 서버 간 편차는 크지 않은
것으로 보인다. 이 수치로 역산하면 평균 3~5분(180~300초)짜리 영상 기준 개당 40~90초,
백로그 2,000개 전체는 **순수 연산으로만 대략 25~50시간** — 하루 이틀에 끝낼 작업이
아니라 여러 날에 걸쳐 나눠 돌리는 걸 전제로 한다.

**실전 팁**: `WhisperModel`은 프로세스당 1회만 로딩되므로(§7.2 지연 초기화), `--limit 5`를
여러 번 나눠 돌리는 것보다 `--limit 100`처럼 한 번에 크게 돌리는 게 모델 재로딩 비용을
줄여 더 효율적이다. 정기 수집(§5 `run()`)과 백로그 스크립트가 동시에 도는 상황을
대비해 `cpu_threads=6`(8코어 중 2개 여유, §7.2)으로 이미 제한해뒀다.

### 4.5 raw 파일 포맷 (확정: 세그먼트 JSON, 2026-07-27)

순수 텍스트(.txt)가 아니라 **세그먼트별 타임스탬프를 포함한 JSON**으로 저장한다.
Whisper 계열 모델은 애초에 "구간(segment) + 시작·끝 시각 + 그 구간 텍스트" 형태로
결과를 낸다 — 순수 텍스트로만 저장하면 모델이 공짜로 계산해준 타임스탬프를 일부러
버리는 셈이고, 파일 용량 차이도 미미해서 버릴 이유가 없다고 판단. 타임스탬프가 있으면
나중에 "특정 발언이 몇 분 몇 초에 나왔는지" 검색, AI 요약 파이프라인(§5, `NEXT_STEPS.md`
4번)의 구간별 챕터 요약에 바로 활용 가능 — 없으면 그때 가서 STT를 다시 돌려야 한다.

```jsonc
// raw/video/{dataset_id}/{video_id}.json
{
  "video_id": "dQw4w9WgXcQ",
  "language": "ko",
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "안녕하세요 오늘은 반도체 HBM에 대해서 알아보겠습니다."},
    {"start": 4.2, "end": 9.8, "text": "최근 삼성전자가 HBM4 양산을 발표했는데요."}
  ],
  "full_text": "안녕하세요 오늘은 반도체 HBM에 대해서 알아보겠습니다. 최근 삼성전자가 HBM4 양산을 발표했는데요."
  // full_text 동봉 — 텍스트만 필요한 소비자는 segments 재조합 없이 바로 사용
}
```

이에 따라 §2.1의 `{item_key}` 확장자도 video만 `.json`으로 정정 (news/blog는
스크래핑한 본문 그대로라 `.txt` 유지 — 세그먼트 개념이 없음), §3.2의
`mi:transcriptRef`가 가리키는 파일도 `.json`으로 갱신.

### 4.6 백로그 이후 운영 방식 — Airflow 연결 시 반영 필요 (2026-07-28, 사용자 확인)

YouTube 영상 규모 자체가 크지 않을 것으로 예상돼(현재 데이터셋 2개, ~2,000개), §4.4
방식대로 `--limit`을 키워가며 며칠(보통 수집 갱신 주기인 1주일 이내)에 걸쳐 돌리면
백로그가 끝난다. **일단 백로그가 소진된 뒤에는 별도 배치 처리가 필요 없다** —
§5에서 이미 확정한 대로 `run()`이 신규 영상을 발견하는 바로 그 시점에 STT까지
같이 돌기 때문에(`youtube_pipeline.py` 신규 분기), 정기 수집만 계속 돌면 새로
올라오는 영상만 자동으로, 그때그때 소량씩 처리된다. 즉 "백로그 소진"과 "그 이후
정상 운영"은 같은 코드 경로(`run()`)가 자연히 담당하고, 백필 스크립트는 어디까지나
1회성 소급용이다.

**Airflow 도입(§6.2, `04_Collection_Pipeline_Operations.md`) 시 반영해야 할 것**:
- 백로그 소진은 Airflow DAG가 아니라 이번처럼 수동으로 `--limit`을 키워가며 미리
  끝내두는 걸 전제로 한다(Airflow는 "많은 배치를 며칠에 걸쳐 처리"하는 용도로 설계돼
  있지 않음 — 정기 수집처럼 짧게 끝나는 작업에 맞는 도구라서, 굳이 DAG화하지 않음)
- 다만 `run()`의 인라인 STT 호출이 어떤 이유로든 실패한 영상은 `has_transcript=FALSE`로
  영구히 남는다(§5 결정대로 예외를 삼키고 넘어가므로) — Airflow DAG에 **저빈도 안전망
  태스크**(예: 주 1회 `backfill_youtube_transcripts.py --limit N` 실행)를 하나 추가해
  이런 누락분을 주기적으로 걷어내는 걸 고려할 것. 지금 당장 결정할 사항은 아니고
  §6.2 착수 시점에 다시 논의.

---

## 5. 쓰기 시점 (확정)

DB 트랜잭션(=`dcat_provenance`/`data_registry` 갱신)이 성공적으로 끝난 **직후**,
각 파이프라인 `run()`의 마지막 단계로 SeaweedFS 쓰기를 추가한다.

- **PostgreSQL이 항상 먼저, 유일한 source of truth.** S3 쓰기는 DB가 이미 커밋된
  뒤 그 결과를 파일로 내보내는 후속 단계 — S3가 절대 DB보다 앞서가거나 어중간한
  상태를 반영하지 않는다.
- **개별 아이템 raw 파일**(뉴스/블로그 본문, YouTube 트랜스크립트)은 신규/갱신되는
  그 시점에 이미 메모리에 콘텐츠가 있으므로 그 자리에서 같이 쓴다.
- **JSON-LD 전체 스냅샷과 shopping/persona CSV**는 `run()` 끝에서 "지금 DB에 있는
  전체 상태"를 다시 읽어 통째로 재생성한다 — 부분 변경분만 반영하면 파일이 점점
  DB와 어긋날 위험이 있다.
- **S3 쓰기 실패는 `run()` 전체를 실패시키지 않는다.** DB 수집은 이미 성공했으므로
  그게 우선이고, S3는 부가적인 백업/배포 산출물이다. 실패 시 로그만 남기고(추후
  재시도는 다음 수집 주기가 자연스럽게 대체) 예외를 삼킨다 — 멀쩡한 수집까지 매번
  실패로 기록되는 걸 방지.
- 완료 후 `data_registry.s3_raw_prefix`/`s3_jsonld_prefix`를 실제 경로로 갱신한다
  (지금까지 한 번도 채워진 적 없는 컬럼).

---

## 6. Vector Embedding과의 관계 (사실 기록, 확정 아님 — 향후 과제)

지금 임베딩(`scripts/embed_*.py`)은 **완전히 수동, 수집 파이프라인과 무관**하다.
5개 `run()` 어디서도 자동 호출되지 않고, 수집이 끝난 뒤 사람이 별도로 스크립트를
실행해야 한다. 게다가 지금 방식은 **테이블 전체 DELETE 후 재계산**
(`scripts/embed_youtube_videos.py`의 `DELETE FROM meta_youtube_video_vec` 등) —
영상 1개가 늘어도 전체를 다시 임베딩한다.

Airflow 도입(§6.2, `04_Collection_Pipeline_Operations.md`) 시 임베딩도 파이프라인에
연결돼야 하는 건 맞지만, 지금 방식(전체 재계산) 그대로 매 수집 후 자동 실행시키면
비효율이 크다(영상 1개 늘 때마다 기존 수천 개 재임베딩). **순서 제안**: 증분
임베딩(신규/변경분만) 전환을 먼저 하고, 그 다음에 Airflow task로 연결 — 이 문서의
SeaweedFS export와 구조적으로 비슷한 처지("수집 뒤에 붙는 후속 단계, 현재 수동")이지만
범위가 커서 별도 과제로 `NEXT_STEPS.md`에서 계속 추적한다.

---

## 7. `src/storage/` 모듈 설계 (초안, 2026-07-27)

지금까지 확정된 §2~§5를 실제로 실행하는 코드 레이어. 아직 미구현 — 아래는 인터페이스
초안이며, 구현 전 STT 서버 스펙(§4.4, §8) 확인이 선행돼야 §4.5 부분이 완성된다.

```
src/storage/
├── s3_client.py       # boto3 클라이언트 팩토리 + 저수준 업로드 헬퍼
├── raw_export.py       # 아이템 단위 raw 파일 쓰기 (video 트랜스크립트 JSON,
│                        # news/blog 본문 txt, shopping/persona CSV)
└── jsonld_export.py    # source_type별 JSON-LD 생성 + 업로드
```

### 7.1 `s3_client.py`

```python
def get_s3_client():
    """boto3 클라이언트. infrastructure/04_ObjectStorage.md의 .env 값
    (S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY/S3_REGION) 사용, path-style 강제."""

def upload_text(key: str, text: str) -> None: ...
def upload_json(key: str, obj: dict) -> None: ...
def upload_bytes(key: str, data: bytes, content_type: str) -> None: ...
```

`src/common/config.py`에 이미 있는 `.env` 로딩 패턴(`get_env`/`require_env`) 그대로
재사용 — `S3_ENDPOINT`/`S3_ACCESS_KEY`/`S3_SECRET_KEY`/`S3_BUCKET`/`S3_REGION` 5개
상수 추가만 필요.

### 7.2 `raw_export.py`

```python
def write_video_transcript(dataset_id: str, video_id: str, segments: list, full_text: str) -> str:
    """§4.5 포맷으로 JSON 업로드. 반환값 = S3 key (JSON-LD의 mi:transcriptRef에 씀)."""

def write_article_content(dataset_id: str, source_type: str, item_id: int, text: str) -> str:
    """news/blog 공용 — has_content=TRUE일 때만 파이프라인이 호출."""

def write_declarative_csv(dataset_id: str, source_type: str, rows: list[dict]) -> str:
    """shopping/persona — run() 끝에서 전체 active_meta_* 재조회 후 통째로 덮어씀."""
```

**호출 시점(§5 결정 그대로)**: `write_video_transcript`/`write_article_content`는 STT/
스크래핑 결과가 메모리에 있는 그 자리(각 pipeline의 신규/갱신 분기 안)에서 호출.
`write_declarative_csv`는 `run()` 마지막에 한 번.

### 7.3 `jsonld_export.py`

```python
def export_dataset(dataset_id: str) -> tuple[str, str]:
    """dcat_dataset.source_type을 보고 아래 build_* 중 하나로 분기,
    결과를 jsonld/{source_type}/{dataset_id}/{dataset_id}.jsonld로 업로드.
    반환값 = (s3_raw_prefix, s3_jsonld_prefix) — data_registry 갱신용."""

def _build_video(dataset_id: str) -> dict: ...      # §3.2 스키마
def _build_news(dataset_id: str) -> dict: ...
def _build_blog(dataset_id: str) -> dict: ...
def _build_shopping(dataset_id: str) -> dict: ...    # §3.3 스키마 (참조 방식)
def _build_persona(dataset_id: str) -> dict: ...
```

**호출 시점**: 각 파이프라인 `run()`의 `dcat.update_data_registry(...)` 성공 직후 1회.
DB에서 "지금 전체 상태"를 다시 읽어 통째로 재생성(§5) — try/except로 감싸서 실패해도
`run()` 자체는 성공 처리(§5 결정).

### 7.4 파이프라인 통합 지점 (구현 시 손댈 파일)

기존 5개 `src/pipelines/*.py`에 아래 한 줄 패턴이 추가된다 (예: `youtube_pipeline.py`):

```python
try:
    s3_raw_prefix, s3_jsonld_prefix = jsonld_export.export_dataset(dataset_id)
    dcat.update_data_registry(dataset_id, s3_raw_prefix=s3_raw_prefix, s3_jsonld_prefix=s3_jsonld_prefix)
except Exception as e:
    logger.warning(f"S3 export 실패 (수집 자체는 성공): {e}")
```

**구현 완료 (2026-07-27)**: `src/storage/{s3_client,raw_export,jsonld_export}.py`,
`src/collectors/youtube_transcript_collector.py`, 5개 파이프라인 통합, `meta_youtube_video.
has_transcript`/`transcribed_at` 마이그레이션 적용, `scripts/backfill_youtube_transcripts.py`
전부 실 서버(`naver_news_ai`, `youtube_samsung_official`)로 검증 완료 — SeaweedFS에
실제 오브젝트 생성, `data_registry.s3_raw_prefix`/`s3_jsonld_prefix` 채워짐, 트랜스크립트
JSON 정상 생성 확인.

구현 중 발견한 것: yt-dlp 기본(web) 클라이언트가 2025년 하반기 YouTube 봇 감지 강화로
"The page needs to be reloaded" 에러를 냄 — `extractor_args: {"youtube": {"player_client":
["android"]}}`로 우회(§4의 IP 차단 문제와는 다른 층위 — 이건 단순 다운로드 요청 포맷
문제). 또한 최초 구현 시 Whisper `language="ko"`를 고정했었는데, YouTube 데이터셋이
꼭 한국어 채널만은 아니라서(예: Samsung 글로벌 채널은 영어) 언어를 강제하면 품질이
크게 떨어지는 걸 실측으로 확인 — 언어 자동 감지로 수정, `raw_export.write_video_transcript`도
감지된 실제 언어를 받도록 시그니처 변경.

### 7.5 `pyproject.toml` 추가 의존성

```
boto3            # S3 클라이언트
faster-whisper   # STT (§4.4 — CTranslate2 기반, openai-whisper보다 CPU 추론 빠름)
```

`yt-dlp`는 오디오 다운로드용으로 별도 필요 — pip 패키지(`yt-dlp`)로 추가.

---

## 8. 아직 논의/확정 필요한 것 (다음 단계)

- [x] ~~§2.1 `{item_key}` 파일명 규칙~~ — 확정 (2026-07-27, news/blog 내부 PK 사용 승인)
- [x] ~~§3.3 shopping/persona JSON-LD inline vs 참조~~ — **확정: 참조 방식** (2026-07-27,
      최신 스냅샷만 JSON-LD에, 전체 이력은 CSV 참조)
- [x] ~~§4 YouTube 트랜스크립트 수집 방식~~ — **확정: 자체 STT** (2026-07-27, yt-dlp/프록시/
      유료 API 전부 제외 — 레거시와 다른 방식 + 무료 조건)
- [x] ~~raw 트랜스크립트 파일 포맷~~ — **확정: 세그먼트별 타임스탬프 JSON**(§4.5) (2026-07-27,
      Whisper가 어차피 세그먼트 단위로 출력하므로 버릴 이유 없음, `full_text` 필드 동봉)
- [x] ~~`src/storage/` 모듈 설계~~ — 초안 완료(§7), 실제 구현은 아래 항목들 확정 후
- [x] ~~STT 모델 크기 선택~~ — **확정: `faster-whisper` + `small` 모델 + INT8, CPU 추론**
      (§4.4, 2026-07-27, 서버에 GPU 없음 확인됨)
- [x] ~~CPU 코어 수 확인~~ — `RnD-analyzer01` 8코어 확인 (2026-07-27, §4.4)
- [x] ~~`ffmpeg` 서버에 설치~~ — 완료 (2026-07-27, CRB + RPM Fusion Free 경유, §4.4)
- [x] ~~백로그 소급 처리 파일럿 실행~~ — **실 서버(`RnD-analyzer01`) 재측정 완료**
      (2026-07-28, `--limit 5`): 모델 로딩 이후 영상 길이의 0.2~0.3배 시간 확인,
      개발 중 로컬 머신 측정치와 큰 편차 없음(§4.4 표 참조). 2,000개 백로그 전체
      순수 연산 25~50시간 추정 — 여러 날에 걸쳐 `--limit`을 키워가며 나눠 돌리는
      것 전제로 스크립트 설계됨(§7.4)
- [x] ~~`infrastructure/04_ObjectStorage.md`의 기존 디렉토리 구조 절을 이 문서의 §2.1로
      교체~~ — 완료 (2026-07-27)
- [x] ~~구현~~ — `src/storage/`, `youtube_transcript_collector.py`, 5개 파이프라인 통합,
      `has_transcript` 마이그레이션, 백필 스크립트 전부 완료 및 실 서버 검증 (2026-07-27)

---

## 9. 관련 문서 갱신 이력

- 2026-07-27: 이 문서 신설. `infrastructure/04_ObjectStorage.md`의 날짜 파티션
  디렉토리 구조를 §2.1의 아이템 단위/덮어쓰기 구조로 교체 예정.

---

## 관련 문서

- 인프라: [infrastructure/04_ObjectStorage.md](../infrastructure/04_ObjectStorage.md)
- 전략 결정: [ADR-004](../adr/004_ObjectStorage_Strategy.md)
- 수집 파이프라인 실행 로직: [04_Collection_Pipeline_Operations.md](04_Collection_Pipeline_Operations.md)
