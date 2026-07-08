# 연구 기획서 모음 (v2)

> 작성일: 2026-07-07
> 목적: 논문 주제 후보 검토 및 연구 방향 회의용
> 대상 분량: 5페이지 내외 단편 논문 / 학회·워크숍 단문 논문
>
> **읽는 법**: 각 주제의 "연구 질문"이 핵심이다.
> 연구 방법은 그 질문에 답하는 실험 절차이고,
> 평가 방법은 그 답이 맞는지 확인하는 방법이다.
> 세 요소의 연결이 끊기면 논문이 성립하지 않는다.

---

## 목차

| # | 주제 | 분야 | 데이터 가용성 | 구현 난이도 |
|---|------|------|------------|-----------|
| P01 | 상대 검색량 지수의 장기 연속 시계열 복원 | 데이터 전처리·방법론 | 즉시 | 중 |
| P02 | DCAT 2.0 기반 이종 웹 데이터 통합 메타데이터 플랫폼 | 시스템·데이터 엔지니어링 | 즉시 | 하 |
| P03 | LLM 기반 한국어 YouTube 콘텐츠 메타데이터 자동 생성 | NLP·AI | 수집 필요 | 중 |
| P04 | 쇼핑 Persona Index 독립 가정의 카테고리별 위반 정도 분석 | 데이터 분석·통계 | 즉시 | 중 |
| P05 | 뉴스 기사 댓글 시계열로 기사 사회적 임팩트 측정 | 소셜 미디어 분석 | 수집 필요 | 중 |
| P06 | YouTube 조회수와 네이버 쇼핑 검색량 간 그랜저 인과 분석 | 시계열 분석 | 즉시+수집 | 중 |
| P07 | RAG 기반 한국어 도메인 Q&A: 뉴스 기사 지식베이스 활용 | NLP·IR | 수집 필요 | 상 |
| P08 | 계층적 벡터 검색을 이용한 이종 미디어 데이터셋 탐색 | 정보 검색 | 즉시 | 중 |
| P09 | YouTube 썸네일+텍스트 멀티모달 임베딩을 이용한 영상 검색 성능 향상 | 멀티모달·IR | 즉시 | 중 |
| P10 | 비전-언어 모델을 이용한 YouTube 썸네일 메타데이터 자동 생성 | 멀티모달·NLP | 즉시+ | 상 |
| P11 | 썸네일-제목 의미 정합성을 활용한 한국어 YouTube 클릭베이트 탐지 | 멀티모달·콘텐츠 품질 | 레이블링 필요 | 중 |

---
---

# P01. 상대 검색량 지수의 장기 연속 시계열 복원

## 연구 필요성 (Research Gap)

네이버 쇼핑인사이트·Google Trends 등 검색 트렌드 API는 절대 검색량 대신
**요청 범위 내 최댓값=100으로 정규화된 상대값**을 반환한다. 이 구조는 두 가지
문제를 일으킨다.

1. **배치 간 불연속**: API가 한 번에 최대 3개 카테고리 비교를 허용하므로 여러
   배치로 나눠 호출하면 배치마다 정규화 기준 M이 달라진다. 같은 카테고리라도
   배치 구성에 따라 raw_ratio가 달라지는 것이다.
2. **수집 구간 간 불연속**: 다른 날 같은 기간을 재수집하면 검색량 분포 자체가
   달라져 M이 바뀐다. 두 시점의 raw_ratio를 그냥 연결하면 단절이 생긴다.

기존 문헌 대부분은 단일 API 호출 범위 내 비교에 그친다. **anchor 카테고리와
두 단계 Scale 보정(intra_scale × inter_scale)으로 장기 연속 시계열을 복원하는
체계적 방법론**은 발표된 논문이 없다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Choi & Varian (2012). "Predicting the Present with Google Trends." *The Economic Record*, 88(S1), 2–9. | Google Trends 상대 지수를 소비·고용 등 경제 지표 예측에 활용한 선구적 연구. 단일 수집 세션의 데이터만 사용해 배치 간 정규화 기준 차이 문제를 논의하지 않음. | 다수 배치·다수 수집 구간 간 보정 방법 미제시 |
| Da, Engelberg & Gao (2011). "In Search of Attention." *Journal of Finance*, 66(5), 1461–1499. | 개인 투자자 관심도의 대리 지표로 Google SVI(Search Volume Index)를 활용. 상대값의 크로스 섹션 비교 한계를 언급하나 계량적 보정 방법을 제시하지 않음. | anchor 기반 연속 시계열 복원 없음 |
| Preis, Moat & Stanley (2013). "Quantifying Trading Behavior Using Google Trends." *Scientific Reports*, 3, 1684. | 검색 트렌드를 금융 행동 지표로 사용. 단일 키워드 시계열 분석에 그치며, 카테고리 배치 구성 변경 시 발생하는 불연속 문제를 다루지 않음. | 단일 쿼리·단일 배치 가정 |
| Lazer et al. (2014). "The Parable of Google Flu: Traps in Big Data Analysis." *Science*, 343(6176), 1203–1205. | 알고리즘 변화로 인한 Google Flu Trends 붕괴 사례를 통해 외부 요인이 상대 지수 신뢰성을 해친다는 점을 지적. 단, 체계적 재보정 방법 없이 데이터 자체의 한계를 논증하는 데 그침. | 보정 방법론 미제시, 경고성 사례 연구 수준 |

기존 문헌들은 상대 지수를 **있는 그대로** 활용하거나 단일 세션 내 비교에 머무른다. 수집 배치 구성과 수집 시점이 달라져도 장기 연속 시계열을 복원하는 방법론은 제시된 바 없다.

## 기여점 (Contribution)

- 상대 지수 비연속 문제의 수학적 정형화
- intra_scale / inter_scale 2단계 보정 방법 제안
- 중앙값 기반 Robust 추정으로 이상치 내성 확보
- pseudo_volume 신뢰도 분석 및 한계 명시

## 제목

> *Pseudo-Volume: A Two-Stage Scale Correction Method for Reconstructing Continuous Time-Series from Relative Search Indices*

## 초록

네이버 쇼핑인사이트 등 검색 트렌드 API는 절대 검색량 대신 요청 범위 내 상대값을
반환한다. 이로 인해 호출 배치가 달라지거나 수집 시점이 분리되면 시계열이 단절된다.
본 연구는 anchor 카테고리를 매 배치에 포함시켜 배치 간 정규화 기준 차이를 보정하고
(intra_scale), 수집 구간이 겹치는 기간의 anchor 값 비율로 수집 구간 간 차이를
보정하는(inter_scale) 두 단계 Pseudo-Volume 방법을 제안한다. 네이버 쇼핑인사이트
5개 카테고리 1년 치 데이터로 검증하고, 기존 단순 연결 방식 대비 연속성과 예측 정확도를
비교한다.

## 연구 내용

### 1단계: 문제 정형화

```
R(c, t, B) = 배치 B에서 카테고리 c, 시점 t의 raw_ratio
M(B) = 해당 배치의 검색량 최대값 (API가 숨기는 값)
R(c, t, B) = actual_volume(c, t) / M(B) × 100
```

배치 B1과 B2가 같은 기간을 다루더라도 M(B1) ≠ M(B2)이면 R의 직접 비교는 불가하다.

### 2단계: intra_scale (배치 간 보정)

anchor 카테고리 a를 모든 배치에 포함시킨다.
기준 배치(첫 번째 유효 배치)의 anchor 값과 각 배치의 anchor 값 비율 중앙값으로 보정한다.

```
intra_scale(B) = median_t { R(a, t, B_ref) / R(a, t, B) }
```

### 3단계: inter_scale (수집 구간 간 보정)

이전 수집과 신규 수집이 겹치는 기간을 이용해 anchor 값 비율 중앙값으로 보정한다.

```
inter_scale = median_t { R_db(a, t) / R_new(a, t) }   (겹치는 t에 대해)
```

### 4단계: pseudo_volume 산출

```
pseudo_volume(c, t) = R(c, t) × intra_scale(B) × inter_scale
```

---

## 연구 방법

### 핵심 연구 질문

> "두 단계 Scale 보정으로 복원한 pseudo_volume은, 배치 구성과 수집 시점이 달라도
> 동일한 (카테고리, 날짜)에 대해 일관된 값을 산출하는가?"

### 실험 1: 배치 구성 변경 실험 (intra_scale 검증)

동일한 카테고리 집합을 **의도적으로 다른 배치 구성**으로 수집한다.

```
실험 A 배치 구성: anchor + [패션의류, 스포츠] → [패션잡화]
실험 B 배치 구성: anchor + [스포츠] → [패션의류, 패션잡화]
```

같은 날짜의 pseudo_volume이 배치 구성과 무관하게 일치해야 한다.

### 실험 2: 수집 구간 겹침 실험 (inter_scale 검증)

같은 기간(예: 2025-01 ~ 2025-03)을 **두 번 다른 날에 수집**하고
두 번의 pseudo_volume을 비교한다. 차이가 클수록 inter_scale 보정의 필요성이 크다.

### 실험 3: 예측 정확도 실험

1년 치 pseudo_volume vs. raw_ratio vs. normalized_ratio로 각각 ARIMA 모델을 학습하고
마지막 4주를 예측해 비교한다.

```
학습 기간: 2025-01 ~ 2026-03 (15개월)
예측 기간: 2026-04 ~ 2026-06 (3개월)
```

---

## 평가 방법

### 비교 대상 (Baselines)

| 방법 | 설명 |
|------|------|
| Naive 연결 | raw_ratio를 그냥 이어붙임 (보정 없음) |
| 선형 스케일링 | 각 수집 구간의 평균값으로 나눠 정규화 |
| 단일 anchor | intra_scale 없이 inter_scale만 적용 |
| 제안 방법 | intra_scale × inter_scale 2단계 |

### 측정 지표와 측정 대상의 연결

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| 배치 일관성 (CV) | 같은 (카테고리, 날짜)의 다른 배치 pseudo_volume 변동계수 | 배치 구성이 달라도 값이 같아야 한다는 핵심 요건을 직접 측정 |
| 구간 연결점 jump 크기 | 수집 구간 경계에서의 값 단절 절댓값 | 시계열이 얼마나 매끄럽게 이어지는지 측정 |
| ARIMA RMSE | 복원 시계열로 예측한 미래값의 오차 | 연속 시계열의 실용적 가치(예측에 써먹을 수 있는지) 측정 |
| Bootstrap 신뢰구간 폭 | scale 계수 추정 불확실성 | 방법의 안정성과 한계를 동시에 표현 |

### 해석 기준 (성공 조건)

- 배치 일관성 CV: 제안 방법 < Naive의 50% → 배치 간 일관성 확보 입증
- 연결점 jump 크기: 제안 방법 < Naive의 50%
- ARIMA RMSE: 제안 방법이 Naive 대비 통계적으로 유의하게 낮음 (paired t-test p < 0.05)

## 구현 난이도: ★★☆☆☆

- 데이터 즉시 가용, 수식 구현 Python 300줄 이내
- 추가 API 호출 비용 소요 (의도적 중복 수집 실험)

## 향후 확장성

- Google Trends 동일 적용 (API 구조 유사)
- Online 추정: 실시간 streaming 환경에서의 sliding window scale 추정

---
---

# P02. DCAT 2.0 기반 이종 웹 데이터 통합 메타데이터 플랫폼

## 연구 필요성 (Research Gap)

DCAT(Data Catalog Vocabulary)은 공공 데이터 포털 중심으로 적용되며, YouTube·뉴스·쇼핑
트렌드처럼 **구조·갱신 주기·수집 방식이 전혀 다른 이종 웹 API 데이터에 DCAT 2.0을
체계적으로 적용한 사례**는 거의 없다. 기존 CKAN, DataHub 같은 오픈소스 카탈로그는
정적 파일 기반 데이터에 최적화되어 있어 실시간 수집·갱신되는 웹 데이터에 그대로
적용하기 어렵다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| W3C (2020). "Data Catalog Vocabulary (DCAT) – Version 2." W3C Recommendation. | DCAT 2.0 공식 표준. `dcat:Dataset`, `dcat:Distribution`, `dcat:DataService` 클래스를 정의하고 공공 데이터 포털 중심의 적용 예시를 제공. | 웹 API 실시간 수집 데이터에 대한 구체적 적용 방법론 부재 |
| Neumaier, Umbrich & Polleres (2016). "Automated Quality Assessment of Metadata across Open Data Portals." *JDIQ*, 8(1), 1–29. | CKAN·DKAN 등 공공 데이터 포털의 메타데이터 완전성·일관성을 자동 평가. 정적 파일 배포 모델에 최적화된 품질 지표를 사용. | 시계열 수집·갱신 패턴을 가진 웹 API 데이터에 대한 품질 지표 없음 |
| Heath & Bizer (2011). *Linked Data: Evolving the Web into a Global Data Space*. Morgan & Claypool. | 연결 데이터 원칙(4 rules)을 기반으로 이종 데이터 소스 통합 이론 정립. 대규모 지식 그래프 구축에 초점. | 수집 주기·API 호출 이력 등 operational provenance 모델 없음 |
| Maali, Erickson & Archer (2014). "Data Catalog Vocabulary (DCAT)." W3C Recommendation. | DCAT 1.0 원 표준. 정적 파일 배포(Distribution) 중심 설계. | 동적 스트리밍·반복 수집 패턴 미지원; 시계열 누적 통계 표현 불가 |

기존 연구들은 공공 데이터 포털의 정적 파일 배포 모델을 전제로 하며, YouTube·Naver API처럼 반복 수집·증분 갱신이 기본인 웹 데이터에 대한 DCAT 확장 방법론은 제시된 바 없다.

## 기여점 (Contribution)

- DCAT 2.0 클래스의 웹 API 데이터 매핑 규칙 제안 (확장 어휘 15개 이상)
- 정적 메타데이터(meta_*)와 시계열 통계(active_meta_*) 분리 설계 패턴 정형화
- source_type 경계 원칙과 dataset_origin 이분법으로 수집 주체 추적
- 실제 4종 소스, 6만 건 운영 사례 기반 성능 평가

## 제목

> *A DCAT 2.0-Based Metadata Platform for Heterogeneous Korean Web Data Sources: Design, Implementation, and Evaluation*

## 초록

YouTube, Naver 뉴스, 쇼핑 트렌드처럼 구조가 상이한 웹 API 데이터를 단일 메타데이터
체계로 관리하는 플랫폼을 설계·구현하고 평가한다. W3C DCAT 2.0을 기반으로 웹 API
특화 확장 어휘를 정의하고, 정적 메타데이터와 시계열 통계를 분리하는 active_meta 패턴,
벡터 임베딩 기반 2단계 의미 검색을 통합한다. 실제 운영 환경(PostgreSQL + Kubernetes)
에서 4종 데이터 소스, 약 6만 건 데이터를 대상으로 검색 성능과 메타데이터 완결성을
측정한다.

## 연구 내용

### 설계 핵심 결정사항

| 설계 문제 | 결정 | 이유 |
|----------|------|------|
| 정적/동적 분리 | meta_* / active_meta_* 테이블 분리 | 갱신 빈도가 달라 같은 테이블에 두면 이력 관리 불가 |
| 소스 타입 경계 | 1 dataset = 1 source_type | 혼합 시 스키마 충돌 및 데이터 품질 추적 불가 |
| 벡터 검색 레벨 | 데이터셋 레벨 + 아이템 레벨 2단계 | 단일 레벨로는 "어디서 찾아야 하는가"와 "뭐가 있는가"를 동시에 해결 불가 |
| 수집 이력 추적 | dcat_provenance에 매 실행 INSERT | 오류 원인 추적, API 한도 소진 감지 등 운영 필수 정보 |

---

## 연구 방법

### 핵심 연구 질문

> "DCAT 기반 플랫폼이 없는 경우(raw 테이블 직접 사용)와 비교해
> 데이터 탐색 효율과 메타데이터 품질이 실질적으로 향상되는가?"

### 방법 1: 기존 시스템과 기능 비교 분석

CKAN, DataHub, Amundsen 대상으로 아래 항목을 평가한다.

```
비교 항목:
  - 실시간 수집·갱신 지원 여부
  - 시계열 통계 이력 보존 방법
  - 의미 기반(벡터) 검색 지원 여부
  - 한국어 데이터 특화 지원
```

### 방법 2: DCAT 2.0 속성 매핑 작업

DCAT 2.0 핵심 클래스 각각의 속성이 4종 소스에 어떻게 대응하는지 매핑 테이블 작성.
매핑 불가 속성 → 확장 어휘 정의. 확장 수를 정량화한다.

### 방법 3: 사용자 task 기반 평가 실험

개발자 5명 이상에게 동일한 10개 탐색 과제를 두 조건에서 수행하게 한다.

```
조건 A: 플랫폼 벡터 검색 사용
조건 B: PostgreSQL 원시 테이블 직접 SQL 쿼리
과제 예시:
  - "AI 관련 뉴스 기사가 포함된 데이터셋을 찾아라"
  - "최근 한 달 조회수 증가율이 가장 높은 YouTube 영상 5개를 찾아라"
  - "지난 6개월간 수집 실패가 있었던 데이터셋 목록을 가져와라"
```

---

## 평가 방법

### 비교 대상

| 조건 | 설명 |
|------|------|
| Raw SQL | 플랫폼 없이 PostgreSQL 직접 쿼리 |
| Keyword Search | LIKE 기반 키워드 검색 |
| CKAN | 공개 데이터 카탈로그 시스템 |
| 제안 플랫폼 | DCAT + 벡터 검색 + active_meta |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| 탐색 과제 완료 시간 (초) | 사용자가 과제를 푸는 데 걸린 시간 | 플랫폼의 실용적 효율성을 직접 측정 |
| DCAT 속성 커버리지 (%) | 필수+권고 속성 중 실제 채워진 비율 | 메타데이터 품질의 객관적 척도 |
| 벡터 검색 응답 시간 (ms) | 쿼리당 p50/p95 응답 시간 | 운영 실용성 평가 |
| 검색 Precision@5 | 쿼리 결과 상위 5개 중 관련 결과 비율 | 검색 품질 척도 |

### 해석 기준

- 탐색 과제 완료 시간: 플랫폼 조건이 Raw SQL 대비 40% 이상 단축
- DCAT 속성 커버리지: 핵심 속성(title, description, publisher 등) 95% 이상
- 벡터 검색 p95: 100ms 이하 (10만 건 기준)

## 구현 난이도: ★☆☆☆☆

이미 구현된 시스템을 평가·정리하는 작업이 핵심. 사용자 실험 설계가 추가 필요.

## 향후 확장성

- data.go.kr 공공 데이터 포털과 연동
- 멀티테넌시 지원 (기관별 독립 카탈로그)

---
---

# P03. LLM 기반 한국어 YouTube 콘텐츠 메타데이터 자동 생성

## 연구 필요성 (Research Gap)

YouTube API 메타데이터(제목·설명·태그)는 업로더 입력값으로, 키워드 스터핑이나
콘텐츠 내용과의 불일치가 빈번하다. 자동 자막(STT) 기반 트랜스크립트가 있지만
한국어 STT는 전문 용어 오인식이 심하다. **STT 노이즈가 심한 한국어 텍스트에서
LLM으로 고품질 구조화 메타데이터를 뽑는 파이프라인**의 실증 평가가 부족하다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Brown et al. (2020). "Language Models are Few-Shot Learners (GPT-3)." *NeurIPS*, 33, 1877–1901. | 175B 파라미터 LLM의 few-shot 능력을 실증. 정보 추출·요약 등 다양한 NLP 태스크에서 인간 수준에 근접. | 한국어 전문 도메인·STT 노이즈 환경에서의 소규모 오픈소스 모델 적용 미검증 |
| Touvron et al. (2023). "Llama 2: Open Foundation and Fine-Tuned Chat Models." arXiv:2307.09288. | 7B–70B 오픈소스 LLM 공개. 상용 수준의 한국어 이해 가능성을 시사하나 성능 평가는 영어 벤치마크 중심. | 한국어 구조화 메타데이터 추출(요약+키워드+개체명 동시)의 실용성 평가 없음 |
| Wei et al. (2022). "Emergent Abilities of Large Language Models." *TMLR*. | 모델 규모가 일정 임계를 넘으면 복잡한 추론·추출 능력이 창발함을 분석. 소규모(8B 이하) 모델의 창발 한계 지점 미제시. | 8B 급 오픈소스 모델의 구조화 추출 안정성 평가 없음 |
| Raffel et al. (2020). "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer (T5)." *JMLR*, 21(140), 1–67. | 정보 추출을 text-to-text 프레임워크로 통일. 한국어 전문 용어 STT 오류 패턴에 대한 로버스트성 평가 없음. | 교착어 한국어 STT 노이즈 대응 전략 없음 |

기존 연구들은 대용량 영어 중심 벤치마크에서의 성능 평가에 집중하며, GPU 자원이 없는 환경에서 소규모 오픈소스 LLM으로 한국어 STT 노이즈 텍스트로부터 구조화 메타데이터를 추출하는 실용적 파이프라인을 평가한 연구는 없다.

## 기여점 (Contribution)

- STT 노이즈 유형 분류 및 전처리 파이프라인
- 요약·키워드·개체명·콘텐츠 유형 4종 동시 추출 프롬프트
- 무료 LLM(Groq: llama-3.1-8b, gemma2-9b)의 한국어 실용 성능 측정
- LLM 메타데이터 추가 시 벡터 검색 품질 향상 정량화

## 제목

> *Automated Korean Metadata Enrichment for YouTube Videos via LLM-Based Transcript Analysis*

## 초록

YouTube 영상의 API 메타데이터는 콘텐츠 실제 내용을 충분히 반영하지 못한다. 본 연구는
STT 기반 한국어 트랜스크립트에서 요약·키워드·개체명·콘텐츠 유형을 공개 LLM으로 자동
추출하는 파이프라인을 제안한다. 노이즈 전처리, 구조화 출력 프롬프트, Long Context 처리
전략을 설계하고, 추출 품질을 인간 평가와 검색 정확도(IR 지표) 양 측면에서 평가한다.
Groq 무료 API(14,400 req/day) 환경에서 일일 처리 가능 규모와 비용 효율성도 분석한다.

## 연구 내용

### 파이프라인 구성

```
[youtube-transcript-api] → 원시 트랜스크립트
        ↓ 전처리
  - 타임스탬프 제거
  - 반복 구문 병합 (STT 버벅임 제거)
  - 토큰 수 계산 → 16K 초과 시 청킹
        ↓ LLM 호출 (Groq API)
  프롬프트: "아래 YouTube 트랜스크립트를 분석하여 JSON으로 반환하라.
             {summary, keywords, entities, content_type}"
        ↓ 파싱 및 검증
  - JSON schema validation
  - 빈 필드 fallback 처리 (title+description으로 재시도)
        ↓
  meta_youtube_video_ai 테이블 저장
```

### Long Context 처리 전략

| 트랜스크립트 길이 | 전략 |
|----------------|------|
| ≤ 8K 토큰 | 전체 입력 |
| 8K ~ 32K 토큰 | Map-Reduce: 청크별 요약 → 최종 통합 |
| > 32K 토큰 | 앞·중간·뒤 3구간 샘플링 후 통합 |

---

## 연구 방법

### 핵심 연구 질문

> "LLM이 생성한 메타데이터를 추가했을 때,
> 트랜스크립트가 없는 API 메타데이터만 사용한 경우 대비
> 검색 정확도가 통계적으로 유의하게 향상되는가?"

### 실험 설계

**데이터 구축**

- YouTube 영상 200편 이상 (기술 100편 + 의료 50편 + 뉴스 50편)
- 각 영상에 대해 인간 레퍼런스 생성: 3문장 요약, 5~10개 키워드, 개체명 목록
  (평가자 2인, 불일치 시 제3자 조정)
- 검색 평가용 Query-Relevance 쌍 50개 구축
  (질문 예시: "HBM 제조 공정을 설명하는 영상")

**조건 비교**

```
조건 A: 제목 + 설명 + 태그 (API 메타데이터만)
조건 B: 조건 A + LLM 요약 + 키워드
조건 C: 조건 B + 개체명 + 콘텐츠 유형
```

**LLM 비교**

```
llama-3.1-8b   (Groq, 무료)
gemma2-9b      (Groq, 무료)
GPT-4o-mini    (유료, 품질 상한 기준)
```

---

## 평가 방법

### 평가 1: 메타데이터 품질 (생성 자체의 품질)

이 평가는 "LLM이 올바른 메타데이터를 생성하는가"를 측정한다.

| 지표 | 측정 대상 | 계산 방법 |
|------|----------|---------|
| ROUGE-L | 요약 품질 | LLM 요약 vs. 인간 레퍼런스 요약의 최장 공통 부분 수열 |
| Keyword F1 | 키워드 적중률 | LLM 키워드 ∩ 인간 키워드 / Union |
| NER F1 | 개체명 인식 정확도 | LLM 개체명 vs. 인간 레이블 |
| 인간 평가 (5점) | 전반적 유용성 | 관련성·정확성·완결성 항목 |

### 평가 2: 검색 품질 향상 (메타데이터가 검색에 도움이 되는가)

이 평가가 핵심이다. 메타데이터 자체의 품질보다 **실제로 사용할 때 더 잘 찾아지는가**가 중요하다.

```
실험 절차:
1. 조건 A/B/C 각각으로 영상 200편을 임베딩·인덱싱
2. 50개 검색 쿼리를 각 조건에서 실행
3. 결과 상위 10개와 정답셋(관련 영상 목록) 비교
```

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| NDCG@5 | 상위 5개 결과의 순위 품질 | 사용자는 보통 상위 몇 개만 확인 |
| MRR | 첫 번째 관련 결과의 순위 역수 평균 | 정확한 답을 얼마나 빨리 찾는지 |
| Recall@10 | 정답 중 상위 10개 안에 있는 비율 | 놓치는 관련 결과가 없는지 |

### 해석 기준

- NDCG@5: 조건 C > 조건 A에서 Δ ≥ 0.05 (paired t-test p < 0.05)
- LLM 인간 평가: llama-3.1-8b 평균 3.5/5.0 이상 (실용 수준)
- 처리 효율: 영상 1편당 Groq 호출 ≤ 3회, 응답 시간 ≤ 10초

## 구현 난이도: ★★★☆☆

- 인간 레퍼런스 및 Query-Relevance 쌍 구축이 가장 큰 병목
- Groq API rate limit 관리 로직 구현 필요

## 향후 확장성

- 영상 썸네일 비전 결합 멀티모달 메타데이터
- 트랜스크립트 변경 감지 시 자동 재생성 파이프라인

---
---

# P04. 쇼핑 Persona Index 독립 가정의 카테고리별 위반 정도 분석

## 연구 필요성 (Research Gap)

`persona_index = gender_pv × age_pv`는 성별과 연령 검색 행동이 **통계적으로 독립**이라는
강한 가정에 기반한다. 하지만 임산부 용품이나 군용품 같은 카테고리에서는 성별-연령 교호작용이
강할 것이다. 네이버 공식 문서나 관련 논문 어디에도 **이 가정이 카테고리별로 얼마나
성립하는지 측정한 연구**가 없다.

**핵심 통찰**: 사실 shopping_insight API는 gender='m', age='20'처럼 성별과 연령을
**동시에** 필터링한 실측값을 제공한다. 이 값은 진짜 joint distribution의 근사값이다.
persona_index는 독립 가정 하의 추정값이다. 두 값을 비교하면 위반 정도를 직접 측정할 수 있다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Agresti, A. (2002). *Categorical Data Analysis*, 2nd ed. Wiley. | 범주형 변수의 독립성 검정 이론(카이제곱, 오즈비, 로그선형 모델). 관측 빈도표(contingency table)가 주어진 경우의 독립성 평가 방법 체계화. | 실측 교차 빈도표 없이 API 상대 지수만으로 독립성을 검증하는 방법론 부재 |
| Allenby & Rossi (1998). "Marketing Models of Consumer Heterogeneity." *Journal of Econometrics*, 89(1–2), 57–78. | 마케팅 맥락에서 소비자 이질성 모델링 시 인구통계 교호작용의 중요성을 강조. 계층적 베이즈 모델로 성별-연령 교호작용을 추정. | 관측 불가 교차 분포를 API 상대값으로 근사하는 방법 미제시 |
| Choi & Kim (2019). "Effects of Consumer Characteristics on Online Shopping Behavior." *Journal of Distribution Science*, 17(9), 27–36. | 한국 온라인 쇼핑 맥락에서 성별·연령 세그먼트가 구매 행동에 미치는 영향 분석. 설문조사 기반 데이터 사용. | API 기반 상대 검색량 지수 활용 없음; 교호작용 위반 정도 정량화 없음 |
| Manchanda, Ansari & Gupta (1999). "The 'Shopping Basket': An Analysis of Selection Decisions." *Marketing Science*, 18(2), 95–114. | 상품 카테고리 간 교차 구매 행동 분석. 성별-카테고리 교호작용이 카테고리 유형에 따라 달라짐을 실증. | 디지털 검색 트렌드 API 데이터 미적용 |

기존 마케팅·통계 문헌은 실측 교차 빈도표가 있는 경우의 독립성 검정에 집중하며, 성별과 연령을 분리 수집하는 API 상대 지수로 독립 가정 위반 정도를 카테고리별로 정량화하고 같은 플랫폼의 joint 측정값을 Ground Truth로 활용하는 연구는 없다.

## 기여점 (Contribution)

- shopping_insight 실측 joint 값을 Ground Truth로 사용하는 비교 방법 제안
- 위반 정도를 카테고리별로 정량화하는 지표 체계 구축
- 고위반 카테고리 유형 분류 및 실무 사용 주의 기준 제시
- 독립 가정이 안전한 조건과 위험한 조건 가이드라인

## 제목

> *When Does Independence Hold? Quantifying Persona Index Assumption Violations Across Shopping Categories*

## 초록

네이버 쇼핑인사이트 Persona Index는 성별과 연령 검색 행동이 독립이라는 가정 하에
`gender_pv × age_pv`로 산출한다. 그런데 쇼핑인사이트 API는 성별+연령을 동시에 필터링한
실측값도 제공한다. 본 연구는 이 실측 joint값을 기준으로 persona_index의 위반 정도를
카테고리별로 직접 측정한다. 패션·유아·스포츠 등 30개 카테고리에 적용해 위반 정도가
높은 카테고리 유형을 분류하고, 실무 활용 시 주의 기준을 제시한다.

## 연구 내용

### 측정 원리

```
실측 joint 값 (Ground Truth proxy):
  GT(gender, age, t) = shopping_insight.raw_ratio(gender=g, age=a, t)
  → 이 값은 gender와 age 필터를 동시에 적용한 실측 검색량 지수

독립 가정 추정값 (Persona Index):
  PI(gender, age, t) = persona_index(gender=g, age=a, t)
  = gender_pv(g,t) × age_pv(a,t)

위반 비율:
  violation_ratio(g, a, t) = PI(g, a, t) / GT(g, a, t)
  → 1에 가까울수록 독립 가정 성립, 멀수록 위반
```

단, GT와 PI는 정규화 기준이 다르므로 anchor를 통해 동일 단위로 변환 후 비교한다.

### 카테고리별 위반 지표

```
VD(category) = std_t { violation_ratio(g, a, t) }  across all (g, a) combos
             → 높을수록 독립 가정이 불안정하게 위반됨

VB(category) = mean_t { |violation_ratio - 1| }
             → 평균 편향 (체계적으로 과대/과소 추정하는지)
```

---

## 연구 방법

### 핵심 연구 질문

> "성별과 연령 필터를 동시에 적용한 실측값과 독립 가정 기반 persona_index 사이의
> 괴리가 카테고리에 따라 유의하게 다른가? 어떤 카테고리 특성이 괴리를 예측하는가?"

### 데이터 수집 설계

두 API를 동일 카테고리, 동일 기간에 대해 수집한다.

```
수집 A: shopping_insight API (categories endpoint)
  - gender 필터: 'm', 'f', '' (3종)
  - age 필터: '10', '20', '30', '40', '50', '' (6종)
  - 12조합 × 카테고리 × 날짜 = 실측 joint 데이터

수집 B: persona_insight API (gender + age 별도 API)
  - gender API: 'm', 'f' 각각
  - age API: '10'~'60' 각각
  - 곱해서 persona_index 계산
```

- 대상: 30개 이상 카테고리 (성별 편향 강한 카테고리 15개 + 편향 약한 카테고리 15개)
- 기간: 6개월 이상

### 분석 절차

1. 단위 통일: anchor 카테고리로 두 데이터 소스를 동일 척도로 변환
2. 카테고리별 violation_ratio 시계열 계산 (12조합 × N일)
3. VD, VB 계산 및 카테고리 순위화
4. k-means 군집: 고위반/중위반/저위반 카테고리 그룹 분류
5. 카테고리 특성(성별 편향 지수, 계절성 강도)으로 VD 회귀 분석

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| 기존 persona_index | 독립 가정 그대로 사용 |
| 성별 편향 지수 보정 | 성별 비율로만 보정한 단순 방법 |
| 카테고리 그룹별 상한 | 본 연구가 제시하는 오차 상한 활용 |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| violation_ratio 분포 | PI와 실측 joint 간 비율의 분포 | 독립 가정이 얼마나 성립하는지 직접 측정 |
| VD (변동계수) | 카테고리별 위반 불안정성 | 시간에 따라 위반 정도가 들쑥날쑥한지 측정 |
| VB (평균 편향) | 카테고리별 체계적 과대/과소 추정 | 방향성 있는 오류인지 측정 |
| 군집 간 VD 분산 차이 | 군집의 타당성 | 군집이 실제로 의미있게 다른지 확인 |
| 회귀 R² | 카테고리 특성의 VD 설명력 | 어떤 특성이 위반을 예측하는지 확인 |

### 해석 기준

- 카테고리 간 VD 차이: Kruskal-Wallis p < 0.05 → 카테고리에 따라 위반 정도가 다름을 입증
- 군집 Silhouette Score > 0.3 → 군집 구분이 유의미함
- 고위반 카테고리의 VB > 0.3 → 평균 30% 이상 과대/과소 추정으로 실무 주의 기준 제시

## 구현 난이도: ★★☆☆☆

- 데이터 즉시 수집 가능, 수학적 계산 중심
- 30개 카테고리 추가 API 수집 비용 소요
- 단위 통일(anchor 변환) 구현이 핵심 기술 과제

## 향후 확장성

- 시간 지연(time-lag) 고려한 동적 독립성 검정
- 대안 지표: 계층적 베이즈 모델로 joint distribution 추정

---
---

# P05. 뉴스 기사 댓글 시계열 분석을 통한 사회적 임팩트 측정

## 연구 필요성 (Research Gap)

뉴스 기사 영향력 측정 연구는 주로 기사 공유 수, 인용 수에 의존하는데, 한국 뉴스
환경에서는 댓글이 핵심 반응 지표다. 그러나 **댓글 수의 시간별 누적 패턴**을 분석해
기사 임팩트를 유형화한 연구는 드물다. "언제까지 반응이 오는가", "얼마나 빠르게
반응이 모이는가"가 기사 유형마다 다를 것이라는 가설이 검증되지 않았다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Szabo & Huberman (2010). "Predicting the Popularity of Online Content." *CACM*, 53(8), 80–88. | Digg·YouTube 콘텐츠에서 초기 반응이 장기 인기를 예측한다는 선형 예측 모델 제시. 조회수·추천 수 기반. | 댓글 수 누적 곡선 자체의 수학적 모델화 없음; 뉴스 기사 맥락 미적용 |
| Wu & Huberman (2007). "Novelty and Collective Attention." *PNAS*, 104(45), 17599–17601. | 집단 관심도(뉴스 사이트 방문 등)의 지수 감쇠 패턴을 모델화. 신선도가 떨어질수록 관심이 급감하는 보편적 패턴 실증. | 단일 감쇠 모델만 제시; 지속 확산형·단발 화제형 등 복수 패턴 유형화 없음 |
| Tatar et al. (2014). "A Survey on Predicting the Popularity of Web Content." *JISA*, 5(1), 1–20. | 웹 콘텐츠 인기도 예측 기법(초기값 기반, 시계열 기반, 콘텐츠 기반) 서베이. 영어·유럽 미디어 중심. | 한국어 뉴스 환경(댓글 중심 반응 구조) 미분석; 누적 곡선 분류 없음 |
| Cheng et al. (2014). "Can Cascades be Predicted?" *WWW 2014*, 925–936. | 소셜 미디어 정보 확산(reshare) 예측. 초기 K 단계 정보로 최종 크기 예측. | 댓글 시계열 패턴 유형 분류보다 총량 예측에 집중 |

기존 연구들은 온라인 콘텐츠의 인기도를 단일 지표로 예측하는 데 초점을 맞추며, 한국어 뉴스 댓글의 누적 패턴을 Velocity·Duration·Volume 세 차원으로 분해해 기사 유형별 임팩트 궤적을 분류한 연구는 없다.

## 기여점 (Contribution)

- 댓글 누적 곡선의 수학적 모델 제안 및 파라미터 해석
- Velocity(속도)·Duration(지속)·Volume(규모) 3차원 임팩트 지표 정의
- 기사 임팩트 패턴 유형 분류 (단발 화제형 vs. 지속 확산형 등)
- 발행 후 24시간 댓글만으로 최종 임팩트 조기 예측 가능성 검증

## 제목

> *Measuring Social Impact of News Articles via Comment Count Time-Series: Velocity, Duration, and Volume Analysis*

## 초록

네이버 뉴스 기사의 사회적 임팩트를 댓글 수 시계열로 측정하는 방법을 제안한다. 기사
발행 후 댓글 누적 속도(velocity), 증가 지속 기간(duration), 총 규모(volume)의 3차원
지표를 정의하고 지수 포화 모형으로 누적 곡선을 모델링한다. AI·반도체 관련 뉴스 기사
500건 이상에 대해 발행 후 1시간·6시간·24시간·72시간·1주 시점에서 댓글 수를 수집해
임팩트 패턴을 분류하고, 24시간 데이터만으로 최종 임팩트를 예측하는 모델을 구축한다.

## 연구 내용

### 3차원 임팩트 지표 정의

```
Velocity  = (C(24h) - C(0h)) / 24    (시간당 평균 증가량, 초기 반응 속도)
Duration  = t_half                    (총 댓글의 50%가 쌓이는 데 걸린 시간)
Volume    = C(1week)                  (1주 후 누적 댓글 수, expose_count 기준)
```

### 누적 곡선 모델

```
C(t) = C_max × (1 - exp(-λ × t))    (지수 포화 모형)

파라미터 의미:
  C_max: 이론적 최대 댓글 수 (수렴값)
  λ:     반응 속도 (클수록 빠르게 수렴)
  → Velocity ≈ C_max × λ, Duration ≈ ln(2) / λ
```

### 데이터 수집 설계

```
수집 대상: Naver-hosted 기사 500건 (is_naver_hosted=TRUE)
주제: AI·반도체 (200건) + 경제 (150건) + 사회 (150건)
수집 시점:
  T+1h, T+6h, T+24h, T+72h, T+168h(1주)   ← 5 time points per article
총 API 호출: 500 × 5 = 2,500회 (Naver comment API)
```

---

## 연구 방법

### 핵심 연구 질문

> "기사 주제와 발행 시간대에 따라 댓글 누적 패턴(velocity·duration·volume)이
> 유의하게 다른 유형으로 분류되는가? 그리고 발행 24시간 내 데이터만으로
> 최종 임팩트를 정확하게 예측할 수 있는가?"

이 질문은 두 파트로 구성된다.
- **파트 1 (기술 분석)**: 패턴 유형화 — 데이터를 설명하는 연구
- **파트 2 (예측 모델)**: 조기 예측 — 유용성을 입증하는 연구

### 파트 1: 임팩트 유형 군집화

1. 기사별 누적 곡선 데이터를 지수 포화 모형으로 피팅 → (C_max, λ) 추정
2. (Velocity, Duration, Volume) 3차원 공간에서 k-means 군집 (k=3~5)
3. 군집 특성 해석: 각 군집의 기사 주제·언론사·발행 시간대 분포 비교
4. 군집 레이블링 (예: "단발 화제형", "지속 관심형", "장기 확산형")

### 파트 2: 조기 예측 모델

24시간 데이터(C(1h), C(6h), C(24h))를 feature로 사용해 1주 Volume을 예측한다.

```
Feature: C(1h), C(6h), C(24h), 기사 주제(one-hot), 발행 시간대, 언론사
Target: C(1week)
모델: Ridge Regression, Random Forest, LightGBM
```

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| 단순 선형 외삽 | C(24h) × (168/24) |
| 지수 포화 모형만 | 24h 데이터로 C_max, λ 추정 후 외삽 |
| ML 예측 모형 | 제안 방법 (feature 기반) |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| 누적 곡선 R² | 지수 포화 모형의 적합도 | 모델 전제가 데이터에 맞는지 확인. 낮으면 모형 자체를 바꿔야 함 |
| Silhouette Score | 군집 경계의 명확성 | 군집이 실제로 구분되는지, 임의로 나눈 것인지 판단 |
| MAPE (%) | 조기 예측 오차율 | 실무에서 "몇 % 오차로 예측하는가" 직관적 해석 가능 |
| 군집 간 주제 분포 χ² 검정 | 군집과 기사 주제의 독립성 | 군집이 실제로 주제와 연관되는지 검증 |

### 해석 기준

- R² > 0.85: 지수 포화 모형이 데이터에 적합함 (낮으면 이중 지수 모형 시도)
- Silhouette Score > 0.35: 군집 구분 의미 있음
- MAPE < 30%: 24시간 데이터로 1주 예측이 실용적 수준

## 구현 난이도: ★★★☆☆

- 500건 기사 × 5 시점 수집 스케줄링 파이프라인 구축 필요
- Naver comment 비공식 API 안정성 리스크 (대안: 실패 시 재시도 로직 필수)

## 향후 확장성

- 실시간 바이럴 예측 시스템으로 확장
- 반응(좋아요), 조회수 추가 시 다변량 임팩트 모델

---
---

# P06. YouTube 조회수와 네이버 쇼핑 검색량 간 그랜저 인과 분석

## 연구 필요성 (Research Gap)

소셜 미디어와 소비자 구매 의향 간 관계를 다룬 연구는 많지만, **YouTube 조회수
변화량과 동일 카테고리 쇼핑 검색량 사이의 선행·후행 관계를 한국 데이터로
실증한 연구**는 거의 없다. "영상이 트렌드를 주도하는가(creator-led)" vs.
"트렌드가 영상 소비를 유도하는가(trend-following)" 두 가설을 데이터로 구분하려면
Granger 인과 검정이 적합하다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Granger, C. W. J. (1969). "Investigating Causal Relations by Econometric Models and Cross-Spectral Methods." *Econometrica*, 37(3), 424–438. | Granger 인과성 개념 원논문. VAR 모델로 시계열 X가 Y를 예측하는 데 유용한가를 검정하는 방법론 확립. | 인과 방향 분류의 방법론적 토대만 제공; 미디어-쇼핑 도메인 적용 없음 |
| Choi & Varian (2012). "Predicting the Present with Google Trends." *The Economic Record*, 88(S1), 2–9. | 검색 트렌드가 소비·고용·자동차 판매 등 현재 경제 지표의 선행 예측에 유용함을 실증. | YouTube 조회수와 쇼핑 검색량 사이의 인과 방향 분석 없음 |
| Tirunillai & Tellis (2012). "Does Chatter Really Matter? Dynamics of UGC and Stock Performance." *Marketing Science*, 31(2), 198–215. | UGC(온라인 구전) 지표(볼륨, 감성)와 주가 간 그랜저 인과 분석. UGC → 주가 방향이 더 일반적임을 실증. | YouTube 조회수 특이성 미분석; 쇼핑 검색량과의 연계 없음 |
| Jun et al. (2018). "Ten Years of Research Change Using Google Trends." *Technological Forecasting and Social Change*, 130, 69–87. | 2006–2016년 Google Trends 활용 연구 리뷰. 선행 지표 활용이 주류임을 확인. | YouTube 조회수-쇼핑 트렌드 상호작용 연구 부재를 간접 확인 |

기존 문헌들은 Google Trends나 SNS 구전 지표를 한 방향(검색→소비)으로 활용하는 데 집중하며, YouTube 조회수와 네이버 쇼핑 검색량 사이의 양방향 인과 관계를 카테고리별로 분류한 연구는 없다.

## 기여점 (Contribution)

- YouTube 주간 조회수 delta와 쇼핑 pseudo_volume의 이종 시계열 정렬 방법
- VAR 모델 기반 Granger 인과 방향 분류 (YouTube→쇼핑 / 쇼핑→YouTube / 양방향 / 무관)
- 카테고리 유형별 인과 패턴과 최적 lead/lag 기간 분석
- 마케팅 전략 시사점 도출 (어떤 카테고리에서 YouTube 마케팅이 효과적인가)

## 제목

> *Creator-Led or Trend-Following? Granger Causality Analysis Between YouTube View Counts and Naver Shopping Search Volume*

## 초록

YouTube 영상 조회수와 네이버 쇼핑 검색량 간의 인과 관계를 그랜저 검정으로 분석한다.
패션·전자제품·스포츠 등 5개 이상 카테고리에 대해 YouTube 주간 조회수 delta와 쇼핑인사이트
pseudo_volume을 52주 이상 수집·정렬하고, VAR 모형 기반 그랜저 검정으로 인과 방향과
최적 lag를 도출한다. 결과를 마케팅 전략 관점에서 해석하고, YouTube 조회수가 쇼핑
트렌드의 선행 지표로 유용한 카테고리 유형을 규명한다.

## 연구 내용

### 핵심 도전: 이종 시계열 정렬

두 시계열은 출처, 단위, 시간 해상도가 다르다.

```
YouTube: 영상별 주간 조회수 delta (delta_views)
  → 카테고리 집계: 해당 카테고리 영상 N편의 delta_views 합산
  → 주간 시계열

Naver 쇼핑: 카테고리별 일간 pseudo_volume
  → 주간 집계: 7일 평균

카테고리 매핑: YouTube category_id ↔ 네이버 카테고리 수동 매핑
  예) YouTube "Howto & Style"(category_id=26) → 네이버 "패션의류"(50000148)
```

### 분석 절차

```
1. 단위근 검정 (ADF test): 비정상 시계열 → 차분 변환
2. 최적 lag 선택: VAR 모형 AIC/BIC 기준, lag=1~12주 탐색
3. Granger 인과 검정:
   H0: "YouTube delta가 쇼핑 예측에 추가 정보를 주지 않는다"
   H0: "쇼핑 volume이 YouTube 예측에 추가 정보를 주지 않는다"
4. Impulse Response Function: 충격 발생 후 몇 주까지 반응이 지속되는가
5. 카테고리별 결과 비교 및 패턴 분류
```

---

## 연구 방법

### 핵심 연구 질문

> "YouTube 주간 조회수 변화량이 네이버 쇼핑 검색량 변화를 Granger-cause 하는가,
> 아니면 그 반대인가? 그리고 이 방향이 카테고리에 따라 다른가?"

### 실험 설계

**데이터 수집**

```
YouTube 조회수:
  - 카테고리별 대표 채널 10개 이상 선정
  - 각 채널의 영상 목록 수집 → active_meta_youtube에서 주간 delta_views 집계
  - 기간: 52주 이상 (최소 1년)

Naver 쇼핑:
  - 동일 카테고리 pseudo_volume (이미 수집된 데이터 활용)
  - 일간 → 주간 평균으로 리샘플링
```

**카테고리 매핑 테이블** (수동 구축 필요)

| YouTube 카테고리 | 네이버 카테고리 | 매핑 신뢰도 |
|----------------|--------------|-----------|
| Howto & Style (26) | 패션의류 (50000148) | 높음 |
| Sports (17) | 스포츠/레저 (50000167) | 높음 |
| Science & Technology (28) | 전자제품 (50000542) | 중간 |

**Robustness Check**

```
계절성 제거 후 동일 분석 반복 (STL 분해 잔차 사용)
→ 결과가 계절성에 의한 허위 인과인지 확인
```

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| 단변량 ARIMA | YouTube만으로 쇼핑 예측 (인과 없다는 가정) |
| VAR (인과 고려) | 제안 방법 (Granger 인과 방향 활용) |
| 교차 상관 분석 | 기존 단순 correlation 방법 (인과 방향 구분 불가) |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| Granger F-test p-value | 인과 관계의 통계적 유의성 | 연구 핵심 질문에 대한 직접 답변 |
| 최적 lag (주) | 효과가 나타나는 데 걸리는 시간 | 마케팅 관점에서 "YouTube 게시 후 몇 주 뒤 효과가 나타나는가" |
| VAR 예측 RMSE | Granger 인과 활용한 예측 정확도 | 인과 관계가 실용적으로 도움이 되는지 검증 |
| IRF (Impulse Response) 지속 기간 | 충격 후 효과가 몇 주 유지되는가 | 효과의 크기와 지속성 파악 |

### 해석 기준

- Granger F-test p < 0.05: 인과 관계 존재
- VAR RMSE < ARIMA RMSE: Granger 인과 정보가 예측에 실제로 도움됨
- 카테고리 간 인과 방향 패턴 차이: χ² 검정 p < 0.05

## 구현 난이도: ★★★☆☆

- YouTube 카테고리 매핑 테이블 수동 구축이 핵심 병목
- 시계열 분석 라이브러리(statsmodels) 사용으로 구현 자체는 용이

## 향후 확장성

- 인플루언서 구독자 규모별 인과 강도 비교
- 멀티채널(인스타·틱톡) 추가 시 다변량 인과 모델

---
---

# P07. RAG 기반 한국어 도메인 Q&A: 뉴스 기사 지식베이스

## 연구 필요성 (Research Gap)

RAG(Retrieval-Augmented Generation)는 LLM 환각을 줄이고 최신 정보를 반영하는
방법으로 주목받는다. 그러나 **한국어 기술 도메인(AI·반도체) 뉴스 기사를 지식베이스로
사용한 RAG 시스템의 체계적 평가 연구**는 드물다. 특히 청킹 전략과 검색 방법 조합이
성능에 미치는 영향을 한국어 특성(교착어, 전문 용어)과 연결해 분석한 연구가 없다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Lewis et al. (2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." *NeurIPS*, 33, 9459–9474. | RAG 원논문. DPR 검색기와 BART 생성기를 결합해 오픈 도메인 QA에서 파인튜닝 없이 지식 주입. | 영어 Wikipedia 기반; 한국어 기술 도메인 뉴스 지식베이스 적용 미검증 |
| Karpukhin et al. (2020). "Dense Passage Retrieval for Open-Domain QA." *EMNLP*, 6769–6781. | DPR 제안. 이중 인코더(bi-encoder) 구조로 dense 검색 성능을 BM25 대비 크게 향상. | 한국어 교착어 특성·도메인 전문 용어 환경에서의 성능 평가 없음 |
| Robertson & Zaragoza (2009). "The Probabilistic Relevance Framework: BM25 and Beyond." *Foundations and Trends in IR*, 3(4), 333–389. | BM25 알고리즘 이론 및 확장. 한국어 형태소 처리(Mecab·Kiwi)와 결합 시 성능 변화 미분석. | 교착어 특성 고려 없음 |
| Es et al. (2023). "RAGAS: Automated Evaluation of Retrieval Augmented Generation." arXiv:2309.15217. | RAG 자동 평가 프레임워크 RAGAS 제안. Faithfulness·Answer Relevancy·Context Precision 등 4가지 지표로 구성. | 영어 도메인 중심 설계; 한국어 평가 데이터셋 없음 |
| Reimers & Gurevych (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks." *EMNLP*, 3982–3992. | Siamese 네트워크 기반 문장 임베딩으로 의미 검색 성능 대폭 향상. 다국어 확장판(paraphrase-multilingual-mpnet-base-v2) 포함. | 한국어 기술 뉴스 도메인 검색 성능 평가 없음 |

기존 RAG 연구들은 영어 오픈 도메인 QA를 중심으로 평가하며, 한국어 교착어 특성·기술 전문 용어·뉴스 기사 특화 청킹 전략이 RAG 성능에 미치는 영향을 체계적으로 분석한 연구는 없다.

## 기여점 (Contribution)

- 한국어 뉴스 기사 특화 청킹 전략 4종 비교
- Dense/Sparse/Hybrid 검색 방법 한국어 도메인 성능 비교
- RAGAS 프레임워크 기반 자동 평가 파이프라인 구축
- 무료 LLM(llama-3.1-8b)의 한국어 RAG 실용 성능 측정

## 제목

> *Korean Domain-Specific RAG: A Comparative Study of Chunking Strategies and Retrieval Methods for Technical News Q&A*

## 초록

한국어 AI·반도체 뉴스 기사 1,000건 이상을 지식베이스로 구축하고 RAG 시스템의
청킹 전략(4종) × 검색 방법(3종) 조합 12가지를 체계적으로 비교 평가한다. 평가 데이터셋은
100개 질문-정답-근거 기사 트리플렛으로 구성하고, RAGAS 자동 평가 지표와 인간 평가를
병행한다. 분석 결과로 한국어 기술 도메인 Q&A에 가장 효과적인 구성을 규명하고
무료 LLM의 실용 수준을 측정한다.

## 연구 내용

### 파이프라인 전체 구조

```
[meta_naver_news.content]
        ↓
  청킹 (4종 중 하나 선택)
        ↓
  임베딩 (paraphrase-multilingual-mpnet-base-v2, 768차원)
        ↓ pgvector 저장
  [검색 단계]
  쿼리 입력 → 임베딩 → 유사도 검색
        ↓ (3종 검색 방법 중 하나)
  top-K 청크 검색
        ↓
  [생성 단계]
  프롬프트: "아래 문서를 참고해 질문에 답하라. [청크들] [질문]"
  LLM (llama-3.1-8b via Groq)
        ↓
  답변 생성
```

### 청킹 전략 4종

| 전략 | 방법 | 청크 크기 |
|------|------|---------|
| 고정 크기 | 512 토큰 단위 단순 분할 | ~512 |
| 문단 경계 | '\n\n' 기준 분할 | 가변 |
| 문장 경계 | 문장 단위 + 최대 300 토큰 합산 | ~300 |
| 의미 단위 | 소제목·단락 구조 감지 후 분할 | 가변 |

### 검색 방법 3종

| 방법 | 설명 |
|------|------|
| Dense | pgvector cosine 유사도 검색 |
| Sparse | BM25 (Elasticsearch 또는 rank_bm25) |
| Hybrid | Dense + Sparse 점수를 RRF(Reciprocal Rank Fusion)로 결합 |

---

## 연구 방법

### 핵심 연구 질문

> "한국어 기술 도메인 뉴스 Q&A에서, 어떤 청킹 전략과 검색 방법의 조합이
> 가장 높은 Faithfulness와 Answer Relevancy를 달성하는가?"

청킹은 **무엇을 검색 단위로 볼 것인가**의 문제,
검색은 **어떻게 그 단위를 찾을 것인가**의 문제다.
두 선택이 독립적이지 않기 때문에 모든 조합을 실험해야 한다.

### 평가 데이터셋 구축 (가장 중요한 작업)

```
구축 방법:
  1. 뉴스 기사 1,000건에서 핵심 사실 문장 200개 추출
  2. 각 문장에서 질문 생성 (LLM 보조 + 인간 검토)
  3. 질문-정답-근거 기사 트리플렛 100개 최종 선정
  4. 2인 평가자 교차 검증 (Cohen's Kappa > 0.6 목표)

질문 유형 분포:
  단일 사실 확인 50%: "삼성전자가 HBM4 양산 목표 시기는?"
  비교 분석 30%:      "A사와 B사의 AI 반도체 전략 차이는?"
  추론 필요 20%:      "GPU 수요 증가가 HBM 시장에 미치는 영향은?"
```

### Ablation 실험 설계

```
변수 1 (청킹): 고정 | 문단 | 문장 | 의미   ← 4종
변수 2 (검색): Dense | Sparse | Hybrid    ← 3종
총 조합: 4 × 3 = 12가지

각 조합에 100개 질문 적용 → 1,200개 답변 생성
```

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| No RAG | LLM만 사용, 지식베이스 없음 |
| BM25 + 고정 청킹 | 기존 키워드 검색 기반 RAG |
| Dense + 문단 청킹 | 현재 가장 일반적인 RAG 구성 |
| 최적 조합 | 제안 실험에서 도출된 최고 성능 조합 |

### RAGAS 4개 지표와 측정 대상 연결

| RAGAS 지표 | 측정 대상 | 연결 이유 |
|-----------|----------|----------|
| Faithfulness | 답변이 검색된 문서에 근거하는가 | LLM 환각 측정. RAG의 핵심 존재 이유 |
| Answer Relevancy | 답변이 질문에 얼마나 적절한가 | 검색이 틀린 문서를 가져와도 답변이 맞아 보이는 경우 탐지 |
| Context Precision | 검색된 문서 중 관련 있는 것의 비율 | 청킹 전략의 품질 직접 반영 |
| Context Recall | 답변에 필요한 정보가 검색됐는가 | 검색 방법의 재현율 반영 |

각 지표가 청킹 전략과 검색 방법 중 **어느 쪽에 더 민감한지**도 분석한다.
(Context Precision/Recall → 청킹 영향이 크다고 예상, Faithfulness → 검색 영향이 크다고 예상)

### 해석 기준

- Faithfulness > 0.7: 답변이 문서에 기반함 (환각 수준 허용 범위)
- Context Recall > 0.6: 필요한 정보의 60% 이상을 검색이 가져옴
- 청킹 전략 간 주요 지표 차이: Kruskal-Wallis p < 0.05

## 구현 난이도: ★★★★☆

- 평가 데이터셋 100개 트리플렛 구축이 가장 큰 병목 (2~3주 소요)
- BM25 + pgvector 하이브리드 검색 구현 필요
- Groq API rate limit 내 1,200개 답변 생성 일정 관리 필요

## 향후 확장성

- 멀티홉 Q&A (여러 기사를 조합해야 답할 수 있는 질문)
- 시간 인식 RAG: 질문의 시점과 기사 발행일 매칭

---
---

# P08. 계층적 벡터 검색을 이용한 이종 미디어 데이터셋 탐색

## 연구 필요성 (Research Gap)

벡터 검색 연구 대부분은 **단일 컬렉션 내 유사 아이템 탐색**에 집중한다. 그러나
YouTube 영상과 뉴스 기사가 혼재하는 환경에서 "어떤 데이터셋에 무엇이 있는가"를
의미 기반으로 탐색하는 **계층적 데이터셋 탐색** 연구는 없다. 특히 데이터셋 레벨
벡터 검색과 아이템 레벨 벡터 검색을 결합해 효율성과 정확도를 동시에 달성하는
아키텍처 연구가 부재하다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Malkov & Yashunin (2018). "Efficient and Robust ANN Search Using HNSW." *IEEE TPAMI*, 42(4), 824–836. | HNSW 알고리즘 제안. 계층적 그래프 구조로 대규모 단일 컬렉션 내 ANN 검색을 높은 정밀도·속도로 수행. | 이종 미디어 다중 컬렉션 계층 탐색 미지원; 데이터셋 레벨 필터링 개념 없음 |
| Johnson, Douze & Jégou (2019). "Billion-Scale Similarity Search with GPUs (FAISS)." *IEEE Trans. Big Data*, 7(3), 535–547. | FAISS 라이브러리로 GPU 기반 수십억 벡터 인덱싱·검색 최적화. IVF, PQ 양자화 등 다양한 인덱스 전략 제공. | 단일 플랫 인덱스 최적화; 데이터셋→아이템 drill-down 계층 구조 없음 |
| Reimers & Gurevych (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks." *EMNLP*, 3982–3992. | 다국어 임베딩 모델(paraphrase-multilingual-mpnet-base-v2). 텍스트 의미 유사도 기반 검색의 기반 모델 역할. | YouTube 영상 텍스트 메타데이터와 뉴스 기사의 cross-modal 혼합 검색 평가 없음 |
| Yao et al. (2021). "FILIP: Fine-grained Interactive Language-Image Pre-Training." arXiv:2111.07783. | 이종 미디어(텍스트-이미지) 간 fine-grained 상호작용으로 cross-modal 검색 성능 향상. | 영상 텍스트 메타+뉴스 기사 텍스트 혼합 검색을 계층 구조로 제공하는 방법 미제시 |

기존 벡터 검색 연구들은 단일 대규모 컬렉션 내 ANN 최적화에 집중하며, 데이터셋 레벨 coarse 검색과 아이템 레벨 fine 검색을 결합해 이종 미디어 데이터셋을 계층적으로 탐색하는 아키텍처를 제안한 연구는 없다.

## 기여점 (Contribution)

- 데이터셋 레벨(coarse) + 아이템 레벨(fine) 2단계 계층적 벡터 검색 아키텍처 제안
- 단계별 필터링 효과: 1단계 데이터셋 필터가 검색 공간을 얼마나 줄이는가 정량화
- 이종 미디어(YouTube 영상 ↔ 뉴스 기사) 간 cross-modal 탐색 가능성 검토
- 정확도-속도 트레이드오프 분석 (K값에 따른 변화)

## 제목

> *Hierarchical Vector Search for Heterogeneous Media Dataset Discovery: Coarse Dataset Filtering with Fine-Grained Item Retrieval*

## 초록

YouTube 영상과 뉴스 기사가 혼재하는 이종 미디어 환경에서 자연어 질의로 관련 콘텐츠를
탐색하는 2단계 계층적 벡터 검색 시스템을 제안한다. 1단계에서 데이터셋 description 임베딩
(dcat_dataset_vec)으로 관련 데이터셋 K개를 추려내고, 2단계에서 그 데이터셋 내 아이템
임베딩(meta_*_vec)에서 세부 결과를 반환한다. 전체 컬렉션 Flat 검색과 비교해 응답 시간과
검색 정확도를 측정하고, cross-modal 탐색 시나리오(영상 쿼리로 관련 기사 탐색)도 평가한다.

## 연구 내용

### 2단계 검색 아키텍처

```
질의 입력: "HBM 반도체 공정 기술"
        ↓ 임베딩
[L1] dcat_dataset_vec에서 유사 데이터셋 top-K 검색
        → K=3이면: youtube_samsung_official, naver_news_ai, user_hbm_collection 선택
        ↓
[L2] 선택된 K개 데이터셋의 meta_*_vec에서만 유사 아이템 검색
        → meta_youtube_video_vec ∪ meta_naver_news_vec 대상으로 검색
        ↓
최종 결과 반환 (데이터셋 정보 + 아이템 정보 포함)
```

### 검색 공간 축소 효과

```
전체 아이템 수: N
K개 데이터셋 선택 후 검색 대상: n  (n << N)
공간 축소율: (N - n) / N × 100%
```

K가 작을수록 속도는 빠르지만 관련 아이템을 놓칠 위험 증가.
K값에 따른 정확도-속도 트레이드오프 곡선을 그린다.

### Cross-modal 탐색 시나리오

```
시나리오 1: 영상 쿼리 → 관련 뉴스 기사
  "삼성 HBM 영상을 보고 관련 최신 뉴스 기사를 찾아줘"

시나리오 2: 기사 쿼리 → 관련 영상
  "AI 데이터센터 전력 소비 기사와 관련된 YouTube 영상을 찾아줘"
```

---

## 연구 방법

### 핵심 연구 질문

> "2단계 계층적 검색이 전체 Flat 검색 대비 응답 시간을 줄이면서도
> 검색 정확도 손실이 통계적으로 무시 가능한 수준인가?"

정확도 손실 없이 속도가 빨라지면 계층 구조가 의미 있다.
정확도가 크게 떨어지면 K값을 늘려야 한다 → 트레이드오프 분석 필요.

### 실험 1: 정확도-속도 트레이드오프

```
변수: K = 1, 2, 3, 5, 10, "전체"(Flat)
측정: 각 K에서 응답 시간(ms)과 검색 정확도(MRR@10, Recall@10)
결과: 정확도-속도 트레이드오프 곡선 작성
```

### 실험 2: 데이터 규모별 확장성

```
아이템 수: 1K, 5K, 10K, 50K (시뮬레이션 또는 실제 수집)
각 규모에서 Flat vs. 계층 검색 응답 시간 비교
→ 규모가 클수록 계층 검색의 이점이 커지는지 확인
```

### 실험 3: Cross-modal 탐색 평가

동일 주제 영상-기사 쌍 30개를 수동 레이블링하고,
영상 설명으로 관련 기사를 검색했을 때 recall을 측정한다.

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| Flat Dense | 전체 아이템 대상 단일 벡터 검색 |
| Source-type Filter | 소스 타입으로 먼저 필터링 후 검색 |
| 계층 검색 (K=3) | 제안 방법 |
| 계층 검색 (K=5) | 제안 방법 (K 변형) |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| MRR@10 | 첫 번째 관련 결과의 순위 역수 평균 | 사용자가 처음 보는 결과의 품질 측정 |
| Recall@10 | 정답 중 상위 10개 안에 있는 비율 | 계층 검색이 관련 결과를 놓치는지 측정 |
| 응답 시간 (ms) | 쿼리당 처리 시간 | 속도 이점의 실질적 크기 측정 |
| Cross-modal Recall | 영상-기사 쌍 정답 회수율 | 이종 미디어 탐색 가능성 입증 |

### 해석 기준

- MRR@10: 계층(K=3) vs. Flat 차이 < 0.05 → 정확도 손실 무시 가능
- 응답 시간: 10만 건 기준 계층 검색이 Flat 대비 50% 이상 단축
- Cross-modal Recall@5: 60% 이상 → 이종 미디어 탐색 실용 수준

## 구현 난이도: ★★★☆☆

- pgvector HNSW 인덱스로 구현 가능, 추가 라이브러리 불필요
- 평가용 Query-Relevance 쌍 50개 수동 구축 필요
- Cross-modal 쌍 레이블링 30건 필요

## 향후 확장성

- 3레벨 계층 (소스 타입 → 데이터셋 → 아이템)
- 사용자 피드백 기반 데이터셋 레벨 임베딩 fine-tuning

---
---

# P09. YouTube 썸네일+텍스트 멀티모달 임베딩을 이용한 영상 검색 성능 향상

## 연구 필요성 (Research Gap)

YouTube 영상 검색 시스템은 제목·설명·태그 등 텍스트 메타데이터에 의존한다. 그러나
썸네일은 영상 내용을 압축한 시각 요약으로, 텍스트에서 드러나지 않는 정보(등장 제품,
화면 구성, 감성 톤)를 담는다. **CLIP 모델 기반 썸네일 시각 임베딩을 텍스트 임베딩과
결합해 한국어 YouTube 도메인 검색 성능을 향상시키는 연구**는 발표된 바 없다.

특히 기술 설명형(다이어그램 중심)·인물형(얼굴 중심)·제품형 썸네일처럼 시각 정보의
밀도가 카테고리마다 다른 환경에서 융합 가중치를 최적화하는 방법도 명확하지 않다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Radford et al. (2021). "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*. | 이미지-텍스트 대조 학습으로 zero-shot 이미지 분류·텍스트-이미지 검색의 강력한 기반 모델 확립. | 한국어 도메인 YouTube 검색에의 직접 적용 및 평가 없음 |
| Fang et al. (2021). "CLIP2Video: Mastering Video-Text Retrieval via Image CLIP." arXiv:2106.11097. | 프레임 단위 CLIP 임베딩을 시간 집계해 비디오-텍스트 검색에 적용. 영어 데이터셋(MSR-VTT) 중심. | 썸네일 단일 프레임 활용 및 한국어 메타데이터 텍스트 임베딩과의 융합 평가 없음 |
| Reimers & Gurevych (2019). "Sentence-BERT." *EMNLP*, 3982–3992. | 다국어 텍스트 임베딩 모델. 한국어 포함 검색에 활용됨. | 시각 채널과의 융합 방법 및 최적 가중치 미제시 |
| Li et al. (2022). "BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation." *ICML*. | 이미지-텍스트 통합 모델로 검색·캡션 생성·VQA를 단일 아키텍처로 처리. | 한국어 도메인 적용 평가 없음; 카테고리별 시각 정보 기여도 분석 없음 |

기존 멀티모달 검색 연구들은 영어 대규모 데이터셋에서의 성능을 중심으로 평가하며, 한국어 YouTube 도메인에서 썸네일 임베딩과 텍스트 임베딩의 최적 융합 비율 및 카테고리별 효과를 분석한 연구는 없다.

## 기여점 (Contribution)

- CLIP 썸네일 임베딩 + 다국어 텍스트 임베딩 late fusion 검색 파이프라인 구축
- 텍스트 단독 vs. 시각 단독 vs. late fusion 3방향 비교 실험
- 콘텐츠 카테고리(기술 설명형·인물형·제품형)별 최적 융합 가중치 분석
- meta_youtube_video_vec 확장: 시각 임베딩 컬럼 추가 설계

## 제목

> *Multimodal Video Retrieval via Thumbnail-Text Fusion Embeddings for Korean YouTube Content*

## 초록

YouTube 영상 검색 시스템은 제목·설명·태그 등 텍스트 메타데이터에 의존하며 썸네일의 시각
정보를 활용하지 못한다. 본 연구는 CLIP ViT-B/32로 추출한 썸네일 시각 임베딩과 다국어
텍스트 임베딩을 late fusion 방식으로 결합해 검색 성능을 향상시키는 방법을 제안한다.
한국어 AI·반도체 도메인 YouTube 영상 1,000개와 50개 테스트 쿼리로 MRR·NDCG@10 개선
효과를 실증하고, 시각 정보가 도움이 되는 콘텐츠 유형을 카테고리별로 분석한다.

## 연구 내용

### 1단계: 임베딩 추출

```
썸네일 URL → 다운로드 → CLIP ViT-B/32 → 512-dim 시각 벡터 v_img
제목 + 설명 → paraphrase-multilingual-mpnet-base-v2 → 768-dim → PCA 512-dim v_txt
```

### 2단계: Fusion 방법 비교

```
Late Fusion:   score = α × sim(q_img, d_img) + (1-α) × sim(q_txt, d_txt)
               α ∈ {0.1, 0.3, 0.5, 0.7, 0.9}

Concat Fusion: [v_img ; v_txt] → 1024-dim 벡터 (단순 concatenation)
Learned Fusion: linear(α) 파라미터를 validation 쿼리 20개로 학습
```

### 3단계: 카테고리별 분석

```
기술 설명형 (다이어그램·슬라이드 썸네일) → 시각 정보 고밀도 → α 높을 것
인물형 (얼굴 중심 썸네일)                → 텍스트 보완 필요 → α 낮을 것
제품형 (제품·패키지 썸네일)              → 시각 정보 중간
```

---

## 연구 방법

### 핵심 연구 질문

> "썸네일 시각 임베딩을 텍스트 임베딩과 결합했을 때 텍스트 단독 대비 검색 정확도가
> 유의미하게 향상되는가? 향상 효과는 콘텐츠 카테고리에 따라 다른가?"

### 실험 1: 쿼리셋 구축 및 Relevance 레이블링

50개 한국어 테스트 쿼리를 작성하고 영상 1,000개에 대해 상위 20개 후보의 관련성을
2인 독립 레이블로 수동 평가 (관련/부분관련/무관).

### 실험 2: 가중치 탐색 (Validation)

Validation 쿼리 20개로 α를 그리드 탐색해 MRR@10이 최대인 α를 선택한다.

### 실험 3: 카테고리별 효과 분석

썸네일 유형(기술 설명형·인물형·제품형)별로 그룹을 나눠
각 그룹에서 최적 α와 MRR 향상 폭을 비교한다.

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| Text-only | 텍스트 임베딩 단독 (paraphrase-multilingual-mpnet-base-v2) |
| Visual-only | CLIP 썸네일 임베딩 단독 |
| Late Fusion (최적 α) | 제안 방법 |
| Concat Fusion | 벡터 단순 연결 |
| Learned Fusion | Validation으로 학습된 가중치 |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| MRR@10 | 첫 관련 결과의 순위 역수 평균 | 사용자 첫 클릭 품질을 직접 측정 |
| NDCG@10 | 상위 10개 순위 가중 품질 | 전반적 검색 목록 품질 평가 |
| Recall@10 | 정답 중 상위 10개 안에 포함된 비율 | 시각 정보가 관련 결과를 더 많이 회수하는지 |
| 카테고리별 MRR | 썸네일 유형 그룹별 성능 분해 | 시각 정보 기여도가 콘텐츠 유형에 따라 다른지 확인 |

### 해석 기준

- Late Fusion MRR@10 > Text-only + 0.05 → 시각 정보의 실질적 기여 입증
- Wilcoxon signed-rank test p < 0.05 → 통계적 유의성 확보
- 기술 설명형 MRR 향상 > 인물형 MRR 향상 → 카테고리 가설 검증

## 구현 난이도: ★★★☆☆

- CLIP CPU 추론 가능 (썸네일 1,000개 배치 약 30–40분)
- 평가 쿼리 50개 + relevance 레이블 수동 작업이 주요 비용
- meta_youtube_video_vec에 visual_embedding 컬럼 추가 필요

## 향후 확장성

- 썸네일 단일 프레임 → 영상 대표 프레임 3장 샘플링으로 확장
- 썸네일 변경 감지: 리그랜트 후 A/B 썸네일 교체 탐지
- CLIP fine-tuning으로 한국어 기술 도메인 특화

---
---

# P10. 비전-언어 모델을 이용한 YouTube 썸네일 메타데이터 자동 생성

## 연구 필요성 (Research Gap)

P03(트랜스크립트 기반 LLM 메타데이터 생성)은 텍스트 채널만 활용한다. 그러나
썸네일에는 **제품·인물·감성 톤처럼 트랜스크립트에 언급되지 않는 시각 정보**가
존재한다. 비전-언어 모델(VLM)을 이용해 썸네일에서 구조화 메타데이터를 추출하고
트랜스크립트 기반 메타데이터와의 보완 관계를 실증한 연구는 없다.

특히 GPU 없는 환경에서 Groq 무료 Vision API를 통해 이 파이프라인을 실용적으로
구현할 수 있는지의 검증도 연구 가치가 있다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Liu et al. (2023). "Visual Instruction Tuning (LLaVA)." *NeurIPS*, 36. | 시각 인스트럭션 튜닝으로 이미지에 대한 자유형식 질문 응답 가능한 VLM 공개. 한국어 입력·출력 지원 가능. | 한국어 YouTube 도메인 구조화 메타데이터 추출 평가 없음 |
| Zhu et al. (2023). "MiniGPT-4: Enhancing Vision-Language Understanding." arXiv:2304.10592. | 소형(7B) VLM으로 고품질 이미지 설명·추론 가능. | 제목·썸네일 보완 관계 분석 없음 |
| Radford et al. (2021). "CLIP." *ICML*. | 이미지-텍스트 정렬 모델로 이미지 분류·검색 광범위 활용. | 구조화 메타데이터 생성(자유 형식 텍스트 출력) 불가 |
| Zhang et al. (2023). "Video-LLaMA: An Instruction-tuned Audio-Visual Language Model for Video Understanding." *EMNLP (Demo)*. | 비디오 프레임+오디오를 LLM에 결합해 영상 내용 이해. | 썸네일 단일 이미지 → 구조화 메타 추출 실용성 평가 없음 |

기존 VLM 연구들은 일반 이미지 이해 능력 향상에 집중하며, 한국어 YouTube 썸네일에서 트랜스크립트가 담지 못하는 신규 메타데이터를 추출하고 검색 성능 향상으로 연결하는 end-to-end 평가가 없다.

## 기여점 (Contribution)

- VLM 썸네일 메타데이터 4종 추출 파이프라인 (visual_summary·dominant_objects·visual_emotion·layout_type)
- 트랜스크립트 LLM 메타 vs. VLM 썸네일 메타의 정보 보완성 정량화 (Jaccard 기반 신규 정보 비율)
- 트랜스크립트 없는 영상(has_content=FALSE)에서 VLM 대체 활용 가능성 실증
- Groq Vision API 무료 tier로의 실용적 파이프라인 구현 및 비용·품질 분석

## 제목

> *Vision-Language Models for Automated Thumbnail Metadata Generation in Korean YouTube Content*

## 초록

YouTube 영상 썸네일은 콘텐츠의 시각적 요약을 담고 있으나 기존 메타데이터 자동 생성 연구는
트랜스크립트 텍스트에 편중되어 있다. 본 연구는 비전-언어 모델(LLaVA 계열, Groq Vision API)을
통해 썸네일에서 시각적 메타데이터 4종(시각 요약·주요 객체·감성·레이아웃 유형)을 자동 추출하는
파이프라인을 구축하고, 트랜스크립트 기반 LLM 메타데이터와의 보완성을 실험적으로 검증한다.
특히 트랜스크립트가 없는 영상에서 VLM이 실용적 대체 수단이 될 수 있는지를 중점 평가한다.

## 연구 내용

### 1단계: VLM 추론 파이프라인

```
썸네일 URL 다운로드
    ↓
Groq Vision API (llava-v1.5-7b) 호출
    ↓ 프롬프트:
    "다음 YouTube 썸네일을 분석하여 JSON 형식으로 출력하라:
     visual_summary (1문장), dominant_objects (최대 3개 배열),
     visual_emotion (positive/neutral/dramatic/humorous 중 1개),
     layout_type (face-centered/diagram/product/collage 중 1개)"
    ↓
JSON 파싱 → meta_youtube_video_ai 확장 컬럼에 저장
```

### 2단계: 정보 보완성 분석

```
LLM 트랜스크립트 키워드 집합: K_transcript
VLM 썸네일 키워드 집합: K_visual

Jaccard 유사도 = |K_transcript ∩ K_visual| / |K_transcript ∪ K_visual|
신규 정보 비율 = |K_visual \ K_transcript| / |K_visual|
```

신규 정보 비율이 높을수록 두 채널이 상호 보완적임을 의미한다.

### 3단계: Ablation 검색 실험

```
조건 A: API 메타만 (제목+설명+태그)
조건 B: A + 트랜스크립트 LLM 메타
조건 C: A + VLM 썸네일 메타
조건 D: A + B + C (전체 결합)
```

---

## 연구 방법

### 핵심 연구 질문

> "VLM이 썸네일에서 추출한 시각 메타데이터는 트랜스크립트가 포착하지 못하는 신규 정보를
> 충분히 포함하며, 이를 추가했을 때 검색 성능이 유의미하게 향상되는가?"

### 실험 1: VLM 메타데이터 품질 인간 평가

100개 영상의 visual_summary를 3인이 1–5점으로 평가 (정확성·구체성·유용성).
GPT-4V 생성 결과를 upper bound baseline으로 병행 평가한다.

### 실험 2: 정보 보완성 분석

has_content=TRUE 그룹 (트랜스크립트 있음) vs. has_content=FALSE 그룹에서 각각
신규 정보 비율을 측정해 트랜스크립트 유무에 따른 VLM 기여도를 비교한다.

### 실험 3: 4조건 Ablation 검색 실험

50개 테스트 쿼리로 A·B·C·D 조건의 MRR@10·NDCG@10을 비교하고
Friedman 검정으로 조건 간 유의 차이를 확인한다.

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| 조건 A (Baseline) | API 메타데이터 텍스트 임베딩만 |
| 조건 B | A + 트랜스크립트 LLM 메타 (P03 방법) |
| 조건 C | A + VLM 썸네일 메타 (제안 방법) |
| 조건 D | A + B + C (최대 결합) |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| Human Rating (1–5) | VLM 메타데이터 품질 | 자동 지표가 없는 생성 품질의 직접 측정 |
| 신규 정보 비율 (%) | VLM 전용 키워드 비율 | 보완성의 정도를 정량화 |
| MRR@10 | 검색 정확도 | 생성 메타가 실제 검색에 기여하는지 |
| NDCG@10 | 검색 순위 품질 | 전반적 목록 향상 측정 |
| Friedman p-value | 4조건 간 차이 유의성 | 조건별 성능 차이가 우연이 아님을 확인 |

### 해석 기준

- Human Rating 평균 ≥ 3.5 → 실용 수준의 VLM 메타데이터 품질
- 신규 정보 비율 > 30% → 트랜스크립트와 충분히 독립적인 정보 제공
- 조건 C가 조건 A 대비 MRR@10 > +0.03 → VLM 메타의 검색 기여 입증

## 구현 난이도: ★★★★☆

- Groq Vision API 무료 tier 가용 여부 및 한국어 JSON 출력 안정성 사전 확인 필요
- 100개 영상 인간 레이블링이 주요 비용
- VLM 프롬프트 엔지니어링 및 JSON 파싱 오류 처리 필요
- meta_youtube_video_ai 테이블에 VLM 전용 컬럼 추가 설계 필요

## 향후 확장성

- 뉴스 기사 대표 이미지로 확장 (meta_naver_news 이미지 URL 수집)
- 썸네일 A/B 변경 탐지: VLM 설명이 달라지면 썸네일 교체 감지
- 제품 인식 결과를 Naver 쇼핑 카테고리에 자동 매핑

---
---

# P11. 썸네일-제목 의미 정합성을 활용한 한국어 YouTube 클릭베이트 탐지

## 연구 필요성 (Research Gap)

한국어 YouTube에서 클릭베이트—썸네일과 제목이 실제 내용과 유리된 영상—는 사용자
신뢰를 저해하는 주요 문제다. 기존 탐지 연구는 제목 텍스트의 감탄사·과장 표현 분석에
집중하며, **썸네일과 제목 사이의 시각-언어 의미 정합성(semantic alignment)을
탐지 신호로 활용한 한국어 연구**는 없다. CLIP 모델의 이미지-텍스트 정렬 능력을
활용하면 텍스트 분석이 포착하지 못하는 "시각적 낚시"(정상 제목·이상 썸네일)도
탐지할 수 있다는 가설이 있다.

## 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Chakraborty et al. (2016). "Stop Clickbait: Detecting and Preventing Clickbaits in Online News Media." *IEEE/ACM ASONAM*. | 뉴스 제목의 텍스트 패턴(의문형·명사형 사용)으로 클릭베이트 탐지. 영어 뉴스 대상. | 시각 정보(썸네일) 미활용; 한국어 YouTube 클릭베이트 미분석 |
| Anand et al. (2017). "We Used Neural Networks to Detect Clickbaits: You Won't Believe What Happened Next!" arXiv:1710.08347. | LSTM 기반 제목 텍스트 분류기로 클릭베이트 탐지. Clickbait Challenge 데이터셋(영어) 활용. | 시각 채널 없음; 한국어 환경 미적용 |
| Chen & Chen (2022). "Detecting Clickbait in Online Social Media: You Won't Believe How We Did It." arXiv:2209.14898. | 다중 모달(텍스트+이미지 공동 임베딩)로 뉴스 클릭베이트 탐지 성능 향상 실증. | 영어 뉴스 대상; CLIP 기반 zero-shot alignment 신호 미사용 |
| Radford et al. (2021). "CLIP." *ICML*. | 이미지-텍스트 의미 유사도를 zero-shot으로 계산 가능. | 클릭베이트 탐지에 직접 적용·평가한 연구 없음 |

기존 클릭베이트 탐지 연구들은 영어 뉴스 텍스트 위주이며, CLIP 정합성 점수를 한국어 YouTube 클릭베이트의 zero-shot 탐지 신호로 활용하고 그 효과를 텍스트 단독 방법과 비교한 연구는 없다.

## 기여점 (Contribution)

- CLIP 썸네일-제목 코사인 유사도를 클릭베이트 탐지 신호로 활용하는 zero-shot 방법 제안
- 한국어 YouTube 300건 클릭베이트 레이블 데이터셋 구축 (Cohen's Kappa 검증)
- 텍스트 단독 vs. 시각 정합성 단독 vs. 멀티모달 결합 탐지 성능 비교
- "시각적 낚시형"(정상 텍스트 + 이상 썸네일) 클릭베이트 유형 분류 체계 제안

## 제목

> *Multimodal Clickbait Detection via Thumbnail-Title Semantic Alignment Score in Korean YouTube*

## 초록

한국어 YouTube 클릭베이트 탐지 연구는 제목 텍스트 분석에 편중되어 있으며, 썸네일의 시각
정보를 탐지에 활용한 연구는 없다. 본 연구는 CLIP 모델로 계산한 썸네일-제목 의미 정합성
점수(alignment score)를 클릭베이트 탐지 신호로 활용하는 방법을 제안한다. 한국어 YouTube
영상 300건에 대한 2인 독립 클릭베이트 레이블 데이터셋을 구축하고, 텍스트 단독·시각 단독·
멀티모달 결합 탐지기의 Precision·Recall·F1을 비교한다.

## 연구 내용

### 1단계: CLIP 정합성 점수 산출

```
alignment_score(v) = cosine_similarity(
    CLIP_image(thumbnail_v),
    CLIP_text(title_v)
)
범위: [-1, 1] — 값이 낮을수록 시각-텍스트 불일치
```

### 2단계: 클릭베이트 레이블 체계

```
유형 A (시각적 낚시): 썸네일 내용이 영상 내용과 완전 무관 (예: 유명인 얼굴 삽입)
유형 B (텍스트 낚시): 과장 표현·물음표 제목으로 호기심 유발
유형 C (혼합):        A + B 동시
비클릭베이트:         정상
```

### 3단계: 탐지 모델 비교

```
M1 — 텍스트 단독:       제목 내 감탄사·과장 표현·물음표 비율 → Logistic Regression
M2 — 시각 단독:         alignment_score < τ → Threshold Classifier
M3 — 멀티모달 결합:     [alignment_score, text_features] → Logistic Regression
M4 — 유형 인식 결합:    유형 A/B/C 레이블로 multi-class 분류
```

---

## 연구 방법

### 핵심 연구 질문

> "CLIP 썸네일-제목 정합성 점수가 텍스트 단독 특징 대비 한국어 클릭베이트 탐지에서
> 추가적인 판별력을 제공하는가? 특히 '시각적 낚시형'은 텍스트 방법으로 탐지 불가능한가?"

### 실험 1: 데이터셋 구축

- 수집 영상 중 300건 샘플링 (클릭베이트 150건, 정상 150건 균형)
- 2인 독립 레이블 후 Cohen's Kappa 측정 → Kappa > 0.7 목표
- 불일치 케이스는 3인 합의로 결정

### 실험 2: 정합성 점수 분포 분석

클릭베이트 vs. 정상 그룹의 alignment_score 분포를 비교하고
Mann-Whitney U-test로 두 그룹 차이의 통계적 유의성을 검정한다.

### 실험 3: 탐지 성능 비교

5-fold cross-validation으로 M1–M4의 Precision·Recall·F1을 비교한다.
유형 A(시각적 낚시)는 M1이 탐지하기 어려우나 M2·M3는 가능할 것이라는 가설을 확인한다.

---

## 평가 방법

### 비교 대상

| 방법 | 설명 |
|------|------|
| Random Baseline | 무작위 50% 분류 |
| M1 — Text-only | 제목 텍스트 패턴 → Logistic Regression |
| M2 — Visual-only | alignment_score 임계값 분류 |
| M3 — Multimodal | alignment_score + 텍스트 특징 결합 |

### 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| Precision / Recall / F1 | 클릭베이트 탐지 정확도 | 오탐(Precision)과 미탐(Recall) 모두 중요 |
| Cohen's Kappa | 레이블 일치율 | 데이터셋 신뢰성의 필수 검증 지표 |
| ROC-AUC | 임계값 독립 전반 판별력 | 임계값 선택 없이 모델 자체 성능 비교 |
| MWU p-value | 클릭베이트/정상 그룹 점수 분포 차이 | alignment_score가 신호로서 유효한지 사전 검증 |
| 유형별 F1 | 유형 A/B/C 각각의 탐지 정확도 | 어떤 클릭베이트 유형에 시각 신호가 효과적인지 분석 |

### 해석 기준

- Cohen's Kappa > 0.7 → 레이블 신뢰 확보
- M3 F1 > M1 F1 by ≥ 5%p → 시각 정합성 신호의 추가 기여 입증
- ROC-AUC > 0.75 → 실용적 탐지기 수준
- 유형 A에서 M2 Recall > M1 Recall by ≥ 20%p → "시각적 낚시" 가설 검증

## 구현 난이도: ★★★☆☆

- CLIP CPU 추론 가능 (썸네일 300건 처리 약 10분)
- 300건 수동 레이블링이 주요 비용 (약 2–3인일)
- 한국어 제목 → CLIP 텍스트 인코더의 처리 품질 사전 확인 필요 (영어 중심 학습)

## 향후 확장성

- 뉴스 기사 대표 이미지-헤드라인 정합성으로 확장 (뉴스 낚시 탐지)
- 실시간 파이프라인 통합: data_registry에 clickbait_risk_score 컬럼 추가
- 한국어 특화 CLIP fine-tuning으로 정합성 측정 정확도 향상

---
---

## 종합 비교

| # | 주제 요약 | 독창성 | 데이터 준비 | 구현 | 기대 임팩트 | 단기 착수 |
|---|----------|--------|------------|------|-----------|---------|
| P01 | Pseudo-Volume 시계열 복원 | ★★★★★ | 즉시 | ★★ | 높음 | ✅ |
| P02 | DCAT 메타데이터 플랫폼 | ★★★☆☆ | 즉시 | ★ | 중 | ✅ |
| P03 | LLM YouTube 메타데이터 | ★★★★☆ | 수집 | ★★★ | 높음 | |
| P04 | Persona 독립 가정 검증 | ★★★★☆ | 즉시+ | ★★ | 중 | ✅ |
| P05 | 뉴스 댓글 임팩트 측정 | ★★★☆☆ | 수집 필요 | ★★★ | 중 | |
| P06 | YouTube-쇼핑 Granger | ★★★★☆ | 즉시+ | ★★★ | 높음 | |
| P07 | 한국어 도메인 RAG | ★★★☆☆ | 수집+평가셋 | ★★★★ | 높음 | |
| P08 | 계층적 벡터 검색 | ★★★☆☆ | 즉시 | ★★★ | 중 | ✅ |
| P09 | 썸네일+텍스트 멀티모달 검색 | ★★★★☆ | 즉시 | ★★★ | 높음 | ✅ |
| P10 | VLM 썸네일 메타데이터 생성 | ★★★★☆ | 즉시+ | ★★★★ | 높음 | |
| P11 | 썸네일-제목 클릭베이트 탐지 | ★★★★★ | 레이블링 | ★★★ | 중 | |

> 구현 난이도: ★가 많을수록 어려움

---

## 연구방법-평가방법 연결 요약

각 논문의 연구방법과 평가방법이 어떻게 연결되는지 한눈에:

| # | 연구 질문 핵심 | 연구방법이 답하는 방식 | 평가가 확인하는 것 |
|---|-------------|-------------------|----------------|
| P01 | 보정이 연속성을 높이는가 | 의도적으로 배치를 다르게 구성해 수집 | 같은 (카테고리, 날짜)의 값 일관성 측정 |
| P02 | 플랫폼이 탐색을 빠르게 하는가 | 같은 과제를 플랫폼 유무로 수행 | 탐색 시간, 검색 정확도 비교 |
| P03 | LLM 메타데이터가 검색을 개선하는가 | 조건 A/B/C로 같은 쿼리 실행 | 검색 NDCG, MRR 비교 |
| P04 | 독립 가정이 카테고리별로 다르게 위반되는가 | 실측 joint 값과 persona_index 비교 | violation_ratio 분포 및 군집 검정 |
| P05 | 임팩트 패턴이 유형화되는가 | 시간별 댓글 수집 후 곡선 피팅 | 군집 타당성 + 조기 예측 MAPE |
| P06 | YouTube가 쇼핑을 선행하는가 | VAR 모델 + Granger 검정 | F-test p-value + 예측 RMSE 비교 |
| P07 | 어떤 RAG 조합이 최선인가 | 12조합 × 100개 질문 전수 실험 | RAGAS 4지표 Kruskal-Wallis 검정 |
| P08 | 계층 검색이 속도를 높이면서 정확도를 유지하는가 | K값 변화에 따른 tradeoff 측정 | MRR 차이 < 0.05 + 응답시간 50% 감소 |
| P09 | 썸네일 시각 임베딩이 텍스트 검색을 보완하는가 | α 그리드 탐색 + 카테고리별 분석 | Late Fusion MRR > Text-only + 0.05 |
| P10 | VLM 메타가 트랜스크립트 메타와 보완 관계인가 | 4조건 Ablation + 신규 정보 비율 측정 | 신규 정보 비율 > 30% + MRR 향상 > 0.03 |
| P11 | 시각 정합성 점수가 클릭베이트 판별력을 높이는가 | M1–M3 모델 비교 + 유형별 분석 | Multimodal F1 > Text-only F1 by 5%p |
