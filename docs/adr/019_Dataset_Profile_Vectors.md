# ADR 019: 데이터셋 관계용 벡터 — `vec_role` 확장

> **Date:** 2026-11-02
> **Status:** Proposed (초안 · 와이즈넛 협의 필요)
> **선행:** [vec_schema_unification_proposal.md](../database/vec_schema_unification_proposal.md)
> (2026-10-29, 미발송) — 이 ADR은 그 제안을 **대체하지 않고 확장한다.**

---

## 배경

B2(패턴 모델링 기반 관계 분석)는 **데이터셋 간 유사도**를 내야 한다. 합의된
`relation_type_registry`에 비정형에 쓸 수 있는 관계가 2종 있다.

| relation_type | applies_to | 별첨이 정한 산출 방식 |
|---|---|---|
| `SEMANTICALLY_RELATED` | `['*']` | 제목·설명 임베딩(`dcat_dataset_vec`)의 코사인 |
| `KEYWORD_OVERLAP` | `['*']` | 키워드 집합의 **자카드 계수** |

**둘 다 현재 구조로는 산출할 수 없다.** 2026-11-02 실측 3건으로 확인했다.

### 측정 1 — 청크 최대 유사도로는 데이터셋 관계를 못 낸다

`dcat_dataset_vec`는 2026-10-29에 1:N 청킹으로 바뀌었다. 검색(질의↔문서)에는
청크 최대 유사도가 맞지만, 관계(문서↔문서)에 쓰면 m×n 청크 쌍 중 **가장 비슷한
한 쌍**을 고르게 된다. 데이터셋 300쌍을 실제로 쟀다.

```
최대 0.9921   중앙 0.9189   최소 0.8922
  >= 0.90 : 286쌍 (95%)      >= 0.85 : 300쌍 (100%)
```

가장 무관한 쌍(`양자컴퓨팅 뉴스 ↔ 패션 전체 페르소나`)이 0.8945다.
**어떤 고정 임계값도 전부 연결하거나 전부 끊는다.**
[ADR-018](018_Search_Relevance_Judgment.md)이 검색에서 측정한 e5 점수 압축과 같다.

### 측정 2 — 자카드는 관계를 거꾸로 매긴다

```
자카드 0.000   패션의류 검색 트렌드  ↔  패션 전체 검색 트렌드    공유 없음
자카드 0.200   전기차 충전 블로그    ↔  캠핑 장비 주간 블로그    공유: 가격 공간 디자인 배터리
```

원인 셋 — ① 어휘가 다르면 못 잡는다(`의류`와 `패션`은 집합 연산에서 남남)
② 집합 크기에 휘둘린다(키워드 1~2개끼리는 자카드 **1.000**, 20개 이상끼리는 최대 0.444)
③ 일반어 공유로 거짓 엣지가 선다.

### 측정 3 — B1이 키워드 입력을 고쳤다

| | 등록 키워드 | [B1](../../src/analysis/features/) 집계 키워드 |
|---|---|---|
| 데이터셋당 | 1~4 (중앙 3) | 1~30 (중앙 30) |
| 엣지 | 22/300 (7.3%) | **42/300 (14.0%)** |
| 고립 노드 | **10/25** | **1/25** |

**입력은 고쳐졌고, 남은 것은 비교 방식(자카드)과 저장 구조(청킹)다.**

---

## 결정

**새 테이블을 만들지 않는다.** [2026-10-29 제안](../database/vec_schema_unification_proposal.md)의
`vec_role` 체계를 그대로 쓰고, **역할 2종의 정의만 비정형 쪽으로 확장한다.**

처음에는 와이즈넛 `meta_datagokr_file_vec`을 본떠 `summary_embedding`/
`keywords_embedding` **2컬럼 1:1 테이블**을 제안하려 했으나, 그것은 우리 제안서가
명시적으로 반대하는 설계다 — 평균 벡터는 되돌릴 수 없고, 개별 키워드를 기록할 수
없어 `evidence`에 "어떤 키워드가 매칭됐는지"를 남기지 못한다.

### 역할 정의 확장

| `vec_role` | 1행의 단위 | 비정형 원문 | 용도 |
|---|---|---|---|
| `summary` | 분할된 청크 | 제목·설명·본문 | **검색** (현행 그대로) |
| **`profile`** | 분할된 청크 | **B1 `representative_text`** | `SEMANTICALLY_RELATED` |
| `keyword` | **키워드 1개** | ~~등록 키워드~~ → **B1 `top_keywords`** | `KEYWORD_OVERLAP` |

**`profile`을 새로 둔다.** 제안서의 `summary`는 비정형에서 "제목·설명·본문" 청크,
즉 **검색 채널**이다. 측정 1대로 그걸 관계에 쓰면 300쌍이 전부 0.89~0.99로 뭉친다.
관계에는 **아이템에서 집계한 데이터셋 대표 텍스트**가 따로 필요하다.

정형은 `table_summary`가 짧고 단일 주제라 `summary` 하나로 두 용도를 겸할 수 있다.
비정형은 데이터셋 하나에 아이템이 수천 건이라 겸할 수 없다 — 이것이 정형·비정형의
실질적 차이다.

**`keyword`의 입력을 등록 키워드에서 B1 집계 키워드로 바꾼다.** 측정 3의 근거다.
등록 키워드는 사람이 손으로 적은 2~3개라 그래프가 서지 않는다.

### 입력은 B1 산출물이다

| 역할 | 입력 | 왜 등록 메타데이터가 아닌가 |
|---|---|---|
| `profile` | `meta_feature.representative_text` | 등록 `description`이 평균 **24~36자**다. 한 줄 제목이라 요약의 입력이 못 된다 |
| `keyword` | `meta_feature.top_keywords` | 등록 `keywords`가 평균 **2~3개**다 |

`representative_text`는 **추출 요약**이다 — 상위 키워드가 가장 조밀한 청크를 고른다.
[ADR-013](013_No_External_LLM_API.md)이 외부 LLM을 금지했고 "LLM이 없어도 기능이
성립해야 한다"가 원칙이다. hallucination이 없고 원문 추적이 되는 것은 덤이 아니라
과제 산출물의 근거가 된다.

### 관계 산출 규칙

- **고정 임계값을 쓰지 않는다.** 측정 1대로 어떤 값도 틀린다. **상위 K**만 남긴다.
- 두 축의 점수를 합치지 않고 **따로** `dcat_dataset_relation`에 넣는다.
  `relation_type`이 다르므로 별개 행이다.
- `evidence`에 **어떤 키워드가 매칭됐는지**를 담는다. 개별 키워드가 행으로 있어야
  가능하고, 이것이 2컬럼 평균 방식을 버린 이유다.
- `method`에 산출 방식과 토크나이저 버전을 적는다
  (`tfidf/kiwi-0.24.1+model-0.24.0+pos1`). 토크나이저가 바뀌면 키워드가 통째로
  달라져 이 벡터도 다시 만들어야 한다.

### 마이그레이션

제안서 §8의 `vec_role` 전환에 역할 2종이 추가될 뿐이다. 기존 163,407행은
`vec_role='summary'`로 그대로 유지되고 **재임베딩이 필요 없다.**

---

## 와이즈넛에 회신할 4건

1. **`vec_role` 행 분리 채택 여부** (제안서 §10-1, 미발송분)
2. **`KEYWORD_OVERLAP`의 산출을 자카드 → 키워드 임베딩 코사인으로.** 측정 2가 근거다.
   `required_fields`는 `keywords` 그대로이고 비교 방식만 바뀐다.
3. **`SEMANTICALLY_RELATED`가 가리키는 `dcat_dataset_vec`는 1:N 청크 테이블이다.**
   데이터셋 대표 벡터가 아니다 — 별첨의 근거를 `vec_role='profile'`로 정정해야 한다.
4. **`vec_role` 허용값에 `profile` 추가** (제안서는 `summary`/`keyword`/`column` 3종)

## 한계 — 지금 채워도 절반은 비어 있다

**텍스트 특징이 서는 데이터셋은 25개 중 15개뿐이다.** shopping_insight·
persona_insight 10개는 아이템이 "카테고리"라 본문이 없어 B1 키워드가 1~2개에 그친다.
이들의 관계는 텍스트가 아니라 **시계열 공변동**으로 잡아야 하는데, 발견형 소스의
관측일이 **1일**뿐이라 지금은 불가능하다 — **P0-7(수집 재개)이 선행**이다
([metadata_quality_probe.md](../database/metadata_quality_probe.md)).

이 ADR로 만드는 것은 **비정형 텍스트 축의 관계**까지다.

## 재검토 조건

- 정형 데이터(`meta_datagokr_file`)가 적재되어 `column` 역할이 실제로 쓰일 때
- 데이터셋이 수백 개로 늘어 상위 K 대신 임계값을 쓸 수 있게 될 때
  (지금은 25개라 점수 분포 통계를 신뢰할 수 없다)
- 와이즈넛이 위 4건에 회신할 때

## 참고

- [vec_schema_unification_proposal.md](../database/vec_schema_unification_proposal.md) — 이 ADR의 전제
- [ADR-018](018_Search_Relevance_Judgment.md) · [ADR-010](010_Korean_Fulltext_Search.md) · [ADR-013](013_No_External_LLM_API.md)
- [database/metadata_quality_probe.md](../database/metadata_quality_probe.md) — 측정 원본
