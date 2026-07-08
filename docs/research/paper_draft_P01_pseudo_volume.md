# 논문 초안: 상대 검색량 지수의 장기 연속 시계열 복원

> 기반 기획서: [research_proposals.md](./research_proposals.md) P01
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)

---

## 제목 (Title)

**영문:** *Pseudo-Volume: A Two-Stage Scale Correction Method for Reconstructing Continuous Time-Series from Relative Search Indices*

**국문:** Pseudo-Volume: 상대 검색량 지수로부터 연속 시계열을 복원하는 2단계 Scale 보정 방법

---

## Abstract

Search trend APIs such as Naver Shopping Insight and Google Trends return **relative indices
normalized to 100 within the requested query scope** rather than absolute search volumes. This
design causes two forms of discontinuity: (1) *inter-batch discontinuity*, since the API allows
at most `[DATA: 3]` categories per call and the normalization base changes across batches when
categories are split across multiple calls, and (2) *inter-collection discontinuity*, since
re-collecting the same period on a different day yields a different underlying volume
distribution and therefore a different normalization base. Prior work treats relative indices as
directly comparable within a single collection session and does not address either
discontinuity. We propose **Pseudo-Volume**, a two-stage correction method that (i) inserts a
fixed anchor category into every batch and estimates a median-based `intra_scale` correction
across batches, and (ii) uses the overlapping period between successive collections to estimate
an `inter_scale` correction across collection sessions. We evaluate the method on `[DATA: 5]`
Naver Shopping Insight categories over `[DATA: 18]` months (`[DATA: N observations]` daily
observations), comparing against naive concatenation, linear rescaling, and single-anchor
correction baselines. We measure batch consistency via coefficient of variation, discontinuity
via jump size at collection boundaries, and downstream utility via ARIMA forecast RMSE. Results
show that Pseudo-Volume reduces batch-level CV by `[DATA: Δ%]` and collection-boundary jump size
by `[DATA: Δ%]` relative to naive concatenation, and yields a statistically significant reduction
in forecast RMSE (`[DATA: paired t-test result]`), though the improvement is not uniform across
all categories, revealing a limitation of the anchor-based approach under high-volatility
regimes.

**국문 초록 (draft):** 네이버 쇼핑인사이트·Google Trends 등 검색 트렌드 API는 절대 검색량
대신 요청 범위 내 최댓값을 100으로 정규화한 **상대 지수**를 반환한다. 이 구조는 (1) API가
한 번에 최대 `[DATA: 3]`개 카테고리 비교만 허용해 여러 배치로 나눠 호출하면 배치마다
정규화 기준이 달라지는 **배치 간 불연속**, (2) 같은 기간을 다른 날 재수집하면 검색량
분포 자체가 달라져 정규화 기준이 바뀌는 **수집 구간 간 불연속**을 일으킨다. 기존 연구는
단일 수집 세션 내 비교에 머무르며 이 두 불연속을 다루지 않는다. 본 연구는 **anchor
카테고리를 모든 배치에 포함시켜 배치 간 정규화 기준 차이를 보정하는 intra_scale**과,
**수집 구간이 겹치는 기간의 anchor 값 비율로 수집 구간 간 차이를 보정하는 inter_scale**을
결합한 2단계 Pseudo-Volume 방법을 제안한다. 네이버 쇼핑인사이트 `[DATA: 5]`개 카테고리,
`[DATA: 18]`개월(`[DATA: N]`개 일별 관측치) 데이터로 검증하고, Naive 연결·선형 스케일링·
단일 anchor 보정 대비 배치 일관성(CV), 연결점 불연속(jump), ARIMA 예측 정확도(RMSE)를
비교한다. 제안 방법은 Naive 대비 배치 일관성과 연결점 불연속을 각각 `[DATA: Δ%]`,
`[DATA: Δ%]` 개선했고, ARIMA 예측 오차도 통계적으로 유의하게 낮췄다(`[DATA: paired
t-test 결과]`). 다만 모든 카테고리에서 균일하게 개선되지는 않아, anchor 기반 보정이
고변동성 구간에서 갖는 한계도 함께 논의한다.

**Keywords:** relative search index, pseudo-volume, scale correction, time-series
reconstruction, Google Trends, Naver Shopping Insight, ARIMA forecasting

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

네이버 쇼핑인사이트·Google Trends 등 검색 트렌드 API는 절대 검색량 대신 **요청 범위 내
최댓값=100으로 정규화된 상대값**을 반환한다. 이 구조는 두 가지 문제를 일으킨다.

1. **배치 간 불연속**: API가 한 번에 최대 `[DATA: 3]`개 카테고리 비교를 허용하므로 여러
   배치로 나눠 호출하면 배치마다 정규화 기준 `M`이 달라진다. 같은 카테고리라도 배치
   구성에 따라 raw_ratio가 달라지는 것이다.
2. **수집 구간 간 불연속**: 다른 날 같은 기간을 재수집하면 검색량 분포 자체가 달라져
   `M`이 바뀐다. 두 시점의 raw_ratio를 그냥 연결하면 단절이 생긴다.

두 문제 모두 근본 원인은 동일하다 — API가 정규화 기준 `M`을 노출하지 않고, `M` 자체가
배치 구성과 수집 시점에 따라 달라진다는 것이다. 기존 문헌 대부분은 단일 API 호출 범위
내 비교에 그치며, 여러 배치·여러 수집 시점에 걸친 장기 연속 시계열을 복원하는 체계적
방법론은 제시되지 않았다.

### 1.2 연구 질문

> 두 단계 Scale 보정(intra_scale × inter_scale)으로 복원한 pseudo_volume은, 배치
> 구성과 수집 시점이 달라도 동일한 (카테고리, 날짜)에 대해 일관된 값을 산출하는가?
> 그리고 이렇게 복원한 연속 시계열은 단순 연결 방식보다 실제 예측 과제에서 더 유용한가?

### 1.3 기여점 (Contributions)

1. 상대 지수 비연속 문제(배치 간·수집 구간 간)의 수학적 정형화
2. anchor 카테고리 기반 `intra_scale` / `inter_scale` 2단계 보정 방법 제안
3. 중앙값 기반 Robust 추정으로 이상치 내성을 확보한 scale 계수 산출 절차
4. 배치 구성을 의도적으로 달리한 실험과 수집 구간을 의도적으로 중복시킨 실험을 통한
   직접 검증 설계
5. Naive 연결·선형 스케일링·단일 anchor 보정 대비 배치 일관성·연결점 불연속·예측
   정확도의 정량적 비교와, pseudo_volume 신뢰도의 한계 명시

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Choi & Varian (2012). "Predicting the Present with Google Trends." *The Economic Record*, 88(S1), 2–9. | Google Trends 상대 지수를 소비·고용 등 경제 지표 예측에 활용한 선구적 연구. | 단일 수집 세션의 데이터만 사용해 배치 간 정규화 기준 차이 문제를 논의하지 않음. 다수 배치·다수 수집 구간 간 보정 방법 미제시 |
| Da, Engelberg & Gao (2011). "In Search of Attention." *Journal of Finance*, 66(5), 1461–1499. | 개인 투자자 관심도의 대리 지표로 Google SVI(Search Volume Index)를 활용. | 상대값의 크로스 섹션 비교 한계를 언급하나 계량적 보정 방법을 제시하지 않음. anchor 기반 연속 시계열 복원 없음 |
| Preis, Moat & Stanley (2013). "Quantifying Trading Behavior Using Google Trends." *Scientific Reports*, 3, 1684. | 검색 트렌드를 금융 행동 지표로 사용. | 단일 키워드 시계열 분석에 그치며, 카테고리 배치 구성 변경 시 발생하는 불연속 문제를 다루지 않음. 단일 쿼리·단일 배치 가정 |
| Lazer et al. (2014). "The Parable of Google Flu: Traps in Big Data Analysis." *Science*, 343(6176), 1203–1205. | 알고리즘 변화로 인한 Google Flu Trends 붕괴 사례를 통해 외부 요인이 상대 지수 신뢰성을 해친다는 점을 지적. | 체계적 재보정 방법 없이 데이터 자체의 한계를 논증하는 데 그침. 보정 방법론 미제시, 경고성 사례 연구 수준 |

### 2.1 선행 연구 대비 위치 (Positioning)

- 기존 문헌들은 상대 지수를 **있는 그대로** 활용하거나 단일 세션 내 비교에 머무른다.
  수집 배치 구성과 수집 시점이 달라져도 장기 연속 시계열을 복원하는 방법론은 제시된
  바 없다.
- Choi & Varian(2012)과 Da et al.(2011)은 상대 지수를 예측·행동 분석의 입력으로
  삼으면서도, 그 지수 자체가 배치 구성에 따라 달라질 수 있다는 측정 오차 문제를
  방법론적으로 다루지 않는다. 본 연구는 이 측정 오차를 정면으로 다룬다.
- Lazer et al.(2014)은 상대 지수 기반 지표의 신뢰성 붕괴 사례를 경고하지만, 그
  경고에 대응하는 구체적 재보정 절차는 제시하지 않는다. 본 연구의 anchor 기반
  2단계 보정은 이 공백에 대한 구체적 대응책으로 볼 수 있다.
- 상대 지수 API(네이버 쇼핑인사이트, Google Trends 등)는 구조가 유사하므로, 본
  연구의 방법론은 특정 플랫폼에 종속되지 않는 일반적 접근으로 설계된다.

> **⚠️ 검증 필요:** 위 novelty 주장은 2026-07-08 시점 검토 기준이며, 학회 제출 전
> 최신 arXiv/DBLP/경제학·데이터마이닝 학회 프로시딩 재검색으로 최근 유사 연구가
> 없는지 재확인할 것. 특히 "search index normalization correction", "relative
> search volume reconstruction", "Google Trends anchor calibration" 키워드로
> 재검색 권장.

---

## 3. 제안 방법 (Methodology)

### 3.1 문제 정형화

```
R(c, t, B) = 배치 B에서 카테고리 c, 시점 t의 raw_ratio
M(B) = 해당 배치의 검색량 최대값 (API가 숨기는 값)
R(c, t, B) = actual_volume(c, t) / M(B) × 100
```

배치 `B1`과 `B2`가 같은 기간을 다루더라도 `M(B1) ≠ M(B2)`이면 `R`의 직접 비교는
불가하다. 두 배치를 그대로 이어붙이면(Naive 연결) 실제로는 존재하지 않는 값의
도약(jump)이 시계열에 나타난다.

### 3.2 intra_scale (배치 간 보정)

anchor 카테고리 `a`를 모든 배치에 포함시킨다. anchor는 (1) 항상 상대적으로 큰
검색량을 유지해 API 응답에서 0에 가까운 값으로 잘리지 않고, (2) 계절성이 낮아
장기간 안정적인 기준점 역할을 할 수 있는 카테고리를 선정한다. 기준 배치(첫 번째
유효 배치)의 anchor 값과 각 배치의 anchor 값 비율 중앙값으로 보정한다.

```
intra_scale(B) = median_t { R(a, t, B_ref) / R(a, t, B) }
```

중앙값을 사용하는 이유는 특정 날짜의 일시적 검색량 급등(이벤트성 트래픽 등)이
개별 비율을 왜곡하더라도 median이 이상치 영향을 덜 받기 때문이다.

### 3.3 inter_scale (수집 구간 간 보정)

이전 수집과 신규 수집이 겹치는 기간을 이용해 anchor 값 비율 중앙값으로 보정한다.

```
inter_scale = median_t { R_db(a, t) / R_new(a, t) }   (겹치는 t에 대해)
```

수집 구간을 설계할 때부터 일정 기간(예: 1개월)을 의도적으로 중복시켜 이 보정이
항상 가능하도록 한다.

### 3.4 pseudo_volume 산출

```
pseudo_volume(c, t) = R(c, t) × intra_scale(B) × inter_scale
```

intra_scale은 "같은 시점에 다른 배치로 나뉘어 수집된 값"을 하나의 기준으로
정렬하고, inter_scale은 "다른 시점에 수집된 배치들"을 하나의 기준으로 정렬한다.
두 보정을 곱으로 결합하면 배치 구성과 수집 시점이 모두 달라도 동일한
(카테고리, 날짜)가 동일한 pseudo_volume에 수렴하는 것이 이론적 기대다 — 이 기대를
검증하는 것이 4장의 실험이다.

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| 데이터 소스 | 네이버 쇼핑인사이트 API |
| 카테고리 수 | `[DATA: 5]`개 (anchor 1개 + 대상 카테고리 4개) — 제안서 목표 |
| 카테고리 목록 | `[DATA: anchor = ?, 대상 4개 = ?]` (예: anchor 후보 — 검색량이 크고 계절성이 낮은 카테고리) |
| 수집 기간 | 2025-01 ~ 2026-06 (`[DATA: 18]`개월, 학습 15개월 + 예측 3개월) |
| 배치당 최대 카테고리 수 | `[DATA: 3]` (API 제약) |
| 실험 1 배치 구성 (intra_scale 검증) | `[DATA: 배치 A/B 구성 상세]` |
| 실험 2 수집 구간 겹침 기간 (inter_scale 검증) | `[DATA: 겹침 기간, 두 수집 날짜]` |
| 총 일별 관측치 수 | `[DATA: N]` |

### 4.2 실험 절차

**실험 1: 배치 구성 변경 실험 (intra_scale 검증)**

동일한 카테고리 집합을 **의도적으로 다른 배치 구성**으로 수집한다.

```
실험 A 배치 구성: 배치1 = anchor + [대상1, 대상2]  /  배치2 = anchor + [대상3, 대상4]
실험 B 배치 구성: 배치1 = anchor + [대상3, 대상4]  /  배치2 = anchor + [대상1, 대상2]
```

같은 날짜의 pseudo_volume이 배치 구성과 무관하게 일치해야 한다. `[DATA: 실제
배치 구성 상세]`

**실험 2: 수집 구간 겹침 실험 (inter_scale 검증)**

같은 기간을 **두 번 다른 날에 수집**하고 두 번의 pseudo_volume을 비교한다. 차이가
클수록 inter_scale 보정의 필요성이 크다는 뜻이다.

**실험 3: 예측 정확도 실험**

18개월 치 pseudo_volume vs. raw_ratio vs. normalized_ratio(선형 스케일링)로 각각
ARIMA 모델을 학습하고 마지막 구간을 예측해 비교한다.

```
학습 기간: 2025-01 ~ 2026-03 (15개월)
예측 기간: 2026-04 ~ 2026-06 (3개월)
```

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상 (Baselines)

| 방법 | 설명 |
|------|------|
| Naive 연결 | raw_ratio를 그냥 이어붙임 (보정 없음) |
| 선형 스케일링 | 각 수집 구간의 평균값으로 나눠 정규화 |
| 단일 anchor | intra_scale 없이 inter_scale만 적용 |
| **제안 방법** | intra_scale × inter_scale 2단계 |

### 5.2 측정 지표와 측정 대상의 연결

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| 배치 일관성 (CV) | 같은 (카테고리, 날짜)의 다른 배치 pseudo_volume 변동계수 | 배치 구성이 달라도 값이 같아야 한다는 핵심 요건을 직접 측정 |
| 구간 연결점 jump 크기 | 수집 구간 경계에서의 값 단절 절댓값 | 시계열이 얼마나 매끄럽게 이어지는지 측정 |
| ARIMA RMSE | 복원 시계열로 예측한 미래값의 오차 | 연속 시계열의 실용적 가치(예측에 써먹을 수 있는지) 측정 |
| Bootstrap 신뢰구간 폭 | scale 계수 추정 불확실성 | 방법의 안정성과 한계를 동시에 표현 |

### 5.3 주요 개념 설명

**CV (Coefficient of Variation, 변동계수)**
표준편차를 평균으로 나눈 값. 단위가 없어 서로 다른 스케일의 데이터에서도 변동성을
비교할 수 있다. CV = 0.1이면 평균의 10% 수준으로 값이 흔들린다는 뜻. 값이 낮을수록
일관성이 높다. 배치 일관성 측정에 CV를 쓰는 이유: 같은 날짜·카테고리를 다른
배치에서 수집해도 pseudo_volume이 비슷해야 하므로, 배치 간 분산을 평균으로
정규화한 CV가 가장 적합한 지표다.

**ARIMA (Auto-Regressive Integrated Moving Average)**
시계열 예측의 표준 모델. 과거 자신의 값(AR)과 과거 예측 오차(MA), 그리고 차분(I)을
조합해 미래를 예측한다. 이 연구에서는 복원된 시계열이 실제로 "예측에 쓸 수 있는
연속 데이터"인지를 검증하는 도구로 사용한다.

**RMSE (Root Mean Squared Error)**
예측값과 실제값의 차이를 제곱해 평균낸 뒤 제곱근을 취한 값. 값이 작을수록 예측이
정확. 큰 오차에 더 민감하게 반응한다(제곱 때문에 큰 오차가 강조됨).

**Bootstrap 신뢰구간**
정규 분포를 가정하기 어려울 때, 데이터를 수백~수천 번 재샘플링해 scale 계수의
분포를 직접 추정하는 방법. "inter_scale = 1.05, 95% 신뢰구간 [0.98, 1.12]"처럼
추정의 불확실성을 범위로 표현. 신뢰구간이 넓을수록 scale 추정이 불안정하다는 뜻.

**paired t-test**
동일한 샘플(같은 카테고리·날짜)에 두 방법을 각각 적용한 결과를 비교하는 검정.
개체 간 자연적 차이를 제거하고 방법 간 차이만 검정하므로, 단순 두 집단 비교
(independent t-test)보다 검정력이 높다. p < 0.05이면 두 방법의 성능 차이가
우연이 아닌 것으로 판단.

### 5.4 해석 기준 (성공 조건)

- 배치 일관성 CV: 제안 방법 < Naive의 50% → 배치 간 일관성 확보 입증
- 연결점 jump 크기: 제안 방법 < Naive의 50%
- ARIMA RMSE: 제안 방법이 Naive 대비 통계적으로 유의하게 낮음 (paired t-test p < 0.05)

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 배치 일관성 검증 (실험 1: intra_scale)

| 방법 | 배치 일관성 CV (평균) | Naive 대비 감소율 |
|------|----------------------|-------------------|
| Naive 연결 | `[DATA]` | — |
| 선형 스케일링 | `[DATA]` | `[DATA]` |
| 단일 anchor | `[DATA]` | `[DATA]` |
| **제안 방법** | `[DATA]` | `[DATA]` |

카테고리별 세부 결과: `[DATA: 카테고리별 CV 표 또는 그래프 삽입]`

### 6.2 수집 구간 연결 검증 (실험 2: inter_scale)

| 방법 | 연결점 jump 크기 (평균 절댓값) | Naive 대비 감소율 |
|------|-------------------------------|-------------------|
| Naive 연결 | `[DATA]` | — |
| 선형 스케일링 | `[DATA]` | `[DATA]` |
| 단일 anchor | `[DATA]` | `[DATA]` |
| **제안 방법** | `[DATA]` | `[DATA]` |

### 6.3 예측 정확도 비교 (실험 3: ARIMA)

| 방법 | ARIMA RMSE (평균) | Naive 대비 |
|------|--------------------|-----------|
| raw_ratio (Naive) | `[DATA]` | — |
| normalized_ratio (선형 스케일링) | `[DATA]` | `[DATA]` |
| pseudo_volume (제안 방법) | `[DATA]` | `[DATA]` |

paired t-test (pseudo_volume vs. raw_ratio): `[DATA: t-statistic, p-value]`

카테고리별 세부 결과: `[DATA: 카테고리별 RMSE 표 삽입 — 균일하게 개선되는지 확인]`

### 6.4 Bootstrap 신뢰구간 및 scale 계수 안정성

| 계수 | 추정값 | 95% Bootstrap CI | CI 폭 |
|------|--------|-------------------|-------|
| intra_scale (배치 A→B) | `[DATA]` | `[DATA]` | `[DATA]` |
| inter_scale | `[DATA]` | `[DATA]` | `[DATA]` |

`[DATA: 카테고리별/배치별 CI 폭 비교 — 어떤 조건에서 추정이 불안정한지 확인]`

### 6.5 anchor 카테고리 선택 민감도

`[DATA: anchor 후보를 바꿔가며 재계산했을 때 pseudo_volume의 변화 폭 — anchor
선택이 결과에 미치는 영향 정성/정량 분석]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 배치 일관성(CV)과 연결점 jump 개선이 해석 기준을 충족했는지, 그 폭이 어느
  정도인지
- ARIMA RMSE 개선의 통계적 유의성과 실질적 효과크기(effect size)를 구분해서 논의 —
  유의하지만 효과가 작은 카테고리가 있다면 그 원인
- 카테고리별로 개선 폭이 균일하지 않다면(예: 고변동성 카테고리에서 선형
  스케일링과 유사하거나 더 나쁜 경우) anchor 기반 median 보정이 변동성이 큰
  구간에서 갖는 한계를 논의
- Bootstrap CI가 넓게 나온 계수가 있다면 그 원인(수집 구간 겹침 기간이 짧음,
  anchor 자체의 변동성 등)과 실무적 함의
- anchor 카테고리 선택이 결과에 미치는 민감도와, 이것이 방법의 일반화 가능성에
  주는 시사점

## 8. 한계 (Limitations)

- anchor 카테고리 자체의 검색량이 안정적이라는 가정에 의존한다 — anchor의 트렌드가
  변하면 (예: 계절적 이벤트, 알고리즘 변경) scale 추정 자체가 왜곡될 수 있다
- 중앙값 기반 보정은 이상치에 강건하지만, 표본 수(겹치는 날짜 수)가 적으면 median
  추정 자체의 불확실성이 커진다 — 이는 6.4의 Bootstrap CI로 정량화하되, 완전히
  제거되지는 않는다
- `[DATA: 5]`개 카테고리, `[DATA: 18]`개월이라는 범위 내 검증으로, 카테고리 수가
  훨씬 많거나 계절성이 극단적인 카테고리(예: 명절 특수 품목)에 대한 일반화는
  확인되지 않았다
- Naver Shopping Insight 특화 실험이며, Google Trends 등 다른 상대 지수 API에 대한
  실증 검증은 수행하지 않았다(구조적 유사성에 근거한 일반화 주장에 그침)
- pseudo_volume은 여전히 상대적 추정치이며, 절대 검색량 자체를 복원하지는 못한다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- Google Trends 동일 적용 (API 구조 유사)
- Online 추정: 실시간 streaming 환경에서의 sliding window scale 추정
- anchor 다중화: 단일 anchor 대신 여러 anchor의 앙상블로 추정 안정성 개선

---

## 참고문헌 (References)

1. Choi, H., & Varian, H. (2012). Predicting the Present with Google Trends. *The Economic Record*, 88(S1), 2–9.
2. Da, Z., Engelberg, J., & Gao, P. (2011). In Search of Attention. *Journal of Finance*, 66(5), 1461–1499.
3. Preis, T., Moat, H. S., & Stanley, H. E. (2013). Quantifying Trading Behavior Using Google Trends. *Scientific Reports*, 3, 1684.
4. Lazer, D., Kennedy, R., King, G., & Vespignani, A. (2014). The Parable of Google Flu: Traps in Big Data Analysis. *Science*, 343(6176), 1203–1205.

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 카테고리 목록 (anchor + 대상 4개) 확정
- [ ] 4.1 총 일별 관측치 수(N) 확정
- [ ] 4.2 실험 1 배치 구성(A/B) 상세 확정
- [ ] 4.2 실험 2 수집 구간 겹침 기간·두 수집 날짜 확정
- [ ] 6.1 배치 일관성 CV 표 수치 삽입
- [ ] 6.2 연결점 jump 크기 표 수치 삽입
- [ ] 6.3 ARIMA RMSE 표 및 paired t-test 통계량/p-value 삽입
- [ ] 6.3 카테고리별 RMSE 세부 결과 삽입
- [ ] 6.4 Bootstrap 신뢰구간 표 삽입
- [ ] 6.5 anchor 선택 민감도 분석 삽입
- [ ] 7장 논의 작성 (특히 균일하지 않은 개선 폭에 대한 해석)
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 제출 전 novelty 재검색 (2.1절 경고 참고)
