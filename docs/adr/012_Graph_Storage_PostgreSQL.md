# ADR 012: 관계 그래프 저장 — 와이즈넛 합의 스키마 재사용 + NetworkX 분석

> **Date:** 2026-10-27
> **Status:** Accepted
> **개정:** 2026-10-27 — 초안은 `dcat_relation` 신규 테이블을 설계했으나,
> 와이즈넛과 합의된 `dcat_dataset_relation`이 이미 존재함을 확인하고 전면 교체했다.

---

## 배경

연구개발계획서 1차년도 "데이터 패턴 모델링 기반 관계 분석", 2차년도 "액티브 메타데이터 기반
네트워크 생성 및 분석 모듈(모비젠)" 과업을 구현하려면 관계(엣지)를 저장·조회·분석해야 한다.

초안 작성 시점에는 신규 테이블 `dcat_relation`을 설계했으나, 실제 DB 점검 결과
**와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서에 따른 `dcat_dataset_relation`이
이미 생성되어 있었다.** 협의가 끝난 공용 스키마를 우리가 임의로 대체할 수 없다.

## 결정

### 1. 저장은 `dcat_dataset_relation`을 그대로 쓴다

신규 테이블을 만들지 않는다. 합의 스키마가 필요한 기능을 이미 갖추고 있다.

| 요구 | 합의 스키마의 대응 |
|---|---|
| 규칙·임베딩·모델 산출 구분 | `method` (rule / embedding / llm) |
| 제안 → 승인 흐름 | `status` (PENDING / APPROVED / REJECTED) |
| 판정 근거 보존 | `evidence` JSONB |
| 유형 확장 | `relation_type` 문자열 + `relation_type_registry` FK |
| 데이터셋 폐기 시 정리 | `ON DELETE CASCADE` |
| dataset_id URN 전환 | `ON UPDATE CASCADE` (자동 전파) |

### 2. `relation_type`은 `relation_type_registry`의 표준값만 쓴다

FK로 묶여 있어 **등록되지 않은 유형은 INSERT 자체가 불가능하다.**
2026-10-27 기준 등록된 8종 중 **비정형(`applies_to=["*"]`)에 적용 가능한 것은 2종뿐**이다.

| relation_type | 판정 근거 | 비정형 적용 |
|---|---|---|
| `SEMANTICALLY_RELATED` | 제목·설명 임베딩 코사인 유사도 | ✅ |
| `KEYWORD_OVERLAP` | 키워드 집합 자카드 계수 | ✅ |
| `ADJACENT_TO` / `DETAIL_FOR` / `SAME_KIND` / `STATISTIC_FOR` / `COLUMN_NAME_SIMILAR` / `TIMESERIES_SUCCESSOR` | 정형 컬럼 구조·수록기간 기반 | ❌ `["structured_file"]` 전용 |

→ **비정형 관계 분석의 최소선은 이 2종으로 구성한다.**
초안에서 설계했던 `entity_shared`(개체 공유)와 `temporal_comovement`(시계열 공변동)는
표준값에 없다. 추가 가능하다는 회신을 받았으므로 **registry 등록을 먼저 제안**한 뒤 쓴다.

### 3. 규칙 엣지와 모델 엣지는 같은 유형으로 공존할 수 없다

합의 스키마의 UNIQUE는 `(source_dataset_id, target_dataset_id, relation_type)`이다.
**쌍+유형당 1행이고 재생성 시 대체**된다. 초안에서 설계했던
"`method_version`을 UNIQUE에 넣어 규칙·모델 엣지를 동시 보관"은 성립하지 않는다.

따라서 "규칙만 그래프 / 규칙+모델 그래프"를 비교하려면 둘 중 하나다.

- **relation_type을 분리**한다 (예: 모델 산출용 유형을 registry에 별도 등록)
- `evidence`에 이전 산출 이력을 누적한다

**전자(유형 분리)를 채택한다.** 유형 추가가 가능하다는 회신을 받았다(2026-10-27).

접미 `_MODEL` 규약을 쓴다 — 예: 규칙 산출은 `SEMANTICALLY_RELATED`,
모델 산출은 `SEMANTICALLY_RELATED_MODEL`. 같은 의미축을 유지하므로
**두 그래프를 같은 기준으로 비교**할 수 있다.
제안 DDL은 [sql/relation_type_registry.sql](../../sql/relation_type_registry.sql) 하단 주석 참조.

재생성 시 `method='rule'` 행만 선택적으로 교체하는 운용도 UNIQUE 때문에 불가능하므로,
**재계산 범위를 relation_type 단위로 관리**한다 — 규칙 유형만 재계산하고 모델 유형은 건드리지 않는다.
(초안에서 "만료 처리를 `origin='rule'`로 한정"이라 했던 것이 이 구조에서는 유형 단위로 바뀐다.)

### 4. 그래프 분석 지표는 `active_meta_dataset`에 적재한다

초안의 `dcat_graph_metric` 신규 테이블을 철회한다.
`active_meta_dataset`(EAV, `metric_code` + `metric_value` + `observed_at`)이 이미 있고,
그래프 지표도 "특정 시점의 데이터셋 단위 수치"라는 점에서 구조가 맞는다.

- 신규 `metric_code` 3종을 `metric_registry`에 등록 제안: `graph_degree`, `graph_pagerank`,
  `graph_community_id` — 제안 DDL은 [sql/metric_registry.sql](../../sql/metric_registry.sql) 하단 주석 참조
- `observed_at`에 그래프 산출 실행 시각을 넣으면 **시점별 네트워크 변화**를 그대로 얻는다
- ⚠️ 의미상 유의: 이 테이블은 본래 "관측값"을 담고 그래프 지표는 "분석 산출물"이다.
  구조는 맞지만 성격이 다르므로 `source` 컬럼에 산출 주체를 명시해 구분한다

### 5. 분석은 NetworkX로 하고 상태를 두지 않는다

**PostgreSQL이 진실원천, NetworkX는 일회성 연산 엔진**이다.
엣지 적재 → 지표 계산 → `active_meta_dataset` 기록 → 그래프 객체 폐기.

- python-igraph 대신 NetworkX — 이 규모에서 성능 차이는 체감되지 않고,
  **순수 Python 의존성(C 확장 없음)** 이 온프레미스 이미지 빌드에서 더 큰 가치를 갖는다
- Louvain은 **`seed` 고정 필수** — 시드마다 결과가 달라진다
- 동일 쌍에 여러 `relation_type`이 있을 때 **가중치 합성 규칙(max)을 명시·문서화**한다.
  합산하면 관계 종류가 많은 쌍이 과대평가된다
- 다중 홉 탐색은 재귀 CTE로 하되 방어 4종을 전부 적용한다:
  ① 깊이 상한을 재귀항 안에 ② 누적 가중치 곱셈 감쇠 컷 ③ 약한 엣지 선차단
  ④ `CYCLE ... SET ... USING path` (유사도 그래프는 사이클 투성이이고,
  `depth` 컬럼이 들어가는 순간 `UNION` 중복 제거는 무효가 된다)

### 6. 그래프 데이터베이스는 도입하지 않는다

> 본 과제의 관계 그래프는 생성되는 엣지 수가 수십만 건 이하이다. 이 규모에서는 관계형
> 데이터베이스의 인덱스 탐색과 재귀 CTE만으로 다중 홉 탐색 성능이 충분히 확보되며, 별도
> 그래프 데이터베이스 도입 시 발생하는 이중 적재 파이프라인·동기화 지연·운영 부담이 성능
> 이득을 상회한다. 또한 관계 정보를 메타데이터 카탈로그(DCAT)와 동일한 PostgreSQL
> 인스턴스에 보관함으로써 참조 무결성을 외래키 제약으로 직접 보장할 수 있다.

**재검토 조건**: 엣지 100만 건 초과, 또는 실시간 가변 길이 경로 질의가 상시 워크로드가 될 때.
(NetworkX 한계: ~10만 엣지는 전 지표 수 초. ~100만에서 betweenness는 O(V·E)로 사실상 불가.)

## 전제가 바뀐 부분 — 품질이 상한선이다

2026-10-27 실측에서 `SEMANTICALLY_RELATED`의 입력인 `dcat_dataset.description`이
video 13건 중 11건에서 50자 미만(평균 25자)이었다. 자동 수집·등록이 아직 없어
임의 샘플만 들어간 상태이긴 하나, **등록 규칙에 설명 품질 기준이 없으면 자동화 후에도
같은 문제가 남는다.** `relation_type_registry.required_fields`가 비어 있는 데이터셋은
해당 관계가 아예 산출되지 않는다.

→ 관계 분석 착수 전 **데이터셋 등록 시 `description`·`keywords` 최소 품질 기준**을 둔다.

## 참고

- [development/04_Implementation_Methods.md](../development/04_Implementation_Methods.md) §3 B2·B3·B4
- [sql/dcat_dataset_relation.sql](../../sql/dcat_dataset_relation.sql)
- [sql/relation_type_registry.sql](../../sql/relation_type_registry.sql)
