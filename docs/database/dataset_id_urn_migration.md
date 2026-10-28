# dataset_id URN 전환 — 영향 범위와 절차

> **Last Updated:** 2026-10-28
> **상태:** ✅ **전환 완료 (2026-10-28)**
>
> 와이즈넛 정형 데이터 적재 개시 **전에** 완료했다. 적재 후였다면 FK `ALTER`가
> 양측 합의 사항이 되고 전환 범위에 상대 데이터가 들어갔을 것이다.
> ([ADR-014](../adr/014_Schema_Ownership_And_Change_Control.md))
>
> 실행 스크립트: [sql/migration_2026_10_28_dataset_id_urn.sql](../../sql/migration_2026_10_28_dataset_id_urn.sql)
> 이 문서는 전환의 근거와 범위를 남긴 기록이다. 아래 §1·§2는 **전환 전** 상태다.
>
> 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서는 `dataset_id`를
> **TEXT 최대 100자 URN**, 케이웨어 `cetus_*.metadata_id`와 **동일 값**으로 규정한다.
> 현재 우리 값은 slug 형식이라 전환이 필요하다. 착수 전 이 문서로 범위를 확정한다.

---

## 1. 전환 전 상태 (2026-10-27 실측)

| 항목 | 값 |
|---|---|
| 데이터셋 수 | 18건 |
| 형식 | slug (`naver_news_ai`, `youtube_samsung_official`, `user_hbm_video_collection`) |
| 최대 길이 | 33자 (스펙 상한 100자 — 여유 있음) |
| URN 접두 사용 | **0건** |

**발급 주체는 우리다.** 케이웨어가 우리 `dataset_id`를 받아가는 구조이므로,
외부에서 ID를 받아와 맞추는 것이 아니라 **우리가 정한 값을 URN 형식으로 바꾸면 된다.**
→ 마이그레이션 난이도가 크게 낮아진다. 값 자체의 의미는 보존할 수 있다.

**확정 규칙** (2026-10-28 와이즈넛 승인): `urn:{소스}:{수집단위키}`

비정형은 데이터셋이 원천 객체 하나에 1:1로 대응하지 않으므로, 원천 키 대신
**유일성이 보장된 수집 단위 키**를 쓴다. 원천 객체 키는 `external_ids`에 보존한다.

| 현재 slug | 전환 후 URN |
|---|---|
| `youtube_samsung_official` | `urn:youtube:samsung_official` |
| `user_hbm_video_collection` | `urn:youtube:hbm_video_collection` |
| `naver_news_ai` | `urn:naver:news_ai` |
| `naver_blog_ai` | `urn:naver:blog_ai` |
| `naver_shopping_insight` | `urn:naver:shopping_insight` |
| `naver_shopping_insight_advertiser` | `urn:naver:shopping_insight_advertiser` |
| `naver_persona_insight` | `urn:naver:persona_insight` |

신규 등록은 기존 채번 로직(슬러그 + 임의 접미 `secrets.token_hex(3)`)이 유일성을 보장한다.
→ `urn:naver:news_ai_a3f1c2`

---

## 2. 영향 범위

### 2.1 DB — FK 전파 여부가 갈린다

와이즈넛이 만든 테이블은 `ON UPDATE CASCADE`가 걸려 있어 **자동 전파**된다.
우리 테이블은 `NO ACTION`이라 **전파되지 않는다.**

| 테이블 | ON UPDATE | 조치 |
|---|---|---|
| `dcat_dataset_attr` | **CASCADE** | 자동 |
| `active_meta_dataset` | **CASCADE** | 자동 |
| `dcat_dataset_relation` (출발·도착) | **CASCADE** | 자동 |
| `meta_datagokr_file` | **CASCADE** | 자동 |
| `data_registry` | NO ACTION | **FK 재생성 필요** |
| `dcat_dataset_vec` | NO ACTION | **FK 재생성 필요** |
| `dcat_provenance` | **FK 없음** | ⚠️ **명시적 UPDATE 필요** — 아래 참조 |
| `dataset_credentials` | NO ACTION | **FK 재생성 필요** |
| `meta_video` | NO ACTION | **FK 재생성 필요** |
| `meta_news` / `blog` / `shopping` / `persona` | NO ACTION | **FK 재생성 필요** |

> ⚠️ **`dcat_provenance`는 FK를 제거했다**(2026-10-27, 별첨 공통 규약 "dcat_provenance 제외").
> 데이터셋 폐기 후에도 이력을 보존하기 위한 결정인데, 그 대가로 **dataset_id 변경이
> 전파되지 않는다.** URN 전환 시 이 테이블만 별도로 UPDATE해야 한다.
>
> ```sql
> UPDATE dcat_provenance p SET dataset_id = <urn>
>  WHERE p.dataset_id = <old_slug>;   -- dcat_dataset UPDATE와 같은 트랜잭션에서
> ```
> 순서 주의: FK가 없으므로 어느 쪽을 먼저 해도 제약 위반은 안 나지만, **빠뜨리면
> 조용히 끊어진 참조가 남는다.** 전환 후 아래로 확인한다.
> ```sql
> SELECT DISTINCT p.dataset_id FROM dcat_provenance p
>   LEFT JOIN dcat_dataset d USING (dataset_id) WHERE d.dataset_id IS NULL;
> ```

→ 우리 7개 FK에 `ON UPDATE CASCADE`를 먼저 부여하면 **`UPDATE dcat_dataset SET dataset_id=...`
한 번으로 DB 전체가 끝난다.** 구문은
[sql/migration_2026_10_27_wisenut_alignment.sql](../../sql/migration_2026_10_27_wisenut_alignment.sql) §A 참조.

### 2.2 오브젝트 스토리지 — FK가 못 따라오는 영역

`dataset_id`가 **경로에 박혀 있다.**
([architecture/06_Object_Storage_Format_Spec.md](../architecture/06_Object_Storage_Format_Spec.md))

```
raw/{source_type}/{dataset_id}/{item_key}.json
raw/{source_type}/{dataset_id}/{dataset_id}.csv
jsonld/{source_type}/{dataset_id}/{dataset_id}.jsonld
```

- 오브젝트 **복사 후 삭제**가 필요하다(S3에는 rename이 없다)
- 또는 **기존 경로를 그대로 두고** `data_registry.s3_raw_prefix` / `s3_jsonld_prefix`만
  유지하는 선택지도 있다 — 경로가 식별자와 일치할 필요는 없다.
  **이쪽이 비용이 훨씬 낮다.** 다만 신규 수집분부터 새 경로를 쓰면 경로가 두 세대로 갈린다

### 2.3 JSON-LD 문서 내용

이미 생성된 JSON-LD의 `@id`에 기존 식별자가 들어 있다.
→ 전량 재생성(`src/storage/jsonld_export.py`)이 필요하다. 원본 데이터는 그대로이므로
재생성 자체는 안전하고 비용도 낮다.

### 2.4 코드·설정·문서

| 위치 | 내용 |
|---|---|
| `sql/seeds.sql` | 샘플 데이터 6건의 `dataset_id` 리터럴 |
| `docs/**` | 예시로 쓰인 `dataset_id` 문자열 다수 |
| 운영 CLI | `python -m src.main run <dataset_id>` 호출 습관 |
| `dataset_credentials` | 자격증명이 `dataset_id`로 묶여 있음 |

### 2.5 외부 통보

~~**케이웨어가 이미 우리 `dataset_id`를 받아갔다면 변경 통보가 필요하다.**~~
→ **불필요.** 2026-10-28 기준 케이웨어와 연계된 것이 없어 통보 대상이 없다.
연계 이후에 전환했다면 양측 일정 조율이 필요했을 것이다.

---

## 3. 수행한 절차 (전부 완료, 2026-10-28)

1. ~~URN 생성 규칙 확정~~ — 2026-10-28 와이즈넛 승인
2. 우리 FK **8개**에 `ON UPDATE CASCADE` 부여
   (문서 초안에 7개로 적었으나 실측 8개 — `dataset_credentials`가 빠져 있었다)
3. **기존 slug를 `external_ids`에 보존** — 마이그레이션 §2에 포함돼 있다
   와이즈넛 형식('네임스페이스:값' 문자열 배열)을 그대로 지키고 자체 네임스페이스를 쓴다.
   ```json
   ["legacy:youtube_samsung_official"]
   ```
   객체(`{"legacy_slug": ...}`)가 아니라 **문자열 배열**이어야 한다. 포털 번호와 섞이지 않고,
   값이 데이터셋마다 유일해 와이즈넛의 중복 병합 판정에 오탐을 만들지 않는다.
   S3 경로를 유지하면 경로에도 slug가 남아 이중으로 추적된다.

4. 트랜잭션 안에서 `UPDATE dcat_dataset SET dataset_id = <urn>` (CASCADE 전파)
5. ~~`data_registry`의 `s3_*_prefix` 갱신~~ — **생략.** S3 경로를 유지하기로 했다
6. JSON-LD 재생성 (3건) — `@id`를 `mi:dataset/{slug}` → URN 자체로 바꿨다
7. `seeds.sql`·문서 예시 갱신
8. 와이즈넛에 전환 완료 통보 (케이웨어는 연계 없음)

> **순서 주의**: 3번(slug 보존)을 4번보다 먼저 해야 한다. 나중에 하면 원래 값을 잃는다.
> 실제로는 2026-10-27 `migration_2026_10_27_wisenut_alignment.sql`에서 이미 보존돼 있었다.

### 코드 변경 2건

**`scripts/register_dataset.py`** — 신규 등록이 다시 slug를 만들지 않도록 채번을
`urn:{네임스페이스}:{slug}_{랜덤}`으로 바꿨다. `--dataset-id` 직접 지정값도 URN 형식과
100자 상한을 검증한다. `origin`(admin/user)은 식별자에서 뺐다 — `dataset_origin`
컬럼이 이미 구분하고 있어 중복이고, 등록 주체가 바뀌면 식별자까지 흔들린다.

**`src/storage/s3_client.storage_key()`** — 오브젝트 키에는 `dataset_id` 대신 이
함수를 쓴다. 콜론은 S3 키에 쓸 수는 있지만 URL 인코딩·CLI 인용에서 걸린다.

```
urn:naver:news_ai → naver_news_ai     (urn: 제거 후 ':' → '_')
```

**이 변환 결과가 전환 전 slug와 같아서 기존 S3 경로가 그대로 유지된다.**
객체가 있는 경로 6개 전부 보존을 실측으로 확인했다. 유일한 예외
`user_hbm_video_collection` → `youtube_hbm_video_collection`은 객체가 0개다.

---

## 4. 전면 재구축과 함께 할 것인가

[sql/migration_2026_10_27_wisenut_alignment.sql](../../sql/migration_2026_10_27_wisenut_alignment.sql)
헤더에 적은 대로, 현재 DB에는 재생성 비용이 큰 데이터가 있다
(`active_meta_shopping_insight` 601일치 등 — 과거 관측값은 재수집으로 복원되지 않는다).

- **권장**: URN 전환도 `UPDATE` 기반으로 수행하고 데이터를 보존한다
- 전면 DROP → CREATE는 **수집 데이터를 버려도 되는 시점**에만 한다.
  그때 `seeds.sql`을 URN 형식으로 함께 갱신한다

---

## 5. 체크리스트

- [x] URN 생성 규칙 확정 — 2026-10-28 와이즈넛 승인
- [x] 케이웨어 전달 여부 확인 — **연계 없음, 통보 불필요**
- [x] 우리 FK **8개** `ON UPDATE CASCADE` 부여 → 13개 전부 CASCADE
- [x] `dcat_provenance.dataset_id` 명시적 UPDATE (41행) + 끊어진 참조 0건 확인
- [x] `external_ids`에 `legacy:<slug>` 보존 확인 — 18건 전부
- [x] S3 경로 정책 결정 — **유지** (`storage_key()`로 구현)
- [x] `UPDATE` 실행 — 드라이런(롤백) 검증 후 커밋, 32,209행 전파
- [x] JSON-LD 재생성 (3건)
- [x] `seeds.sql`·문서 예시 갱신
- [x] 정본 DDL 8종에 `ON UPDATE CASCADE` 반영 (`sql/` 재구축 시 DB와 일치)
- [x] `scripts/validate_ddl.py` 29/29, `check_insert_coverage.py` 누락 0

### 검증 결과 (마이그레이션 §D)

| 검사 | 결과 |
|---|---|
| D-1 전부 URN 형식 | 18/18 |
| D-2 건수 보존 | 18건 |
| D-3 `dcat_provenance` 끊어진 참조 | 0건 |
| D-4 자식 테이블 구 slug 잔존 | 0건 (8개 테이블 32,209행) |
| D-5 `legacy:` slug 보존 | 18/18 |
| D-6 길이 상한 | 최대 37자 / 100자 |

---

## 6. 채번 규칙 (신규 등록)

**`urn:{네임스페이스}:{source_type}_dataset_{랜덤접미}`**

```
뉴스    → urn:naver:news_dataset_a3f1c2
블로그   → urn:naver:blog_dataset_7d2e91
유튜브   → urn:youtube:dataset_5c81af        (youtube는 video 하나뿐)
```

`source_type`은 **네임스페이스가 그것을 결정하지 못할 때만** 붙인다.

| 네임스페이스 | 들어오는 source_type | 접두 |
|---|---|---|
| `youtube` | `video` 하나 | 없음 |
| `naver` | `news`·`blog`·`shopping_insight`·`persona_insight` 넷 | 있음 |

`naver`에 접두가 없으면 뉴스와 블로그를 식별자만 보고 구분할 수 없다.
판정은 `_SOURCE_META`에서 세므로, 한 네임스페이스에 source_type이 늘면
그때부터 자동으로 접두가 붙는다.

### 제목에서 키를 만들지 않는다 (2026-10-28 변경)

이전에는 `slugify(title)`을 썼는데 영문·숫자만 남기는 방식이라 결과를
예측할 수 없었다.

| 제목 | slugify | 결과 |
|---|---|---|
| `AI 관련 뉴스` | `ai` | `urn:naver:news_ai_b2989d` |
| `인공지능 뉴스` | `dataset` | `urn:naver:news_dataset_00fc83` |
| `반도체 HBM` | `hbm` | `urn:naver:news_hbm_5eab7d` |

**한글만 있는 제목은 전부 `dataset`으로 떨어져 어차피 의미가 없었고**, 영문
제목은 제목을 조금만 고쳐도 식별자 모양이 달라졌다. 의미는 `title` 컬럼이
들고 있으면 되고, 식별자는 유일하고 안정적이기만 하면 된다.

읽을 수 있는 키가 필요하면 `--dataset-id`로 직접 지정한다. 기존 18건이
`urn:naver:news_ai`, `urn:youtube:samsung_official`인 이유이고, 직접 지정한
값도 URN 형식과 100자 상한을 검증한다.

### `source_type`이 아니라 `source`를 네임스페이스에 두는 이유

[B2 과업](../NEXT_STEPS.md)의 완료 기준이 "YAML 추가만으로 신규 소스 수집"이다.
두 번째 뉴스 원천이 들어오면 `urn:news:ai`는 이미 점유돼 있어 `urn:news:daum_ai`
처럼 원천을 키로 밀어넣게 된다. `urn:naver:news_ai` 쪽은 그냥 `urn:daum:news_ai`로
늘어난다.

---

## 7. `external_ids` 정책

원천이 발급한 객체 키, 또는 수집 조건 집합의 해시를 `'네임스페이스:값'` 문자열
배열로 보존한다(와이즈넛 정의 형식). `dataset_id`는 수집 단위 키라서 중복 판정에
못 쓰는데, 이 컬럼이 그 역할을 한다.

| source_type | 값 | 예 |
|---|---|---|
| `video` | `youtube:{채널ID}` | `youtube:UCWwgaK7x0_FR1goeSRazfsQ` |
| 그 외 | `{source}:{source_type}:{집합해시}` | `naver:news:3c639c929baf` |

`legacy:{전환 전 slug}`는 18건 전부에 남아 있다.

### 왜 개별 값이 아니라 집합 해시인가

검색어·카테고리는 **원천 객체가 아니라 우리가 정한 수집 조건**이다. 개별 값을
그대로 넣으면 조건 하나만 겹쳐도 서로 다른 데이터셋이 중복으로 판정된다 —
실제로 `urn:naver:shopping_insight`와 `urn:naver:shopping_insight_advertiser`는
카테고리 `50000148`을 공유한다.

**집합 전체를 해시하면 완전히 같을 때만 겹친다.**

| 상황 | 개별 값 | 집합 해시 |
|---|---|---|
| 검색어 완전 일치 | 탐지됨 | **탐지됨** |
| 검색어 1개만 겹침 | **오탐** | 안 겹침 |

### 정규화 — 순서는 영향이 없다

```
공백 제거 → 소문자 → 중복 제거 → 코드포인트 정렬 → '|' 결합 → sha256 앞 12자리
```

```
['인공지능','AI','머신러닝','딥러닝']        → ai|딥러닝|머신러닝|인공지능 → 3c639c929baf
['AI','인공지능','딥러닝','머신러닝']        → 동일  (순서 흡수)
['ai',' 인공지능 ','AI','딥러닝','머신러닝'] → 동일  (대소문자·공백·중복 흡수)
['인공지능','AI','머신러닝']                 → ai|머신러닝|인공지능 → fdd75d65cbb0
```

원문은 `subjects` 컬럼에 그대로 남아 있어 해시는 언제든 다시 만들 수 있다.

> ⚠️ **정렬에 `COLLATE "C"`가 반드시 필요하다.** DB 기본 콜레이션은 한글을 영문보다
> 앞에 두어 파이썬 `sorted()`와 결과가 달라진다.
> ```
> SQL 기본      : 딥러닝|머신러닝|인공지능|ai
> SQL COLLATE C : ai|딥러닝|머신러닝|인공지능   ← 파이썬과 같음
> ```

> ⚠️ **sha1이 아니라 sha256을 쓴다.** PostgreSQL에 `sha256()`이 내장돼 있어 SQL에서도
> 같은 값을 만들 수 있다(`sha1`은 내장이 아니다). 두 구현이 같은 값을 내는지
> 마이그레이션에서 5건 전수 대조했다.

### 기간은 해시에 넣지 않는다

같은 검색어를 기간만 나눠 두 번 등록하면 해시가 같아진다 — **의도적이다.**
같은 대상을 보고 있다는 사실이 드러나야 하고, 기간이 다르다는 건 `temporal_*`
컬럼이 이미 말해준다.

### video는 왜 해시가 아닌가

채널 ID는 YouTube가 발급한 진짜 객체 키라 그대로 쓰면 된다. 채널 겹침은
**참 양성**이다 — `urn:youtube:hbm_video_collection`은 `samsung_official`·
`sk_hynix_official`과 같은 채널을 수집 중이고, 그 사실이 드러나는 것이 이
컬럼의 목적이다. 개별 영상 ID는 넣지 않는다(데이터셋의 원천 객체가 아니라 그
안의 항목이고 `meta_video`가 이미 들고 있다).

적용: [migration_2026_10_28_external_ids.sql](../../sql/migration_2026_10_28_external_ids.sql)(video),
[migration_2026_10_28_subject_hash.sql](../../sql/migration_2026_10_28_subject_hash.sql)(그 외)
신규 등록은 `register_dataset.make_external_ids()`가 같은 규칙으로 채운다.

---

## 8. 남은 것

- **와이즈넛 통보** — 전환 완료 사실과 URN 목록
- `active_meta_*` 테이블은 현재 0행이라 전파 확인이 불가능했다. 첫 수집 이후
  `dataset_id`가 URN으로 들어가는지 한 번 확인할 것
