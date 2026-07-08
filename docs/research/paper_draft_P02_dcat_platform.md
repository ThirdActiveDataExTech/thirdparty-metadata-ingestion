# 논문 초안: DCAT 2.0 기반 이종 웹 데이터 통합 메타데이터 플랫폼

> 기반 기획서: [research_proposals.md](./research_proposals.md) P02
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 사용자 실험/측정 후 수치로 교체
> 목표 분량: 6페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)
>
> 이 초안은 기획서 P02의 내용(연구 필요성, 관련 연구, 설계 핵심 결정사항, 사용자
> task 기반 평가 실험, 평가 방법)을 논문 형식으로 재구성한 것이다. 기획서의
> "구현 난이도: ★☆☆☆☆ — 이미 구현된 시스템을 평가·정리하는 작업이 핵심"이라는
> 서술에 따라, 플랫폼 설계/구현 방법론 자체는 새로 고안하지 않았고 기획서 내용을
> 그대로 옮겼다. 사용자 실험 설계만 기획서의 뼈대(개발자 5명 이상, 10개 과제,
> 조건 A/B)를 구체화했다.

---

## 제목 (Title)

**영문:** *A DCAT 2.0-Based Metadata Platform for Heterogeneous Web Data Sources: Design, Implementation, and Evaluation*

**국문:** DCAT 2.0 기반 이종 웹 데이터 통합 메타데이터 플랫폼: 설계, 구현 및 평가

---

## Abstract

Data catalog systems built on the W3C Data Catalog Vocabulary (DCAT) have been applied
almost exclusively to static, file-based open government data portals. It remains
unclear whether — and how — DCAT 2.0 can be systematically applied to heterogeneous,
continuously-updated web API data such as video platforms, news aggregators, and
e-commerce trend feeds, whose structure, update cadence, and collection method differ
fundamentally from portal datasets. We present the design and implementation of a
DCAT 2.0-based metadata platform that (1) separates static metadata from time-series
operational statistics via a `meta_*` / `active_meta_*` table pattern, (2) enforces a
one-dataset-one-source-type boundary to prevent schema drift, (3) tracks collection
provenance through per-run insert logging, and (4) supports two-level (dataset-level and
item-level) vector semantic search. The platform is deployed on PostgreSQL and Kubernetes
and operates over `[DATA: 4]` heterogeneous web data sources comprising approximately
`[DATA: 60,000]` records. We evaluate the platform against raw SQL access, keyword search,
and CKAN through a task-based user study with `[DATA: N ≥ 5]` developers performing
`[DATA: 10]` realistic data-exploration tasks under two conditions (platform vs. raw
table access), and report task completion time, DCAT attribute coverage, vector search
response latency, and search Precision@5.

**국문 초록 (draft):** DCAT(Data Catalog Vocabulary)은 공공 데이터 포털 중심으로
적용되어 왔으며, YouTube·뉴스·쇼핑 트렌드처럼 구조·갱신 주기·수집 방식이 전혀 다른
이종 웹 API 데이터에 DCAT 2.0을 체계적으로 적용한 사례는 거의 없다. 본 연구는 (1)
정적 메타데이터와 시계열 운영 통계를 `meta_*` / `active_meta_*` 테이블로 분리하고,
(2) 1 dataset = 1 source_type 원칙으로 스키마 충돌을 방지하며, (3) 매 수집 실행마다
`dcat_provenance`에 이력을 적재하고, (4) 데이터셋 레벨·아이템 레벨 2단계 벡터 의미
검색을 지원하는 DCAT 2.0 기반 메타데이터 플랫폼을 설계·구현했다. PostgreSQL +
Kubernetes 환경에서 실제 운영 중인 `[DATA: 4]`종 이종 웹 데이터 소스, 약
`[DATA: 60,000]`건을 대상으로 raw SQL, 키워드 검색, CKAN과 비교하는 사용자 task
기반 실험(개발자 `[DATA: N ≥ 5]`명, 10개 탐색 과제, 조건 A/B)을 수행하고 과제 완료
시간, DCAT 속성 커버리지, 벡터 검색 응답 시간, 검색 Precision@5를 측정한다.

**Keywords:** DCAT 2.0, data catalog, metadata platform, heterogeneous web data,
provenance tracking, vector semantic search, data discoverability

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

DCAT(Data Catalog Vocabulary)은 공공 데이터 포털 중심으로 적용되며, YouTube·뉴스·
쇼핑 트렌드처럼 **구조·갱신 주기·수집 방식이 전혀 다른 이종 웹 API 데이터에 DCAT
2.0을 체계적으로 적용한 사례**는 거의 없다. CKAN, DataHub 같은 오픈소스 카탈로그는
정적 파일 기반 데이터에 최적화되어 있어, 실시간으로 수집·갱신되는 웹 데이터에
그대로 적용하기 어렵다. 구체적으로 두 가지 문제가 있다.

첫째, 공공 데이터 포털의 배포 모델은 "한 번 게시되면 거의 바뀌지 않는 파일"을
전제로 한다. 반면 YouTube 조회수, 뉴스 트렌드, 쇼핑 순위 같은 데이터는 매일, 심지어
매시간 갱신되며 이력 자체가 분석 대상이다. 이런 시계열 누적 통계를 DCAT의 정적
`Distribution` 모델에 그대로 얹으면 갱신 이력이 소실되거나 스키마가 무한히 확장된다.

둘째, 서로 다른 API에서 오는 데이터를 하나의 카탈로그로 통합하려면 스키마 충돌과
수집 이력 추적이라는 운영상의 문제를 해결해야 한다. 어떤 데이터셋이 어느 API에서,
언제, 어떤 조건으로 수집되었는지 추적하지 못하면 오류 원인 분석이나 API 한도 소진
감지 같은 실무적 요구를 충족할 수 없다.

### 1.2 연구 질문

> "DCAT 기반 플랫폼이 없는 경우(raw 테이블 직접 사용)와 비교해 데이터 탐색 효율과
> 메타데이터 품질이 실질적으로 향상되는가?"

### 1.3 기여점 (Contributions)

1. DCAT 2.0 핵심 클래스(`dcat:Dataset`, `dcat:Distribution`, `dcat:DataService`)의
   웹 API 데이터 매핑 규칙 제안 및 매핑 불가 속성에 대한 확장 어휘 정의
   (`[DATA: 확장 어휘 수, 제안서 목표: 15개 이상]`)
2. 정적 메타데이터(`meta_*`)와 시계열 통계(`active_meta_*`)를 분리하는 설계 패턴의
   정형화 — 갱신 빈도가 다른 데이터를 같은 테이블에 두면 이력 관리가 불가능하다는
   문제에 대한 해법
3. `source_type` 경계 원칙(1 dataset = 1 source_type)과 `dataset_origin` 이분법을
   통한 수집 주체 추적 방법
4. 매 수집 실행마다 `dcat_provenance`에 이력을 적재하는 운영 provenance 모델
5. 실제 4종 소스, 약 6만 건 규모의 운영 환경에서 CKAN·raw SQL·키워드 검색 대비
   탐색 효율과 메타데이터 품질을 정량 비교하는 사용자 task 기반 실증 평가

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| W3C (2020). "Data Catalog Vocabulary (DCAT) – Version 2." W3C Recommendation. | DCAT 2.0 공식 표준. `dcat:Dataset`, `dcat:Distribution`, `dcat:DataService` 클래스를 정의하고 공공 데이터 포털 중심의 적용 예시를 제공. | 웹 API 실시간 수집 데이터에 대한 구체적 적용 방법론 부재 |
| Neumaier, Umbrich & Polleres (2016). "Automated Quality Assessment of Metadata across Open Data Portals." *JDIQ*, 8(1), 1–29. | CKAN·DKAN 등 공공 데이터 포털의 메타데이터 완전성·일관성을 자동 평가. 정적 파일 배포 모델에 최적화된 품질 지표를 사용. | 시계열 수집·갱신 패턴을 가진 웹 API 데이터에 대한 품질 지표 없음 |
| Heath & Bizer (2011). *Linked Data: Evolving the Web into a Global Data Space*. Morgan & Claypool. | 연결 데이터 원칙(4 rules)을 기반으로 이종 데이터 소스 통합 이론 정립. 대규모 지식 그래프 구축에 초점. | 수집 주기·API 호출 이력 등 operational provenance 모델 없음 |
| Maali, Erickson & Archer (2014). "Data Catalog Vocabulary (DCAT)." W3C Recommendation. | DCAT 1.0 원 표준. 정적 파일 배포(Distribution) 중심 설계. | 동적 스트리밍·반복 수집 패턴 미지원; 시계열 누적 통계 표현 불가 |

### 2.1 선행 연구 대비 위치 (Positioning)

기존 연구들은 공공 데이터 포털의 정적 파일 배포 모델을 전제로 한다. W3C DCAT 2.0
표준과 그 전신인 DCAT 1.0(Maali et al., 2014)은 배포된 파일(Distribution) 단위의
메타데이터 기술에 초점이 맞춰져 있고, 시간에 따라 누적되는 통계나 반복 수집 이력을
표현하는 어휘를 제공하지 않는다. Neumaier et al.(2016)의 메타데이터 품질 평가
프레임워크 역시 "게시 시점에 채워진 필드가 얼마나 완전한가"를 재는 정적 지표이며,
YouTube·Naver API처럼 반복 수집·증분 갱신이 기본인 웹 데이터의 운영 이력(수집
성공/실패, API 한도 소진 등)은 평가 범주에 없다. Heath & Bizer(2011)의 연결 데이터
원칙은 이종 소스 통합의 이론적 토대를 제공하지만 대규모 지식 그래프 구축이 목적이며,
구체적인 수집 주체·시각 추적(operational provenance) 모델은 다루지 않는다.

요컨대, YouTube·Naver 뉴스·쇼핑 트렌드처럼 반복 수집·증분 갱신이 기본인 웹 데이터에
DCAT 2.0을 어떻게 확장해 적용할 것인가에 대한 방법론은 선행 연구에서 제시된 바 없다.
본 연구는 이 공백을 메우기 위해 정적/동적 분리, source_type 경계, 2단계 벡터 검색,
provenance 이력 적재라는 네 가지 설계 원칙을 제안하고 실증 평가한다.

---

## 3. 제안 방법 (Methodology)

### 3.1 설계 핵심 결정사항

| 설계 문제 | 결정 | 이유 |
|----------|------|------|
| 정적/동적 분리 | `meta_*` / `active_meta_*` 테이블 분리 | 갱신 빈도가 달라 같은 테이블에 두면 이력 관리 불가 |
| 소스 타입 경계 | 1 dataset = 1 source_type | 혼합 시 스키마 충돌 및 데이터 품질 추적 불가 |
| 벡터 검색 레벨 | 데이터셋 레벨 + 아이템 레벨 2단계 | 단일 레벨로는 "어디서 찾아야 하는가"와 "뭐가 있는가"를 동시에 해결 불가 |
| 수집 이력 추적 | `dcat_provenance`에 매 실행 INSERT | 오류 원인 추적, API 한도 소진 감지 등 운영 필수 정보 |

### 3.2 아키텍처 개요

플랫폼은 PostgreSQL(pgvector 확장 포함) + Kubernetes 위에서 운영된다. 수집
파이프라인이 새 데이터를 적재할 때마다 (1) 정적 속성은 `meta_*` 테이블에 upsert,
(2) 조회수·순위 등 변동 통계는 `active_meta_*` 테이블에 시점 스냅샷으로 append,
(3) 수집 실행 메타(시작/종료 시각, 성공 여부, 오류 코드, API 호출 잔여 한도)는
`dcat_provenance`에 INSERT된다. 검색 시에는 데이터셋 레벨 임베딩(어떤 데이터셋을
봐야 하는가)과 아이템 레벨 임베딩(그 안에 무엇이 있는가)을 순차 조회하는 2단계
벡터 검색을 사용한다.

### 3.3 DCAT 2.0 속성 매핑 및 확장 어휘

DCAT 2.0 핵심 클래스 각각의 속성이 4종 소스(YouTube, Naver 뉴스, 쇼핑 트렌드,
`[DATA: 4번째 소스명]`)에 어떻게 대응하는지 매핑 작업을 수행했다. 표준 속성으로
직접 매핑되지 않는 항목(예: 수집 실행 이력, API 한도 사용량, 시계열 통계 스냅샷)은
확장 어휘로 정의했다.

| DCAT 2.0 클래스 | 표준 속성 예시 | 확장 어휘 예시 | 확장 사유 |
|----------------|---------------|---------------|----------|
| `dcat:Dataset` | `dct:title`, `dct:description`, `dct:publisher`, `dcat:keyword`, `dct:temporal` | `source_type`, `dataset_origin` | 웹 API 소스 구분 및 수집 주체(직접 수집/외부 연동) 구분이 표준 어휘에 없음 |
| `dcat:Distribution` | `dcat:accessURL`, `dcat:byteSize`, `dct:format` | `active_meta_snapshot_at` | 시계열 통계 스냅샷 시각을 표현하는 표준 속성 부재 |
| `dcat:DataService` | `dcat:endpointURL`, `dcat:servesDataset` | `api_quota_remaining`, `collection_interval` | 반복 수집 주기·API 호출 한도는 정적 파일 배포 모델에 없는 개념 |
| (신규 확장 클래스) `dcat_provenance` | — | `run_started_at`, `run_status`, `error_code`, `records_collected` | 매 수집 실행의 성공/실패 이력을 표현하는 DCAT 표준 클래스 없음 |

`[DATA: 전체 매핑 속성 수, 표준 매핑 수, 신규 확장 어휘 수 — 제안서 목표: 확장
어휘 15개 이상]`

### 3.4 기존 시스템과의 기능 비교

CKAN, DataHub, Amundsen을 대상으로 아래 항목을 비교한다. 이는 별도 수치 측정이
아니라 각 시스템의 공개 문서·소스코드를 기준으로 한 기능 지원 여부 분석이다.

| 비교 항목 | CKAN | DataHub | Amundsen | 제안 플랫폼 |
|----------|------|---------|----------|-------------|
| 실시간 수집·갱신 지원 | 제한적 (수동/배치 업로드 중심) | 부분 지원 (ingestion 프레임워크 필요) | 제한적 (메타데이터 스캐너 중심) | 지원 (수집 파이프라인 내장) |
| 시계열 통계 이력 보존 | 미지원 | 부분 지원 (버전 관리) | 미지원 | 지원 (`active_meta_*` 분리 설계) |
| 의미 기반(벡터) 검색 | 미지원 | 미지원 (키워드/그래프 검색 중심) | 미지원 | 지원 (2단계 벡터 검색) |
| 한국어 데이터 특화 지원 | 미지원 | 미지원 | 미지원 | 지원 (한국어 임베딩 모델 적용) |
| 수집 실행 이력(provenance) | 부분 지원 (수동 로그) | 지원 (lineage 그래프) | 부분 지원 | 지원 (`dcat_provenance` 자동 적재) |

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 참가자 및 데이터셋

| 항목 | 값 |
|------|-----|
| 참가자 | 개발자 `[DATA: N ≥ 5]`명 (제안서 목표: 5명 이상) |
| 데이터 소스 | 4종 (YouTube, Naver 뉴스, 쇼핑 트렌드, `[DATA: 4번째 소스명]`) |
| 총 레코드 수 | `[DATA: 약 60,000]`건 |
| 탐색 과제 수 | 10개 |
| 실험 조건 | 조건 A(플랫폼 벡터 검색) / 조건 B(PostgreSQL 원시 테이블 직접 SQL 쿼리) |

### 4.2 탐색 과제 설계

동일한 10개 탐색 과제를 두 조건에서 수행하게 한다. 과제는 아래 세 유형으로 구성된다.

```
조건 A: 플랫폼 벡터 검색 사용
조건 B: PostgreSQL 원시 테이블 직접 SQL 쿼리

과제 예시:
  - "AI 관련 뉴스 기사가 포함된 데이터셋을 찾아라"          (의미기반 탐색)
  - "최근 한 달 조회수 증가율이 가장 높은 YouTube 영상 5개를 찾아라"  (통계/트렌드 파악)
  - "지난 6개월간 수집 실패가 있었던 데이터셋 목록을 가져와라"       (운영/이력 추적)
```

`[DATA: 10개 과제 전체 목록 및 유형별 분류 확정]`

### 4.3 실험 절차

1. 참가자별 사전 설문(개발 경력, DCAT/카탈로그 시스템 사용 경험) 실시.
2. 조건 순서에 따른 학습 효과를 통제하기 위해 조건 A/B 및 과제 순서를 참가자 간
   균형 배치(counterbalancing)한다.
3. 각 과제에 대해 완료까지 걸린 시간을 측정하고, 과제 완료 후 결과의 정확성을
   검증한다.
4. 전체 과제 종료 후 정성적 피드백(플랫폼 사용 경험, 불편했던 지점)을 수집한다.

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상 (Baselines)

| 조건 | 설명 |
|------|------|
| Raw SQL | 플랫폼 없이 PostgreSQL 직접 쿼리 |
| Keyword Search | LIKE 기반 키워드 검색 |
| CKAN | 공개 데이터 카탈로그 시스템 |
| 제안 플랫폼 | DCAT + 벡터 검색 + active_meta |

### 5.2 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| 탐색 과제 완료 시간 (초) | 사용자가 과제를 푸는 데 걸린 시간 | 플랫폼의 실용적 효율성을 직접 측정 |
| DCAT 속성 커버리지 (%) | 필수+권고 속성 중 실제 채워진 비율 | 메타데이터 품질의 객관적 척도 |
| 벡터 검색 응답 시간 (ms) | 쿼리당 p50/p95 응답 시간 | 운영 실용성 평가 |
| 검색 Precision@5 | 쿼리 결과 상위 5개 중 관련 결과 비율 | 검색 품질 척도 |

### 5.3 주요 개념 설명

**Precision@5 (상위 5 정밀도)**
검색 결과 상위 5개 중 실제로 관련 있는 결과의 비율. Precision@5 = 0.6이면 5개 중
3개가 관련 결과라는 뜻. (Recall과의 차이: Recall은 "전체 관련 결과 중 몇 개를
찾았는가"이고, Precision은 "찾아낸 것 중 얼마나 맞았는가"다. 이 연구에서는 5개
결과를 제시할 때 정확한 것이 몇 개인지가 중요하므로 Precision@5를 사용)

**p50 / p95 응답 시간 (백분위수 응답 시간)**
응답 시간의 분포를 백분위로 표현한다.
- p50 = 중앙값: 전체 요청의 50%가 이 시간 이내에 응답됨
- p95: 전체 요청의 95%가 이 시간 이내에 응답됨 (나머지 5%는 더 느림)
평균 대신 p95를 쓰는 이유: 평균은 간헐적인 느린 요청을 희석시키지만, p95는 "실제
사용자 중 5%가 겪는 최악의 경험"을 드러낸다. API 운영 SLA 기준으로 널리 사용된다.

**DCAT 속성 커버리지**
W3C DCAT 2.0 표준에서 정의하는 필수(mandatory)·권고(recommended) 속성 목록 중
실제로 값이 채워진 비율. 커버리지가 높을수록 다른 시스템과의 상호운용성
(interoperability)이 높고 데이터셋 발견 가능성(discoverability)이 좋아진다.

### 5.4 통계 검정

- **Wilcoxon signed-rank test**(비모수, paired) — 동일 참가자가 조건 A/B 양쪽을
  모두 수행하는 within-subject 설계이므로, 과제별 완료 시간 차이에 순위를 매겨
  조건 간 전체 성능 차이의 유의성을 검정 (p < 0.05 기준). 과제 유형(의미기반 탐색 /
  통계·트렌드 파악 / 운영·이력 추적)별로도 별도 검정한다.

### 5.5 해석 기준 (성공 조건)

- 탐색 과제 완료 시간: 플랫폼 조건이 Raw SQL 대비 40% 이상 단축
- DCAT 속성 커버리지: 핵심 속성(title, description, publisher 등) 95% 이상
- 벡터 검색 p95: 100ms 이하 (10만 건 기준)

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 탐색 과제 완료 시간

| 조건 | 평균 완료 시간 (초) | 표준편차 |
|------|---------------------|---------|
| Raw SQL | `[DATA]` | `[DATA]` |
| 제안 플랫폼 | `[DATA]` | `[DATA]` |
| 감소율 | `[DATA]`% | — |

Wilcoxon signed-rank test (제안 플랫폼 vs. Raw SQL, 전체): `[DATA: statistic, p-value]`

과제 유형별 세부 결과:

| 과제 유형 | Raw SQL (초) | 제안 플랫폼 (초) | 감소율 | Wilcoxon p |
|----------|-------------|------------------|--------|-----------|
| 의미기반 탐색 | `[DATA]` | `[DATA]` | `[DATA]`% | `[DATA]` |
| 통계/트렌드 파악 | `[DATA]` | `[DATA]` | `[DATA]`% | `[DATA]` |
| 운영/이력 추적 | `[DATA]` | `[DATA]` | `[DATA]`% | `[DATA]` |

### 6.2 DCAT 속성 커버리지

| DCAT 속성 | 커버리지 (%) |
|-----------|-------------|
| `dct:title` | `[DATA]` |
| `dct:description` | `[DATA]` |
| `dct:publisher` | `[DATA]` |
| `dcat:keyword` | `[DATA]` |
| `dct:temporal` | `[DATA]` |
| `dct:accrualPeriodicity` | `[DATA]` |
| **핵심 속성 평균** | **`[DATA]`** |

### 6.3 벡터 검색 응답 시간

| 검색 레벨 | 대상 규모 | p50 (ms) | p95 (ms) |
|----------|----------|----------|----------|
| 데이터셋 레벨 | `[DATA]`개 데이터셋 | `[DATA]` | `[DATA]` |
| 아이템 레벨 | 약 `[DATA: 60,000]`건 | `[DATA]` | `[DATA]` |

`10만 건 기준 p95 100ms 이하` 목표 대비 실측 규모(약 6만 건)에서의 결과: `[DATA]`

### 6.4 검색 Precision@5

| 방법 | Precision@5 |
|------|-------------|
| Keyword Search | `[DATA]` |
| 제안 플랫폼 | `[DATA]` |

### 6.5 정성적 피드백

`[DATA: 참가자 인터뷰/설문에서 수집한 주요 코멘트 요약]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 해석 기준(과제 완료 시간 40% 단축, DCAT 커버리지 95% 이상, 벡터 검색 p95 100ms
  이하) 각각의 충족 여부와 그 의미
- 과제 유형별로 플랫폼의 이점이 균일했는지, 아니면 특정 유형(의미기반 탐색 vs.
  운영/이력 추적)에서만 두드러졌는지
- DCAT 속성 커버리지가 낮게 나온 속성이 있다면 그 원인(소스별 API 제약, 확장
  어휘 설계의 한계 등)
- 벡터 검색 응답 시간이 목표를 충족/미충족했다면 그 원인(인덱스 파라미터, 데이터
  규모, 레벨별 차이)
- CKAN 등 기존 시스템 대비 기능 비교(§3.4)와 사용자 실험 결과가 일관되는지

## 8. 한계 (Limitations)

- 참가자가 개발자 `[DATA: N ≥ 5]`명으로 소규모이며, 모두 동일 조직 소속이라
  플랫폼에 대한 사전 노출 정도가 다를 수 있어 통계적 검정력과 일반화 가능성에
  한계가 있다.
- 평가 대상 데이터 소스가 4종(YouTube, Naver 뉴스, 쇼핑 트렌드 등)에 한정되어,
  다른 성격의 웹 데이터(예: 금융 시세, IoT 센서 스트림)에 대한 일반화는 별도
  검증이 필요하다.
- 조건 A/B는 counterbalancing으로 순서 효과를 통제했지만, 참가자 수가 적어
  잔여 학습 효과(먼저 수행한 조건에서 데이터 구조를 학습해 이후 조건에 유리해지는
  효과)를 완전히 배제하기 어렵다.
- 벡터 검색 성능은 현재 운영 규모(약 6만 건)에서 측정한 값이며, 인덱스 파라미터
  튜닝(예: pgvector ivfflat/HNSW 설정)을 최적화하지 않은 기본 상태에서 측정했을
  가능성이 있어, 대규모 환경에서의 성능은 별도 검증이 필요하다.
- CKAN·DataHub·Amundsen과의 비교(§3.4)는 실제 배포·측정이 아니라 공개 문서 및
  기능 목록 기반의 정성적 분석이므로, 응답 시간 등 실측 성능 비교는 이루어지지
  않았다.

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 — 과제 완료 시간 단축 여부, DCAT 커버리지 달성 여부,
벡터 검색 응답 시간 달성 여부 + 향후 확장 방향]`

향후 확장성:
- data.go.kr 공공 데이터 포털과 연동
- 멀티테넌시 지원 (기관별 독립 카탈로그)

---

## 참고문헌 (References)

1. W3C (2020). Data Catalog Vocabulary (DCAT) – Version 2. W3C Recommendation.
2. Neumaier, S., Umbrich, J., & Polleres, A. (2016). Automated Quality Assessment of Metadata across Open Data Portals. *Journal of Data and Information Quality (JDIQ)*, 8(1), 1–29.
3. Heath, T., & Bizer, C. (2011). *Linked Data: Evolving the Web into a Global Data Space*. Morgan & Claypool.
4. Maali, F., Erickson, J., & Archer, P. (2014). Data Catalog Vocabulary (DCAT). W3C Recommendation.

---

## 데이터 삽입 체크리스트 (작업용)

사용자 실험 및 시스템 측정 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] Abstract/초록의 참가자 수(N), 4번째 데이터 소스명, 확장 어휘 수 확정
- [ ] 3.3 DCAT 속성 매핑 표 — 전체 매핑 속성 수, 표준/확장 개수 확정
- [ ] 4.1 참가자 수, 4번째 데이터 소스명 확정
- [ ] 4.2 10개 탐색 과제 전체 목록 및 유형 분류 확정
- [ ] 6.1 탐색 과제 완료 시간(전체 + 과제 유형별) 수치 및 Wilcoxon 검정 결과 삽입
- [ ] 6.2 DCAT 속성 커버리지 표 삽입
- [ ] 6.3 벡터 검색 응답 시간(p50/p95, 레벨별) 삽입 및 목표 충족 여부 판정
- [ ] 6.4 검색 Precision@5 삽입
- [ ] 6.5 정성적 피드백 요약 작성
- [ ] 7장 논의 작성
- [ ] 8장 한계 재검토 (실측 결과 반영해 추가/수정)
- [ ] 9장 결론 작성
- [ ] 참고문헌 서지정보 최종 확인
