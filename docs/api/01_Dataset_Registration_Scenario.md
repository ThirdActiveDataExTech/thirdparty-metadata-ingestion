# 비정형 데이터셋 등록 시나리오 — 사용자 입력과 컬럼 충족 출처

> **Last Updated:** 2026-10-28
> **범위:** 비정형 5종(video / news / blog / shopping_insight / persona_insight)만 다룬다.
> 정형(`source_type='structured_file'`)은 와이즈넛이 포털 메타데이터에서 대부분 채우므로
> 이 문서의 대상이 아니다.
>
> **용도:** 프론트엔드 등록 화면 설계와 `POST /api/datasets` 구현의 입력 명세.
> 연계 과업: [NEXT_STEPS.md §6.3](../NEXT_STEPS.md), D1(플랫폼 운영 기능).

---

## 1. 등록의 두 갈래 — 발견형과 선언형

비정형 5종은 **등록 시점에 무엇이 정해지는가**로 갈린다. 이 구분이 화면 구성과
등록 트랜잭션의 범위를 결정한다.
([04_Collection_Pipeline_Operations.md §4](../architecture/04_Collection_Pipeline_Operations.md))

| | **발견형** | **선언형** |
|---|---|---|
| 소스 | video · news · blog | shopping_insight · persona_insight |
| 사용자가 주는 것 | **어디서 찾을지**(채널 ID, 검색어) | **무엇을 볼지**(카테고리 목록) |
| 아이템 확정 시점 | 최초 수집 때 원천이 알려준다 | **등록 시점에 이미 확정** |
| 등록 시 `meta_*` | 쓰지 않는다 (비어 있음) | **함께 INSERT한다** |
| `item_count` | 최초 수집 후 채워짐 | 등록 시 카테고리 개수로 바로 채움 |
| 아이템 증가 | 새 영상·기사·게시물이 계속 들어옴 | 카테고리는 고정, 시계열만 쌓임 |

> 등록 API를 **소스 타입별 핸들러로 분리**해야 하는 이유가 이것이다. 선언형은
> 등록 트랜잭션 안에서 `meta_*`까지 써야 하고, 발견형은 쓰면 안 된다.

---

## 2. 사용자 입력 명세 — 소스별

### 2.1 모든 소스 공통

| 입력 | 필수 | 들어가는 곳 | 비고 |
|---|---|---|---|
| 제목 | ✅ | `title` | 식별자에는 쓰이지 않는다(§4 참조) |
| 설명 | ✅ | `description` | **비우면 안 된다** — 관계 산출(SEMANTICALLY_RELATED)의 판정 근거다 |
| 수집 주기 | — | `accrual_periodicity` | ISO 8601 duration. 기본 `P1D` |
| 공개 범위 | — | `visibility` | 기본 `ORG` |

사용자에게 **묻지 않는 것**도 명확히 해둔다.

- `dataset_id` — 서버가 채번한다. 사용자가 고르게 하면 충돌·형식 위반을 떠안는다
- `dataset_origin` — **요청 바디로 받지 않는다.** 서버가 호출자 권한으로 결정한다
  (사용자가 `admin`을 보내면 그대로 믿게 되는 문제)
- `owner_id` — 인증 토큰에서 꺼낸다

### 2.2 video (YouTube)

| 입력 | 필수 | 형태 | 들어가는 곳 |
|---|---|---|---|
| 채널 ID 목록 | △ | `UCxxxxxxxxxxxxxxxxxxxxxx` | `subjects.channels` |
| 개별 영상 ID 목록 | △ | `dQw4w9WgXcQ` | `subjects.videos` |

△ = **둘 중 최소 하나**는 있어야 한다. 채널 전체 수집과 개별 영상 큐레이션을
한 데이터셋에 섞을 수 있다(2026-07-28 확장).

> 화면 설계 시: 사용자는 채널 **URL**을 붙여넣지 채널 ID를 모른다.
> `youtube.com/@handle` → 채널 ID 변환을 서버가 해줘야 한다. 핸들은 바뀔 수 있으므로
> **저장은 채널 ID로** 한다.

### 2.3 news / blog (Naver 검색)

| 입력 | 필수 | 형태 | 들어가는 곳 |
|---|---|---|---|
| 검색어 목록 | ✅ | `["인공지능","AI","HBM"]` | `subjects` (평평한 배열) |

> 검색어 집합이 곧 수집 단위다. 같은 검색어 집합으로 두 번 등록하면
> `external_ids`의 집합 해시가 겹쳐 중복으로 탐지된다
> ([dataset_id_urn_migration.md §7](../database/dataset_id_urn_migration.md)).
> 화면에서 **등록 전에 경고**하는 것이 좋다.

### 2.4 shopping_insight / persona_insight (Naver 데이터랩)

| 입력 | 필수 | 형태 | 들어가는 곳 |
|---|---|---|---|
| 카테고리 목록 | ✅ | `50000148:패션의류` | `subjects` + **`meta_*` INSERT** |
| 소급 수집 시작일 | — | `2025-01-01` | `temporal_start` |

> **소급 수집 시작일은 등록 시점에만 의미가 있다.** 최초 수집이 이 날짜까지 거슬러
> 올라가고, 그 뒤 `temporal_start`는 실제 수집된 가장 이른 날짜로 덮인다
> ([naver_shopping_pipeline.py:93](../../src/pipelines/naver_shopping_pipeline.py#L93)).
> 나중에 바꿔도 소급되지 않으므로 화면에서 그 점을 알려야 한다.
>
> 카테고리 ID는 사용자가 외우지 못한다. **네이버 쇼핑 카테고리 트리를 화면에서
> 고르게** 하고 ID는 서버가 채운다.

---

## 3. 컬럼 충족 출처 — `dcat_dataset` 30컬럼 전수

범례:
**👤 사용자 입력** · **🔌 원천 API** · **📌 소스별 고정값** · **⚙️ 서버 자동 생성** ·
**🤖 AI/추출** · **🤝 와이즈넛 협의**

| 컬럼 | 출처 | 값 / 규칙 | 시점 |
|---|---|---|---|
| `dataset_id` | ⚙️ | `urn:{ns}:{source_type}_dataset_{랜덤6}` | 등록 |
| `title` | 👤 | 사용자 입력 | 등록 |
| `description` | 👤 | 사용자 입력 (필수) | 등록 |
| `source` | 📌 | video→`YouTube`, 그 외→`Naver` | 등록 |
| `publisher` | 📌 | `source`와 같은 값 (비정형은 원천=제공기관) | 등록 |
| `source_type` | 👤 | 화면에서 고른 소스 종류 | 등록 |
| `subjects` | 👤 | 채널/영상 ID · 검색어 · 카테고리 | 등록 |
| `accrual_periodicity` | 👤 | 기본 `P1D` | 등록 |
| `visibility` | 👤 | 기본 `ORG` | 등록 |
| `dataset_origin` | ⚙️ | 호출자 권한으로 결정 (`admin`/`user`) | 등록 |
| `owner_id` | ⚙️ | 인증 토큰에서 추출 | 등록 |
| `license` | 📌 | 소스별 약관 URL (`_SOURCE_META`) | 등록 |
| `rights` | 📌 | 소스별 이용 제한 문구 | 등록 |
| `landing_page` | 📌 | 소스별 서비스 URL | 등록 |
| `access_url` | 📌 | 소스별 API 엔드포인트 | 등록 |
| `language` | 📌 | `ko` (기본값) | 등록 |
| `spatial` | 📌 | `KR` (기본값) | 등록 |
| `party` | 📌 | **`3rd` 고정** — 비정형은 전부 외부 원천 | 등록 |
| `external_ids` | ⚙️ | video→채널 ID, 그 외→수집조건 집합 해시 | 등록 |
| `version` | ⚙️ | `1.0` | 등록 |
| `created_at` / `updated_at` | ⚙️ | `now()` | 등록/갱신 |
| `item_count` | ⚙️ | `data_registry`에서 미러 | **수집 후** |
| `temporal_start` | ⚙️ | 발견형: 실데이터 `MIN(published_at)` · 선언형: 👤 소급 시작일 | 수집 후 |
| `temporal_end` | — | **NULL이 "진행 중"을 뜻한다.** 채우지 않는다 | — |
| `temporal_resolution` | 📌 | 선언형 `P1D` · 발견형은 해당 없음 | 등록 |
| `keywords` | 🔌🤖 | **§5 참조** — 소스별로 재료가 다르다 | 수집 후 |
| `theme` | 🔌 | **§5 참조** — video·shopping/persona만 가능 | 수집 후 |
| `category` | 🤝 | 디지털 집현전 공통 분류. **와이즈넛 샘플값 대기 중** | 미정 |
| `publisher_code` | 🤝 | 기관코드. 비정형은 해당 없을 가능성 | 미정 |

### 3.1 `data_registry` (등록 시 함께 생성)

| 컬럼 | 출처 | 값 |
|---|---|---|
| `status` | ⚙️ | 등록 직후 `pending`, 최초 수집 성공 시 `active` |
| `pg_meta_table` / `pg_active_table` / `vec_collection` | 📌 | `_SOURCE_META` 고정 매핑 |
| `item_count` / `row_count` | ⚙️ | 수집 때 실측 |
| `s3_raw_prefix` / `s3_jsonld_prefix` | ⚙️ | 첫 내보내기 때. **그 전에는 NULL** |
| `last_collected_at` / `next_collect_at` | ⚙️ | 수집 때 |
| `last_error` | ⚙️ | 실패 시에만 |

---

## 4. 식별자는 사용자 입력에서 만들지 않는다

이전에는 제목을 슬러그화해 `dataset_id`를 만들었으나 2026-10-28에 폐기했다.

```
'AI 관련 뉴스'  → 'ai'       (AI만 살아남음)
'인공지능 뉴스'  → 'dataset'  (한글이 전부 걸러짐)
```

한글 제목은 거의 다 `dataset`으로 떨어져 의미가 없었고, 영문 제목은 제목을 조금만
고쳐도 식별자 모양이 달라졌다. **의미는 `title`이 들고 있으면 되고, 식별자는
유일하고 안정적이기만 하면 된다.**

읽을 수 있는 키가 필요한 경우(운영자가 직접 등록하는 기준 데이터셋 등)에만
관리자용 경로에서 `dataset_id`를 직접 지정한다. 일반 사용자 화면에는 노출하지 않는다.

---

## 5. `keywords` · `theme` — 소스가 주는 것과 안 주는 것

2026-10-28 실측 기준이다. **사용자에게 묻지 않고 채울 수 있는 범위**를 정리한다.

### 5.1 `keywords`

| 소스 | 재료 | 현재 수집 여부 | 방법 |
|---|---|---|---|
| video | `meta_video.tags` (영상 태그) | ✅ **75% 채워져 있음** | 데이터셋 내 태그 빈도 상위 N |
| news / blog | `subjects`(검색어) | ✅ 100% | 검색어 + 🤖 본문 키워드 추출(B1) |
| shopping / persona | `meta_*.category_name` | ✅ 100% | 카테고리명 그대로 |

→ **사용자 입력 불필요.** 이미 DB에 있는 값으로 수집 후 채울 수 있다.

> `keywords`는 GIN 인덱스가 걸려 있고 KEYWORD_OVERLAP 관계 판정의 전제다.
> 비어 있으면 그 데이터셋은 **키워드 검색과 관계 산출에서 통째로 빠진다.**
> 2026-10-28 실측에서 18건 중 11건이 빈 배열이었다.

### 5.2 `theme` (원천 분류 원문)

| 소스 | 원천이 주는 분류 | 상태 |
|---|---|---|
| **video** | `categoryId`(YouTube 고정 32종) + `topicCategories`(위키 URL) | ✅ **100% / 97% 수집 중** |
| **shopping / persona** | 네이버 쇼핑 카테고리 계층 `cat_level1` | ✅ **100% 수집 중** |
| **news / blog** | **없음** | ❌ 네이버 검색 API가 분류를 안 준다 |

실측 분포(video):

```
categoryId  26(Howto&Style) 17,882 · 27(Education) 6,242 · 28(Sci&Tech) 2,103 · …
topicCategories  ["https://en.wikipedia.org/wiki/Health"]
```

뉴스·블로그는 네이버 호스팅 기사 한정으로 **페이지 섹션(정치/경제/IT)을 스크래핑**하면
얻을 수 있으나, 외부 기사(약 68%)는 그마저 안 된다. 🤖 분류 모델로 채우는 것이
현실적인 대안이다(임베딩 zero-shot 분류, ADR-013).

### 5.3 `category` (디지털 집현전 공통 분류)

**와이즈넛 샘플값을 받아야 매핑 규칙을 정할 수 있다.** `theme`(원천 분류 원문)과는
별개 컬럼이며, 대분류 7종·중분류 76종 체계다
([category_taxonomy.md](../database/category_taxonomy.md)).

채우는 방법은 두 단계로 본다.
1. 🟩 `theme` → `category` 규칙 매핑 (YouTube 카테고리 32종, 네이버 쇼핑 대분류)
2. 🟦 매핑 규칙이 없는 뉴스·블로그는 🤖 임베딩 zero-shot 분류

---

## 6. 등록 직후의 상태 — 화면이 보여줘야 할 것

등록만으로는 데이터가 없다. **"등록 완료"와 "수집 완료"를 구분해서 보여줘야 한다.**

```
등록 직후        status=pending   item_count=NULL(발견형) / 카테고리 수(선언형)
                               s3_*_prefix=NULL   임베딩 없음
최초 수집 성공    status=active    item_count·temporal_start 채워짐
                               s3_*_prefix 생성   임베딩 생성
최초 수집 실패    status=error     last_error에 사유
```

> 최초 수집 실패를 `pending`과 구분하지 않으면 화면이 **"등록 중…" 스피너에서
> 영영 안 빠진다.** `GET /api/datasets/{id}/status`가 이 셋을 구분해 반환해야 한다.

---

## 7. 구현 시 확인할 것

- [ ] `party='3rd'` 고정값을 등록 경로에 넣기
- [ ] `landing_page` / `access_url` / `rights` 소스별 고정값을 `_SOURCE_META`에 추가
- [ ] `keywords` 자동 생성 (수집 후, 소스별 재료는 §5.1)
- [ ] `theme` 자동 생성 (video / shopping / persona, §5.2)
- [ ] `category` — 와이즈넛 샘플값 수령 후 매핑 규칙 결정
- [ ] 채널 URL/핸들 → 채널 ID 변환 (화면에서 ID를 묻지 않기 위해)
- [ ] 네이버 쇼핑 카테고리 트리 조회 API (화면 선택용)
- [ ] 같은 수집 조건 중복 등록 경고 (`external_ids` 집합 해시 비교)

---

## 참고

- [NEXT_STEPS.md §6.3](../NEXT_STEPS.md) — 프론트엔드 연동 API 과업 목록
- [04_Collection_Pipeline_Operations.md §4](../architecture/04_Collection_Pipeline_Operations.md) — 발견형/선언형 구분
- [04_Add_New_Dataset_Existing_Source.md](../runbooks/04_Add_New_Dataset_Existing_Source.md) — 현행 수동 등록 절차
- [dataset_id_urn_migration.md §6·§7](../database/dataset_id_urn_migration.md) — 채번 규칙, `external_ids` 규칙
- `scripts/register_dataset.py` — 현행 CLI 구현 (API의 참조 구현)
