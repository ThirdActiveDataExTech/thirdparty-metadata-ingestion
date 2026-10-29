# 테이블별 컬럼 충족 방법 — 비정형 5종

> **Last Updated:** 2026-10-29
> **근거:** 시나리오 25건(소스별 5건)을 실제 등록·수집해 측정한 결과.
> 시나리오 정의는 [scripts/scenarios/collection_scenarios.py](../../scripts/scenarios/collection_scenarios.py).
>
> 정형(`source_type='structured_file'`)은 와이즈넛이 포털 메타데이터로 채우므로 대상이 아니다.
> 등록 입력 명세는 [api/01_Dataset_Registration_Scenario.md](../api/01_Dataset_Registration_Scenario.md) 참조.

---

## 범례

| 기호 | 뜻 |
|---|---|
| 👤 | **사용자 입력** — 등록 화면에서 받는다 |
| 🔌 | **원천 API** — 수집 시 원천이 주는 값 |
| 📌 | **소스별 고정값** — `_SOURCE_META`에 박혀 있다 |
| ⚙️ | **서버 자동** — 채번·계산·집계 |
| 🤖 | **AI 추출** — 아직 미구현 (B1/A2 과업) |
| 🤝 | **와이즈넛 협의** — 값 규칙 미정 |
| — | 해당 없음 (그 소스에는 개념이 없다) |

충족률은 `✅ 전부` / `N/M` / `✗ 전부 빔`.

---

## 1. `dcat_dataset` (25건) — 데이터셋 카탈로그

### 1.1 등록 시점에 채워지는 것

| 컬럼 | 방법 | 값 / 규칙 |
|---|---|---|
| `dataset_id` | ⚙️ | `urn:{ns}:{source_type}_dataset_{랜덤6}` |
| `title` · `description` | 👤 | 필수. `description`은 SEMANTICALLY_RELATED 판정 근거 |
| `keywords` | 👤 | video·shopping·persona **필수**, news·blog는 검색어로 자동 채움 |
| `subjects` | 👤 | 채널/영상 ID · 검색어 · 카테고리 |
| `accrual_periodicity` | 👤 | 기본 `P1D` |
| `visibility` | 👤 | 기본 `ORG` |
| `source_type` | 👤 | 화면에서 고른 소스 |
| `source` · `publisher` | 📌 | video→`YouTube`, 그 외→`Naver` (비정형은 원천=제공기관) |
| `license` · `rights` | 📌 | 소스별 약관 URL·이용 제한 문구 |
| `landing_page` · `access_url` | 📌 | 소스별 서비스 URL·API 엔드포인트 |
| `language` · `spatial` | 📌 | `ko` · `KR` (DDL 기본값) |
| `party` | 📌 | **`3rd` 고정** — 비정형은 전부 외부 원천 |
| `temporal_resolution` | 📌 | 선언형 `P1D`, 발견형은 해당 없음 |
| `dataset_origin` | ⚙️ | 호출자 권한으로 결정. **요청 바디로 받지 않는다** |
| `owner_id` | ⚙️ | 인증 토큰에서 추출 (`origin=user`일 때만) |
| `external_ids` | ⚙️ | §1.3 참조 |
| `version` · `created_at` · `updated_at` | ⚙️ | `1.0` · `now()` |
| `item_count` | ⚙️ | 선언형만 등록 시(카테고리 수). 발견형은 수집 후 |
| `temporal_start` | 👤⚙️ | 선언형은 소급 시작일 입력, 발견형은 수집 후 계산 |

### 1.2 수집 후 채워지는 것

| 컬럼 | 방법 | video | news | blog | shopping | persona |
|---|---|---|---|---|---|---|
| `item_count` | ⚙️ `data_registry` 미러 | ✅ | ✅ | ✅ | ✅ | ✅ |
| `temporal_start` | ⚙️ `MIN(published_at)` / `MIN(period)` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `theme` | 🔌 원천 분류 집계 | ✅ | **✗** | **✗** | ✅ | ✅ |

`theme` 집계 규칙 ([src/database/theme.py](../../src/database/theme.py)):

```
video              categoryId(YouTube 고정 32종) + topicCategories(위키 주제), 빈도순 상위 8
shopping/persona   meta_*.cat_level1 (네이버 쇼핑 대분류)
news/blog          없음 — 네이버 검색 API가 분류를 주지 않는다
```

실제 값:

```
대항병원 대장항문 질환 정보   ['Education', 'People & Blogs', 'Health', 'Society', 'Knowledge']
내가 보는 반도체 채널       ['Science & Technology', 'Nonprofits & Activism', ...]
패션 전체 검색 트렌드       ['패션의류', '패션잡화']
```

### 1.3 `external_ids` — 중복 판정 근거

| 소스 | 값 | 예 |
|---|---|---|
| video (채널) | 🔌 채널 ID 그대로 | `youtube:UCf3ZZpHjdWbCplbPQigtNvw` |
| video (개별영상) | ⚙️ 영상 집합 해시 | `youtube:videoset:sha256-5d24958a5471` |
| news·blog·shopping·persona | ⚙️ 수집 조건 집합 해시 | `naver:news:sha256-3c639c929baf` |

채널 ID는 YouTube가 발급한 **진짜 객체 키**라 그대로 쓴다. 나머지(검색어·카테고리·
큐레이션한 영상 목록)는 **우리가 정한 수집 조건**이라, 개별 값을 넣으면 하나만
겹쳐도 중복으로 오판된다 — 집합 전체를 해시하면 완전히 같을 때만 겹친다.
`sha256-` 접두는 "원천에 조회되지 않는 합성값"임을 값 자체로 드러낸다.
규칙 상세: [dataset_id_urn_migration.md §7](dataset_id_urn_migration.md).

### 1.4 아직 비는 것

| 컬럼 | 상태 | 어떻게 채울 것인가 |
|---|---|---|
| `category` | 🤖 **자동 부여** | 와이즈넛 분류표(대분류 7 / 중분류 76)를 받아 임베딩 zero-shot으로 부여한다. **다만 품질이 낮다 — §9 참조** |
| `theme` (news·blog) | 🤖 **전부 빔** | 네이버 검색 API가 분류를 주지 않는다. 호스팅 기사만 섹션 스크래핑이 가능한데 외부 기사가 약 68%라 커버 안 됨 → 🤖 분류 모델(ADR-013) |
| `publisher_code` | — **미사용 확정** | 2026-10-29 결정: **비정형은 당분간 쓰지 않는다.** 기관코드 체계가 공공데이터포털 기준이라 Naver·YouTube에 대응하는 값이 없다 |
| `temporal_end` | — **전부 빔** | **정상.** NULL이 "현재 진행 중(open-ended)"을 뜻한다 |
| `temporal_resolution` (발견형) | — | **정상.** 영상·기사는 고정 주기 관측이 아니다 |
| `owner_id` | ⚙️ 1/5 | **정상.** `origin=user`일 때만 채운다 |

> ⚠️ **없는 분류를 지어내지 않는다.** news·blog의 `theme`을 검색어로 채우면
> "원천이 붙인 분류"라는 컬럼의 뜻이 깨진다. 분류 모델이 생길 때까지 비워 둔다.

---

## 2. `data_registry` (25건) — 운영 레지스트리

| 컬럼 | 방법 | 시점 | 상태 |
|---|---|---|---|
| `dataset_id` | ⚙️ | 등록 | ✅ |
| `pg_meta_table` · `pg_active_table` · `vec_collection` | 📌 | 등록 | ✅ |
| `status` | ⚙️ | 등록 `pending` → 수집 `active`/`error` | ✅ |
| `item_count` · `row_count` | ⚙️ 실측 | 수집 | ✅ |
| `temporal_start` | ⚙️ | 수집 | ✅ |
| `last_collected_at` · `next_collect_at` | ⚙️ | 수집 | ✅ |
| `s3_raw_prefix` · `s3_jsonld_prefix` | ⚙️ | 첫 내보내기 | ✅ |
| `last_error` | ⚙️ | 실패 시에만 | **✗ 정상** (실패 없음) |
| `temporal_end` | — | — | **✗ 정상** (진행 중) |

> `item_count` · `temporal_start` · `temporal_end`는 `dcat_dataset`과 **같은 값**이다.
> `data_registry`가 원본이고 `dcat_dataset`이 미러이며, `update_data_registry()`가
> 같은 트랜잭션에서 둘 다 갱신한다 — 호출부가 잊을 수 있는 구조였고 실제로
> 18건 중 14건이 어긋나 있었다(2026-10-28 수정).

---

## 3. 아이템 테이블 — 소스별

### 3.1 `meta_video` (1,554행)

| 컬럼 | 방법 | 충족 | 비고 |
|---|---|---|---|
| `video_id` · `title` · `published_at` · `channel_id` · `channel_title` · `duration` · `definition` · `category_id` · `thumbnail_url` | 🔌 | ✅ | `part=snippet,contentDetails` |
| `initial_view_count` | 🔌 | ✅ | `part=statistics` |
| `description` | 🔌 | 1,489/1,554 | 업로더가 비워 둔 영상 |
| `tags` | 🔌 | 1,409/1,554 | 업로더가 안 단 영상 |
| `topic_categories` | 🔌 | 1,321/1,554 | `part=topicDetails` |
| `initial_like_count` · `initial_comment_count` | 🔌 | 1,377 / 1,548 | **비공개 설정이면 API가 안 준다** |
| `default_audio_language` | 🔌 | 1,151/1,554 | 업로더 미설정 |
| `has_transcript` · `transcribed_at` | ⚙️ STT | 14/1,554 | **§5 참조** — 예산 안에서 점진 처리 |
| `is_removed` · `removed_at` | ⚙️ | ✗ 정상 | 삭제 감지된 영상만 |

### 3.2 `meta_news` (1,755행)

| 컬럼 | 방법 | 충족 | 비고 |
|---|---|---|---|
| `article_url` · `title` · `description` · `published_at` · `search_keyword` | 🔌 | ✅ | 네이버 검색 API |
| `publisher` · `naver_url` · `is_naver_hosted` | ⚙️ URL 파싱 | ✅ | |
| `content` · `has_content` | 🔌 스크래핑 | 1,606/1,755 | 본문 스크래핑 실패분 |
| `naver_oid` · `naver_aid` | ⚙️ URL 파싱 | 580/1,755 | **네이버 호스팅 기사만 해당** |
| `is_removed` · `removed_at` | ⚙️ | ✗ 정상 | |

### 3.3 `meta_blog` (1,772행)

| 컬럼 | 방법 | 충족 | 비고 |
|---|---|---|---|
| `post_url` · `title` · `blogger_name` · `blogger_link` · `published_at` · `search_keyword` | 🔌 | ✅ | 네이버 검색 API |
| `platform` | ⚙️ URL 파싱 | ✅ | `naver` / 외부 |
| `description` · `content` · `has_content` | 🔌 스크래핑 | 1,770/1,772 | |
| `blog_id` · `log_no` | ⚙️ URL 파싱 | 1,752/1,772 | **`platform='naver'`만 해당** |

### 3.4 `meta_shopping_insight` · `meta_persona_insight` (각 6행)

| 컬럼 | 방법 | 충족 | 비고 |
|---|---|---|---|
| `category_id` · `category_name` | 👤 | ✅ | 등록 시 사용자 선택 |
| `cat_level1` | ⚙️ `category_name`을 `>`로 분해 | ✅ | |
| `cat_level2~4` | ⚙️ 〃 | ✗ | **정상** — 대분류만 골라서 하위 단계가 없다 |
| `is_anchor` | ⚙️ | ✅ | 첫 카테고리 (shopping만) |

> ⚠️ `cat_level1~4`는 **2026-10-29까지 아무도 채우지 않았다.** 시드 데이터에만 값이
> 있어 가려져 있었고, 실제 등록으로 만든 행은 전부 NULL이었다. `idx_shopping_level1`
> 인덱스가 걸린 대분류 집계·필터의 전제라 쓸 수 없는 상태였다.

---

## 4. 시계열 테이블 (`active_meta_*`)

| 테이블 | 행 | 비는 컬럼 | 판정 |
|---|---|---|---|
| `active_meta_video` | 1,640 | `like_count`(1,463) · `comment_count`(1,634) | 🔌 **비공개 설정 영상** |
| | | `delta_*`(86) | ⚙️ **정상** — 첫 스냅샷은 비교 대상이 없다 |
| `active_meta_news` | 580 | `delta_comments` 전부 | ⚙️ **정상** — 동일 |
| `active_meta_blog` | 2,009 | `reaction_breakdown`(531) | 🔌 반응이 없는 게시물 |
| | | `delta_reactions`(257) | ⚙️ **정상** — 동일 |
| `active_meta_shopping_insight` | 1,596 | **없음** | ✅ |
| `active_meta_persona_insight` | 1,596 | **없음** | ✅ |

---

## 5. 벡터 테이블 — 전부 자동

| 테이블 | 청크 | 입력 텍스트 |
|---|---|---|
| `dcat_dataset_vec` | 75 | 제목 + 설명 + 키워드 |
| `meta_video_vec` | 19,614 | 영상 제목 + 설명 + 태그 |
| `meta_news_vec` | 36,242 | 기사 제목 + 요약 + 본문(2,000자) |
| `meta_blog_vec` | 104,211 | 게시물 제목 + 요약 + 본문(2,000자) |
| **합계** | **160,142** | 모델 `intfloat/multilingual-e5-base` (768차원) |

수집 파이프라인이 끝에서 증분 동기화한다. **원본 1건 = 청크 N건**이며 검색은
청크 최대 유사도로 집계한다 — 근거는 [embedding_chunking.md](embedding_chunking.md).

### 자막(STT)은 시간 예산으로 점진 처리

자막은 B1(키워드 추출)·A2(AI 메타데이터)의 입력이라 파이프라인에 있어야 하지만,
영상 1건당 약 1.4분이라 전부 돌리면 수집이 끝나지 않는다(1,500건 = 35시간).

수집 본체가 끝난 뒤 **예산(기본 600초)만큼만** 만들고 나머지는 다음 회차가
이어서 한다. `YOUTUBE_TRANSCRIPT_BUDGET_SEC`로 조절하고, 백로그를 빨리 줄이려면
`scripts/backfill_youtube_transcripts.py`를 따로 돌린다.

> ⚠️ 기본값 600초는 확정이 아니다. **P0-2(자막 생성 범위 결정)** 에서 수집 주기와
> 함께 정해야 한다.

---

## 6. 이력 테이블 (`dcat_provenance`, 28행)

| 컬럼 | 방법 | 충족 |
|---|---|---|
| `dataset_id` · `activity_type` · `agent` · `started_at` · `ended_at` · `status` | ⚙️ | ✅ |
| `triggered_by` | ⚙️ 환경변수 | ✅ |
| `rows_affected` · `params` | ⚙️ | 27/28 |
| `notes` | ⚙️ | 17/28 — 수집 요약(`신규 N / 갱신 N / 삭제감지 N`) |
| `error_message` | ⚙️ | 1/28 — **실패 시에만** |

> `dcat_provenance`는 FK가 없다(데이터셋 폐기 후에도 이력을 남기기 위함).
> `dataset_id`가 바뀌면 전파되지 않으므로 **명시적 UPDATE가 필요하다**.

---

## 7. 발견된 설계 공백 — 데이터셋 삭제가 S3를 정리하지 않는다

`dcat_dataset`을 지우면 FK `ON DELETE CASCADE`로 DB의 자식 행은 전부 따라간다.
**그런데 오브젝트 스토리지는 아무도 치우지 않는다.**

2026-10-29 샘플 데이터 정리 후 실측:

```
전체 경로 63개 중 고아 경로 16개
고아 객체 2,157개 (27.2MB)
  raw/news/naver_news_ai/        1,228개
  raw/blog/naver_blog_ai/          908개
  jsonld/... 8개 데이터셋분
```

원인은 구조적이다 — FK는 DB 안에서만 작동하고, S3 경로는 `storage_key(dataset_id)`로
파생될 뿐 역참조가 없다. 데이터셋을 지우면 **그 경로를 아무도 모르게 된다.**

필요한 것:
- 데이터셋 삭제 API(§D1)에 S3 prefix 삭제를 포함
- 또는 주기적으로 `data_registry`에 없는 prefix를 찾아 정리하는 작업
- `scripts/check_conventions.py`의 F-1 검사가 이미 고아 경로를 잡아낸다

> ⚠️ 현재 남은 2,157개는 **S3 백업이 없다**(2026-10-29 DB만 CSV로 백업).
> 지우면 복구 불가이므로 별도 판단이 필요하다.

---

## 8. 남은 작업

| 항목 | 상태 | 필요한 것 |
|---|---|---|
| `category` | ⚠️ 부여하나 품질 낮음 | 로컬 sLLM(ADR-013 🟦)으로 대체 검토 — §9 |
| `theme` (news·blog) | 🤖 미착수 | 임베딩 zero-shot 분류 (ADR-013) |
| `publisher_code` | ✅ 미사용 확정 | 비정형은 쓰지 않는다 |
| 자막 백로그 | ⏳ **배치 스케줄 미등록** | `--budget-sec` 지원은 완료. ADR-008 경량 스케줄러에 붙일지 별도 CronJob으로 둘지 결정 필요 |
| 임베딩 모델 | ✅ 전환 완료 | `multilingual-e5-base` (2026-10-29) |
| 채널 URL→ID 변환 | 미구현 | 등록 화면이 채널 ID를 묻지 않으려면 필요 |
| 쇼핑 카테고리 트리 API | 미구현 | 등록 화면 선택용 |
| S3 삭제 경로 설계 | ⏳ | 고아 객체 2,157개는 2026-10-29 정리 완료. **삭제 API에 prefix 정리를 넣는 일은 미구현** |

---

## 9. `category` 분류 품질 — 현재 수준과 방침

와이즈넛은 정형에 **언어 모델**로 부여하고, 실패 시 **임베딩 최근접 중분류 1개**를
넣는다고 정의했다. 우리는 ADR-013으로 외부 LLM을 안 쓰므로 **그 폴백을 주 경로로**
쓴다 — 같은 분류표·같은 형식·같은 개수 규칙이라 결과는 상호 운용된다.

**품질은 신뢰할 수 없다.** 사람이 본 정답과 비교한 실측(8건):

| 모델 | Top-1 정확 | Top-3 포함 |
|---|---|---|
| paraphrase-multilingual-mpnet-base-v2 | 3/8 | 5/8 |
| multilingual-e5-base | 3/8 | 4/8 |

```
HBM 뉴스         → 문화 > 방송·미디어   (기대: 기술 > 전기·전자)
패션의류 검색 트렌드 → 문화 > 공예         (기대: 사회 > 산업)
```

**모델 교체로 해결되지 않는다.** 76개 라벨이 `'의료 > 공중보건'` 같은 짧은 명사구인데,
임베딩으로 긴 데이터셋 설명과 맞추는 일 자체가 이 모델들의 학습 목표가 아니다.
e5는 틀린 답에도 0.82~0.85를 줘서 임계값으로 거르기도 어렵다.

### 모델 교체 후 — 실데이터 25건

합성 8건 테스트에서는 두 모델이 Top-1 3/8으로 같았지만, **실제 데이터셋에서는
e5가 눈에 띄게 낫다.** `theme`이 함께 들어가 신호가 세지기 때문으로 보인다.

```
이전 모델                           e5-base
내가 보는 반도체 채널 → 문화 > 만화     →  기술 > 전기·전자   ✅
암 정보 큐레이션    → 문화 > 만화     →  의료 > 질병관리    ✅
외과 전문의 채널    → 문화 > 음악     →  의료 > 질병관리    ✅
양자컴퓨팅 뉴스     → 기술 > 인공지능·컴퓨팅 (양쪽 동일)    ✅
```

**대분류는 대체로 맞고 중분류가 자주 틀린다.** 25건 중 대분류까지 틀린 것은 3건이다.

```
HBM 뉴스          → 문화 > 방송·미디어   (기대: 기술 > 전기·전자)  ❌
디지털가전 구매층 분석 → 문화 > 방송·미디어   (기대: 기술 > 전기·전자)  ❌
패션의류 검색 트렌드  → 문화 > 공예        (기대: 사회 > 산업)      ❌
치질 수술 안내      → 의료 > 치의학       (대분류는 맞음)          △
```

**방침 (2026-10-29 결정): 틀리더라도 일단 부여한다.**
분류가 비어 있으면 포털 전체 필터링이 아예 성립하지 않기 때문이다.
`CATEGORY_MIN_SIMILARITY=0.0`(기본)으로 임계값을 사실상 끄고, 로컬 sLLM
(ADR-013 🟦 목표선)이 준비되면 그쪽으로 대체한다 — 와이즈넛의 정형 부여 방식과
같아지므로 결과 일관성도 올라간다.

---

## 참고

- [api/01_Dataset_Registration_Scenario.md](../api/01_Dataset_Registration_Scenario.md) — 등록 입력 명세
- [embedding_chunking.md](embedding_chunking.md) — 청킹 전환 근거
- [dataset_id_urn_migration.md](dataset_id_urn_migration.md) — 채번 규칙, `external_ids` 규칙
- `scripts/scenarios/` — 이 문서의 근거가 된 시나리오 정의·실행기
- `scripts/check_conventions.py` — 식별자·경로 규칙 전수 점검기
