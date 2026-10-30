# 벡터 테이블 형식 통합 제안 (모비젠 → 와이즈넛)

> **Date:** 2026-10-29
> **작성:** 모비젠
> **상태:** 제안 (협의 전)
> **대상:** `meta_datagokr_file_vec`(정형) / `dcat_dataset_vec`·`meta_*_vec`(비정형)

---

## 1. 배경 — 현재 두 형식이 다르다

| | 정형 `meta_datagokr_file_vec` | 비정형 `dcat_dataset_vec`·`meta_*_vec` |
|---|---|---|
| PK | `file_id` — **1건 = 1행** | `(키, chunk_index)` — **1건 = N행** |
| 벡터 | `summary_embedding` + `keywords_embedding` **2개 컬럼** | `embedding` **1개 컬럼** |
| 키워드 처리 | **평균 1벡터** | 본문에 합쳐 넣음 |
| HNSW | `summary_embedding`에 생성 | 데이터 축적 후 생성 예정 |

두 형식은 **서로 다른 목적에 최적화되어 있다.**

- 정형의 2벡터 분리는 **관계 계산**에 맞다. `relation_type_registry`의 `required_fields`가
  유형마다 다르기 때문이다 — `SEMANTICALLY_RELATED`는 `title·description`,
  `KEYWORD_OVERLAP`은 `keywords`, `COLUMN_NAME_SIMILAR`는 `column_names`를 본다.
  하나로 합치면 "주제는 유사하나 컬럼 구성은 다르다"를 구분할 수 없다.
- 비정형의 청킹은 **검색**에 맞다. 원문이 길고 주제가 섞여 통짜 임베딩이 실패했다
  (아래 §6 실측).

**따라서 어느 한쪽으로 맞추는 것은 옳지 않다.** 두 요구를 모두 담는 형식을 제안한다.

---

## 2. 제안 — 벡터를 '컬럼'이 아니라 '행'으로 나눈다

`vec_role` 컬럼을 추가하고 PK에 포함한다. 용도별 벡터는 **다른 행**으로 들어간다.

```sql
CREATE TABLE meta_datagokr_file_vec (

    file_id     TEXT NOT NULL
                REFERENCES meta_datagokr_file(file_id) ON DELETE CASCADE,

    vec_role    TEXT NOT NULL,
    -- 이 벡터의 용도. 'summary' | 'keyword' | 'column'

    chunk_index INTEGER NOT NULL,
    -- 역할 안에서 0부터. 쪼갤 필요가 없으면 0 한 행만 쓴다
    -- summary: 원문 분할 순서 · keyword/column: 항목 순서

    embedding   vector(768) NOT NULL,

    embed_text  TEXT NOT NULL,
    -- 이 벡터의 원본 텍스트. **모델 프리픽스는 제외하고 원문만 저장한다**
    -- (재현·디버깅, 증분 판정, 관계 evidence 기록에 쓴다)

    model_name  TEXT NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (file_id, vec_role, chunk_index),

    CONSTRAINT meta_datagokr_file_vec_role_check
        CHECK (vec_role IN ('summary', 'keyword', 'column'))
);

-- 역할별 부분 인덱스 — summary에만 만든다 (pgvector 0.8.4 / PostgreSQL 17 동작 확인)
CREATE INDEX idx_meta_datagokr_file_vec_summary
    ON meta_datagokr_file_vec USING hnsw (embedding vector_cosine_ops)
    WHERE vec_role = 'summary';

-- ⚠️ keyword·column 역할에는 HNSW를 만들지 않는다. 근거는 §7.
```

비정형 테이블도 같은 형태를 갖는다(키 컬럼만 다름).

### 역할 정의

| `vec_role` | 1행의 단위 | 정형 원문 | 비정형 원문 | 주 용도 |
|---|---|---|---|---|
| `summary` | 분할된 청크 | `table_summary` | 제목·설명·본문 | **검색**, `SEMANTICALLY_RELATED` |
| `keyword` | **키워드 1개** | 데이터셋 키워드 | 등록 시 입력한 키워드 | `KEYWORD_OVERLAP` 의미 보강 |
| `column` | **컬럼명 1개** | 컬럼 논리·물리명 | (해당 없음) | `COLUMN_NAME_SIMILAR` |

역할 어휘는 공유하되, 각 테이블은 해당하는 역할만 쓴다. 쓰지 않는 역할이 있어도
형식이 같으므로 **정형·비정형을 한 쿼리로 비교할 수 있다.**

---

## 3. 왜 '평균'이 아니라 '개별 행'인가

현재 정형 설계는 `keywords_embedding`을 **키워드 평균 1벡터**로 둔다(별첨: '컬럼명·키워드 평균').
이 방식에는 두 가지 제약이 있다.

**(1) 평균은 되돌릴 수 없다.** 개별 벡터를 저장해 두면 필요할 때 평균을 내면 되지만,
평균만 저장하면 개별을 복원할 수 없다. 저장 시점에 정보가 사라진다.

**(2) `meta_file_relation`을 채울 수 없다.** 합의된 테이블 정의는 다음과 같다.

```
meta_file_relation (source_file_id, source_column, target_file_id, target_column, ...)
```

`COLUMN_NAME_SIMILAR`는 "**어떤 컬럼이** 어떤 컬럼과 닮았는가"를 기록하도록 되어 있다.
평균 벡터로는 파일 쌍의 점수만 나올 뿐 `source_column`·`target_column`을 채울 수 없다.
컬럼 1개 = 1행이면 `embed_text`에 컬럼명이 그대로 있으므로 **매칭된 컬럼을 그대로 기록**할 수 있고,
`evidence` JSONB에 근거도 남는다.

### 행 수 증가에 대한 대비

컬럼 벡터는 파일당 컬럼 수만큼 늘어난다. `relation_type_registry`의
`COLUMN_NAME_SIMILAR` 설명이 이미 해법을 제시하고 있다.

> 컬럼 논리·물리명의 문자열·의미 유사도. **데이터셋 관계로 후보 쌍을 좁힌 뒤 산출**

따라서 `column` 역할은 **전수 생성하지 않는다.** `meta_datagokr_file.column_names`(JSONB,
GIN 인덱스 있음)로 문자열 기준 후보를 먼저 좁히고, 후보에 든 파일에만 벡터를 만든다.
`summary` 역할은 전수 생성한다.

---

## 4. 임베딩 모델 규약 (가장 중요한 합의 사항)

현재 DDL에 **"정형·비정형 임베딩 모델 통일 여부는 협의 미결"**로 남아 있다.
그런데 `SEMANTICALLY_RELATED`의 `applies_to`는 `["*"]` — **정형·비정형 교차 비교를 전제한다.**

**모델이 다르면 차원이 768로 같아도 벡터 공간이 달라 코사인 유사도가 무의미하다.**
오류가 발생하지 않고 그럴듯한 숫자가 나오기 때문에 더 위험하다.

모비젠은 다음을 제안한다. 선정 근거와 실측은 [ADR-016](../adr/016_Embedding_Model_And_Conventions.md)에 정리되어 있다.

| 항목 | 값 |
|---|---|
| 모델 | `intfloat/multilingual-e5-base` |
| 차원 | 768 (현 DDL과 동일, 변경 없음) |
| 거리 | 코사인 (`vector_cosine_ops`), L2 정규화 후 적재 |
| **프리픽스** | 문서 `passage: ` · 질의 `query: ` — **필수** |
| `model_name` | HuggingFace 식별자 전체를 그대로 기록 |
| `embed_text` | **프리픽스를 제외한 원문**을 저장 |

> ⚠️ **프리픽스 누락은 오류를 내지 않는다.** 검색 품질만 조용히 떨어지므로
> 적재 코드 리뷰 시 반드시 확인이 필요하다. e5 계열의 학습 방식상 필수 규약이다.

---

## 5. 검색 집계 규약

`summary` 역할이 여러 행으로 나뉘므로, 원본 1건의 점수를 정하는 규칙이 필요하다.

```sql
SELECT file_id, MAX(1 - (embedding <=> :query_vec)) AS score
FROM   meta_datagokr_file_vec
WHERE  vec_role = 'summary'
GROUP  BY file_id
ORDER  BY score DESC
LIMIT  20;
```

**평균이 아니라 최대값을 쓴다.** 긴 문서에서 질의와 맞는 청크가 1개이고 무관한 청크가
10개이면, 평균은 그 1개의 신호를 희석시켜 정답을 가라앉힌다.

---

## 6. 근거 실측 (모비젠, 2026-10-29)

동일 코퍼스 1,200건, 동일 조건에서 4가지 구성을 비교했다.

| 질의 | 이전 모델·통짜 | 이전 모델·청킹 | e5-base·통짜 | **e5-base·청킹** |
|---|---|---|---|---|
| 치질 수술 후 주의사항 | 8위 | 7위 | 3위 | **1위** |
| 위암 조기 진단 | 6위 | 4위 | 1위 | **1위** |
| HBM 고대역폭 메모리 | 1위 | 3위 | 2위 | **1위** |
| 대장내시경 검사 | 6위 | 1위 | 3위 | **2위** |

통제 실험에서는 더 분명하게 나타난다. 제목이 **글자까지 동일한** 문서를 질의로 넣었을 때,

- 통짜 임베딩: 코사인 **0.2257** (29,029건 중 17,449위)
- 청킹 후 최대값 집계: 코사인 **1.0000** (1위)

긴 문서를 통짜로 임베딩하면 짧은 질의와의 비대칭 때문에 유사도가 무너진다.
`table_summary`는 생성 요약이라 비정형 본문보다 짧고 단일 주제이므로 손해가 작지만,
같은 형식을 쓰면 길이가 길어질 때도 안전하다.

---

## 7. 규모·성능 검토 (실측 기반)

행이 늘어나는 설계이므로 용량과 인덱스 빌드 비용을 실측해 검증했다.
측정 환경: PostgreSQL 17.10 / pgvector 0.8.4, 모비젠 `meta_blog_vec`(104,211행) 사용.

### 7.1 행당 비용 — 실측

| 항목 | 실측값 |
|---|---|
| 테이블 본체 | **4,363 bytes/행** (vector(768) 3,080 + 행 오버헤드 + `embed_text`) |
| HNSW 인덱스 | **약 4,000 bytes/행** (20,000행·50,000행 두 번 모두 동일) |
| 합계 | **약 8.4 KB/행** |

### 7.2 규모 추정

파일 10만 건, 파일당 컬럼 20개, `table_summary` 300자(80자 청크 4개) 가정.

| 역할 | 행/파일 | 10만 파일 행수 | 본체 | HNSW |
|---|---:|---:|---:|---:|
| `summary` | 4 | 400,000 | 1.7 GB | **1.6 GB** |
| `keyword` | 5 | 500,000 | 2.2 GB | — |
| `column` (전수) | 20 | 2,000,000 | 8.7 GB | — |
| 합계 | 29 | 2,900,000 | **12.7 GB** | 1.6 GB |

현행 설계(파일 1행·벡터 2개)는 20만 벡터 0.6 GB이므로 **본체 기준 약 15배**다.
증가분의 **대부분(8.7 GB)이 `column` 역할**이다.

### 7.3 `keyword`·`column`에 HNSW를 만들지 않는 이유

ANN 인덱스는 **"전체에서 가까운 것을 찾는" 질의**에 필요하다.
`COLUMN_NAME_SIMILAR`는 그 형태가 아니다 — 레지스트리 정의대로
**데이터셋 관계로 후보 쌍을 좁힌 뒤** 산출하므로, 비교 대상이 한 번에 수십~수백 개다.
이 규모는 순차 스캔이 더 빠르고, 인덱스를 만들면 빌드·유지 비용만 든다.

→ HNSW는 `summary`에만 건다. **인덱스 총량이 11.6 GB → 1.6 GB로 줄어든다.**
`vec_role` 부분 인덱스(`WHERE vec_role = 'summary'`)라서 다른 역할의 행은
인덱스에 들어가지 않는다.

### 7.4 ⚠️ `maintenance_work_mem` — 빌드 전 반드시 올려야 한다

HNSW 그래프가 `maintenance_work_mem`에 들어가지 않으면 pgvector가 느린
디스크 경로로 전환한다. 서버 기본값 **64MB에서는 약 17,700행에서 이미 초과**한다.

```
NOTICE: hnsw graph no longer fits into maintenance_work_mem after 17702 tuples
DETAIL: Building will take significantly more time.
```

20,000행 동일 조건 실측:

| 설정 | 빌드 속도 | 메모리 초과 |
|---|---:|---|
| `maintenance_work_mem = 64MB` (기본) | 276 행/초 | **예** |
| `maintenance_work_mem = 1GB` | **484 행/초** | 아니오 |

초과 후에는 **데이터가 늘수록 더 나빠진다.** 같은 64MB 설정에서
20,000행은 276행/초였으나 50,000행은 **77행/초**로 떨어졌다(2.5배 데이터에 3.6배 저하).

`summary` 40만 행 기준으로는 `maintenance_work_mem`을 **2GB 이상**으로 두면
초과 없이 약 14분에 빌드된다. 기본값 그대로 두면 수 시간 단위가 된다.

> 측정 한계: 병렬 빌드(`max_parallel_maintenance_workers`)는 임시 테이블에
> 병렬 워커를 붙일 수 없어 이번 측정에서 효과가 나타나지 않았다(1GB 단독 484행/초,
> 1GB+워커4 496행/초). 실제 테이블에서는 추가 개선이 기대되나 **미검증**이다.

### 7.5 결론

| 구성 | 본체 | HNSW | 합계 |
|---|---:|---:|---:|
| 현행(1행 2벡터) | 0.6 GB | 0.8 GB | 1.4 GB |
| 제안 + `column` 전수 + 전 역할 인덱스 | 12.7 GB | 11.6 GB | **24.3 GB** |
| **제안 + `column` 후보만(10%) + summary만 인덱스** | 4.8 GB | 1.6 GB | **6.4 GB** |

**세 번째 구성을 제안한다.** 현행 대비 약 4.6배이며, 검색 품질과 관계 계산
양쪽을 얻는 대가로 수용 가능한 범위로 판단한다.

운영 조건 두 가지를 전제로 한다.

1. `column` 역할은 **전수 생성하지 않는다** — `column_names`(JSONB, GIN 인덱스)로
   후보를 좁힌 뒤 해당 파일에만 생성
2. HNSW 빌드 시 `maintenance_work_mem`을 **2GB 이상**으로 설정

---

## 8. 전환 비용

| 주체 | 작업 | 비용 |
|---|---|---|
| 와이즈넛 | DDL 교체 + 적재 코드에서 2컬럼 UPSERT → 역할별 행 INSERT | **`meta_datagokr_file`·`meta_datagokr_file_vec` 모두 현재 0건**이므로 데이터 마이그레이션 없음 |
| 모비젠 | `vec_role` 컬럼 추가, 기존 행 `'summary'`로 설정, PK 재정의 | 기존 **160,142행 유지**, 원문이 같으므로 **재임베딩 불필요** |

```sql
-- 모비젠 측 마이그레이션 (4개 테이블 동일 패턴)
ALTER TABLE meta_video_vec ADD COLUMN vec_role TEXT NOT NULL DEFAULT 'summary';
ALTER TABLE meta_video_vec DROP CONSTRAINT meta_video_vec_pkey;
ALTER TABLE meta_video_vec ADD PRIMARY KEY (meta_id, vec_role, chunk_index);
ALTER TABLE meta_video_vec ALTER COLUMN vec_role DROP DEFAULT;
```

적재 전인 지금이 전환 비용이 가장 낮은 시점이다.

---

## 9. 검토한 대안과 미채택 근거

| 대안 | 내용 | 미채택 사유 |
|---|---|---|
| A | 비정형을 정형 형식(1행 2컬럼)에 맞춘다 | 청킹을 포기해야 한다. §6 실측대로 검색이 무너진다 |
| B | 정형을 비정형 형식(1벡터 청킹)에 맞춘다 | 축 분리가 사라져 `COLUMN_NAME_SIMILAR`·`KEYWORD_OVERLAP`을 구분할 수 없다 |
| C | 형식은 그대로 두고 모델만 통일한다 | 교차 비교는 가능하나 조회 쿼리를 두 벌 유지해야 한다. **차선책으로 유효** |
| **제안** | `vec_role` 행 분리 | 검색·관계 양쪽을 만족. 역할 추가 시 `ALTER TABLE`이 불필요 |

**최소한 C(모델 통일)는 반드시 필요하다.** 제안이 수용되지 않더라도 §4는 별도로 합의해야 한다.

---

## 10. 협의가 필요한 사항

1. `vec_role` 방식 채택 여부 (미채택 시 대안 C로 진행)
2. **임베딩 모델·프리픽스 규약 확정** — 교차 관계 계산의 전제
3. `vec_role` 허용값 — 제안은 `summary` / `keyword` / `column` 3종
4. `column` 역할의 후보 선별 기준 — **전수 생성하지 않는 것이 전제다**(§7.5)
5. HNSW는 `summary`에만 생성, 빌드 시 `maintenance_work_mem` 2GB 이상 (§7.4)
6. 정형 `table_summary` 생성 주체·방식 (모비젠 미확인 사항)
