# dataset_id URN 전환 — 영향 범위와 절차

> **Last Updated:** 2026-10-27
> **상태:** ⏳ URN 생성 규칙 확인 대기 (와이즈넛 질의 중)
>
> 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서는 `dataset_id`를
> **TEXT 최대 100자 URN**, 케이웨어 `cetus_*.metadata_id`와 **동일 값**으로 규정한다.
> 현재 우리 값은 slug 형식이라 전환이 필요하다. 착수 전 이 문서로 범위를 확정한다.

---

## 1. 현재 상태

| 항목 | 값 |
|---|---|
| 데이터셋 수 | 18건 |
| 형식 | slug (`naver_news_ai`, `youtube_samsung_official`, `user_hbm_video_collection`) |
| 최대 길이 | 33자 (스펙 상한 100자 — 여유 있음) |
| URN 접두 사용 | **0건** |

**발급 주체는 우리다.** 케이웨어가 우리 `dataset_id`를 받아가는 구조이므로,
외부에서 ID를 받아와 맞추는 것이 아니라 **우리가 정한 값을 URN 형식으로 바꾸면 된다.**
→ 마이그레이션 난이도가 크게 낮아진다. 값 자체의 의미는 보존할 수 있다.

**남은 질의**: URN 생성 규칙(네임스페이스·구분자·소스 표기 방식).

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
| `meta_youtube_video` | NO ACTION | **FK 재생성 필요** |
| `meta_naver_news` / `blog` / `shopping` / `persona` | NO ACTION | **FK 재생성 필요** |

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

**케이웨어가 이미 우리 `dataset_id`를 받아갔다면 변경 통보가 필요하다.**
전환 시점을 양측과 맞춰야 한다.

---

## 3. 권장 절차

1. **URN 생성 규칙 확정** (와이즈넛 질의 회신 대기)
2. 우리 FK 8개에 `ON UPDATE CASCADE` 부여
3. `external_ids`에 기존 slug 보존 — 이미 마이그레이션 §2에 포함돼 있다
   ```json
   {"legacy_slug": "youtube_samsung_official"}
   ```
4. 트랜잭션 안에서 `UPDATE dcat_dataset SET dataset_id = <urn>` (CASCADE 전파)
5. `data_registry`의 `s3_*_prefix` 문자열 갱신 — **경로를 바꾸지 않기로 하면 생략**
6. JSON-LD 전량 재생성
7. `seeds.sql`·문서 예시 갱신
8. 케이웨어·와이즈넛에 전환 완료 통보

> **순서 주의**: 3번(slug 보존)을 4번보다 먼저 해야 한다. 나중에 하면 원래 값을 잃는다.

---

## 4. 전면 재구축과 함께 할 것인가

[sql/migration_2026_10_27_wisenut_alignment.sql](../../sql/migration_2026_10_27_wisenut_alignment.sql)
헤더에 적은 대로, 현재 DB에는 재생성 비용이 큰 데이터가 있다
(`active_meta_naver_shopping` 601일치 등 — 과거 관측값은 재수집으로 복원되지 않는다).

- **권장**: URN 전환도 `UPDATE` 기반으로 수행하고 데이터를 보존한다
- 전면 DROP → CREATE는 **수집 데이터를 버려도 되는 시점**에만 한다.
  그때 `seeds.sql`을 URN 형식으로 함께 갱신한다

---

## 5. 체크리스트

- [ ] URN 생성 규칙 확정
- [ ] 케이웨어 전달 여부 확인 (이미 받아갔으면 통보 일정 협의)
- [ ] 우리 FK 7개 `ON UPDATE CASCADE` 부여 (dcat_provenance 제외 — FK 없음)
- [ ] `dcat_provenance.dataset_id` 명시적 UPDATE + 끊어진 참조 확인
- [ ] `external_ids`에 legacy_slug 보존 확인
- [ ] S3 경로 정책 결정 (유지 / 이전)
- [ ] `UPDATE` 실행 (트랜잭션, 롤백 가능 상태에서)
- [ ] JSON-LD 재생성
- [ ] `seeds.sql`·문서 예시 갱신
- [ ] `scripts/compare_wisenut_spec.py` 재실행으로 정합성 확인
