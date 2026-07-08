# 논문 초안: 썸네일-제목 의미 정합성을 활용한 한국어 YouTube 클릭베이트 탐지

> 기반 기획서: [research_proposals.md](./research_proposals.md) P07
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)

---

## 제목 (Title)

**영문:** *Multimodal Clickbait Detection via Thumbnail-Title Semantic Alignment Score in Korean YouTube*

**국문:** 썸네일-제목 의미 정합성 점수를 이용한 한국어 YouTube 멀티모달 클릭베이트 탐지

---

## Abstract

Clickbait detection research on Korean YouTube has focused almost exclusively on textual
patterns in titles (exclamatory phrases, exaggeration, question marks), leaving the visual
information in thumbnails unexploited as a detection signal. We propose using a CLIP-derived
thumbnail-title semantic **alignment score** — the cosine similarity between a video's
thumbnail image embedding and its title text embedding in CLIP's joint space — as a zero-shot
clickbait detection signal. We construct a Korean YouTube clickbait dataset of `[DATA: 300]`
videos (`[DATA: 150]` clickbait, `[DATA: 150]` non-clickbait), independently labeled by two
annotators (Cohen's κ = `[DATA]`), and further categorize clickbait instances into three
types: **visual bait** (misleading thumbnail, plain title), **textual bait** (exaggerated
title, plain thumbnail), and **mixed bait** (both). We compare a text-only classifier (M1), a
threshold classifier on the alignment score alone (M2), a multimodal classifier combining both
(M3), and a type-aware multi-class classifier (M4) across `[DATA: 5]`-fold cross-validation. We
show that the multimodal model improves F1 over the text-only baseline by `[DATA: Δ]`
percentage points (`[DATA: statistical test / p-value]`), and that the alignment score is
particularly effective at recovering "visual bait" instances that text-only methods
systematically miss (`[DATA]` Recall gain, `[DATA: pp]`). We situate our contribution against
two closely related prior systems — ThumbnailTruth (arXiv:2509.04714, 2025) and the
Multi-Modal-YT-Clickbait-Classifier project — which use a near-identical CLIP thumbnail-title
embedding stack, and discuss the resulting novelty overlap explicitly.

**국문 초록 (draft):** 한국어 YouTube 클릭베이트 탐지 연구는 제목 텍스트의 과장 표현·물음표
같은 패턴 분석에 편중되어 있으며, 썸네일의 시각 정보를 탐지 신호로 활용한 연구는 없다. 본
연구는 CLIP 결합 공간에서 썸네일 이미지 임베딩과 제목 텍스트 임베딩의 코사인 유사도로
계산되는 **정합성 점수(alignment score)**를 zero-shot 클릭베이트 탐지 신호로 제안한다.
한국어 YouTube 영상 `[DATA: 300]`건(클릭베이트 `[DATA: 150]`건, 정상 `[DATA: 150]`건)에
대해 2인 독립 레이블링을 수행해 데이터셋을 구축하고(Cohen's κ = `[DATA]`), 클릭베이트를
**시각적 낚시형**(정상 제목 + 이상 썸네일), **텍스트 낚시형**(과장 제목 + 정상 썸네일),
**혼합형**(둘 다)으로 세분화한다. 텍스트 단독(M1), 정합성 점수 단독(M2), 멀티모달 결합
(M3), 유형 인식 결합(M4) 네 모델을 `[DATA: 5]`-fold 교차검증으로 비교한 결과, 멀티모달
결합이 텍스트 단독 대비 F1을 `[DATA: Δ]`%p 향상시켰으며(`[DATA: 통계검정/p-value]`),
특히 텍스트 방법이 놓치는 "시각적 낚시형"에서 정합성 점수가 큰 폭의 Recall 개선을
가져옴을 확인했다(`[DATA]`%p). 본 연구는 거의 동일한 CLIP 썸네일-제목 임베딩 스택을
사용하는 두 개의 밀접한 선행 시스템 — ThumbnailTruth(arXiv:2509.04714, 2025)와
Multi-Modal-YT-Clickbait-Classifier 프로젝트 — 와의 관계를 명시적으로 논의하고, 겹치는
부분과 차별점을 정직하게 밝힌다.

**Keywords:** clickbait detection, CLIP, semantic alignment, multimodal classification,
thumbnail-title consistency, Korean YouTube, zero-shot detection

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

한국어 YouTube에서 클릭베이트 — 썸네일과 제목이 실제 내용과 유리된 영상 — 는 사용자
신뢰를 저해하는 주요 문제다. 기존 탐지 연구는 제목 텍스트의 감탄사·과장 표현·물음표
사용 같은 텍스트 패턴 분석에 집중해 왔다(Chakraborty et al., 2016; Anand et al., 2017).
그러나 클릭베이트의 상당수는 텍스트만으로는 판단할 수 없다 — 제목은 평이한데 썸네일이
영상 내용과 무관한 이미지(예: 유명인 얼굴 삽입, 자극적인 합성 이미지)를 쓰는 "시각적
낚시"는 텍스트 분석기가 원천적으로 탐지할 수 없는 유형이다.

CLIP(Radford et al., 2021)은 이미지와 텍스트를 같은 임베딩 공간에 정렬해 zero-shot으로
의미적 유사도를 계산할 수 있다. 썸네일과 제목 사이의 CLIP 코사인 유사도가 낮다는 것은
두 채널이 서로 다른 내용을 전달한다는 뜻이며, 이는 곧 시각-텍스트 불일치라는 클릭베이트의
구조적 특징과 직접 연결된다. 그러나 이 정합성 점수를 한국어 YouTube 클릭베이트 탐지
신호로 활용하고, 텍스트 단독 방법과 정량적으로 비교한 연구는 확인되지 않는다.

### 1.2 연구 질문

> CLIP 썸네일-제목 정합성 점수가 텍스트 단독 특징 대비 한국어 클릭베이트 탐지에서
> 추가적인 판별력을 제공하는가? 특히 텍스트 방법으로는 원천적으로 탐지할 수 없는
> "시각적 낚시형"을 정합성 점수가 포착할 수 있는가?

### 1.3 기여점 (Contributions)

1. CLIP 썸네일-제목 코사인 유사도를 클릭베이트 탐지 신호로 활용하는 zero-shot 방법 제안
   (레이블 없이 임계값만으로 동작하는 M2)
2. 한국어 YouTube 클릭베이트 레이블 데이터셋 `[DATA: 300]`건 구축, 2인 독립 레이블링과
   Cohen's Kappa 검증을 통한 신뢰도 확보
3. 텍스트 단독(M1) vs. 시각 정합성 단독(M2) vs. 멀티모달 결합(M3) vs. 유형 인식 결합(M4)
   4방향 탐지 성능 비교
4. "시각적 낚시형(visual bait)" / "텍스트 낚시형(textual bait)" / "혼합형(mixed)" 클릭베이트
   유형 분류 체계 제안과 유형별 탐지 성능 분석
5. 거의 동일한 임베딩 스택을 쓰는 선행 연구(ThumbnailTruth, Multi-Modal-YT-Clickbait-Classifier)
   대비 본 연구의 위치를 정직하게 명시 — 방법론적 novelty가 아닌 **경량 zero-shot 신호로서의
   실용성**과 **유형별 진단 분석**에 기여의 중심을 둠

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Chakraborty et al. (2016). "Stop Clickbait: Detecting and Preventing Clickbaits in Online News Media." *IEEE/ACM ASONAM*. | 뉴스 제목의 텍스트 패턴(의문형·명사형 사용)으로 클릭베이트 탐지. 영어 뉴스 대상. | 시각 정보(썸네일) 미활용; 한국어 YouTube 클릭베이트 미분석 |
| Anand et al. (2017). "We Used Neural Networks to Detect Clickbaits: You Won't Believe What Happened Next!" arXiv:1710.08347. | LSTM 기반 제목 텍스트 분류기로 클릭베이트 탐지. Clickbait Challenge 데이터셋(영어) 활용. | 시각 채널 없음; 한국어 환경 미적용 |
| Chen & Chen (2022). "Detecting Clickbait in Online Social Media: You Won't Believe How We Did It." arXiv:2209.14898. | 다중 모달(텍스트+이미지 공동 임베딩)로 뉴스 클릭베이트 탐지 성능 향상 실증. | 영어 뉴스 대상; CLIP 기반 zero-shot alignment 신호를 직접 특징으로 사용·평가하지 않음 |
| Radford et al. (2021). "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*. | 이미지-텍스트 대조 학습으로 zero-shot 이미지-텍스트 정합성을 계산할 수 있는 기반 모델 확립. | 클릭베이트 탐지에 직접 적용·평가한 연구 없음 |
| **Multi-Modal-YT-Clickbait-Classifier (AlbertBS2 project)** `[TODO: 정식 서지정보/출처 확인]` | CLIP 썸네일 임베딩 + 텍스트 특징을 결합한 late fusion 분류기로 YouTube 클릭베이트 이진 분류. **임베딩 스택이 본 연구의 M3와 사실상 동일.** | 한국어 데이터 미검증; 유형(시각/텍스트/혼합) 세분화 분석 없음; 레이블 신뢰도(Kappa) 보고 여부 미확인 |
| **ThumbnailTruth** (2025). "A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails Across Diverse Cultural Settings." arXiv:2509.04714. | Multi-Modal LLM(VLM) 기반으로 썸네일의 오도성(misleading thumbnail)을 여러 문화권 데이터에서 탐지. | 대규모 VLM 추론이 필요한 무거운 접근(본 연구의 경량 CLIP cosine 임계값 M2와 대비); 한국어가 "diverse cultural settings"에 포함되는지 확인 필요; 클릭베이트 전체가 아닌 "오도성 썸네일"에 초점 |

### 2.1 선행 연구 대비 위치 (Positioning)

> **⚠️ novelty 위협 경고 — 반드시 학회 제출 전 재검토:** ThumbnailTruth와
> Multi-Modal-YT-Clickbait-Classifier는 본 연구와 **과제 자체(클릭베이트/오도성 탐지)가
> 동일**하고 **임베딩 스택(CLIP 썸네일 임베딩 + 제목·텍스트 임베딩의 결합)도 사실상
> 동일**하다. P05(멀티모달 검색)의 경우 과제가 랭킹으로 달라 차별화가 비교적 뚜렷했지만,
> P07은 과제 수준에서 두 선행 연구와 정면으로 겹친다. 이는 이 기획서 전체에서 novelty가
> 가장 취약한 지점이며, 아래 논의는 잠정적 차별화 논거일 뿐 검증된 것이 아니다.

정직하게 정리하면 다음과 같다.

- **겹치는 부분(중요)**: 세 연구 모두 "CLIP 이미지 인코더로 썸네일을, 텍스트 인코더로
  제목을 임베딩하고 두 벡터의 정합성/유사도를 클릭베이트 신호로 사용한다"는 핵심 아이디어를
  공유한다. 본 연구의 M3(멀티모달 결합)는 개념적으로
  Multi-Modal-YT-Clickbait-Classifier와 사실상 동일한 설계다. 이 중첩은 회피할 수 없으며,
  **본 연구가 방법론적으로 독창적이라고 주장할 수 없다**는 점을 먼저 인정한다.
- **잠재적 차별점 1 — 경량 zero-shot vs. VLM**: ThumbnailTruth는 Multi-Modal LLM 기반으로
  추론 비용이 크고 파인튜닝/프롬프트 설계가 필요하다. 본 연구의 M2는 CLIP 임베딩만으로
  계산되는 단순 코사인 유사도 임계값이며 학습이 전혀 필요 없는 zero-shot 신호다. "더
  가벼운 신호로 어느 정도까지 따라잡을 수 있는가"를 정량 비교하는 것이 본 연구의 실질적
  기여가 될 수 있다 — 단, 이는 두 방법을 **동일 데이터셋에서 직접 비교**해야 성립하는
  주장이며, 본 기획에서는 이를 수행하지 않는다(§8 한계 참고).
- **잠재적 차별점 2 — 유형별 세분화 진단**: 시각적 낚시형/텍스트 낚시형/혼합형으로 유형을
  나누고 각 유형에서 M1~M4의 성능을 개별 비교하는 진단적 분석은 확인된 선행 연구에
  보고되어 있지 않다(단, 비공개이거나 우리가 확인하지 못한 것일 수 있음 — 검증 필요).
- **잠재적 차별점 3 — 한국어 도메인**: ThumbnailTruth가 "다양한 문화권"을 표방하지만
  한국어가 실제로 포함되는지, 포함된다면 어떤 성능을 보였는지 확인되지 않았다.
  Multi-Modal-YT-Clickbait-Classifier도 언어권이 명시되어 있지 않다.
- **레이블 신뢰도 검증**: 본 연구는 Cohen's Kappa로 300건 레이블의 신뢰도를 명시적으로
  보고한다. 두 선행 연구가 동일한 수준의 레이블 신뢰도 검증을 수행했는지 확인되지 않았다.

> **결론적으로**, 본 연구를 "새로운 탐지 방법의 제안"이 아니라 "기존에 검증된 신호
> (CLIP 정합성)를 한국어 환경에서 경량화·유형별로 재검증하는 실증 연구"로 프레이밍하는 것이
> 정직한 포지셔닝이다. 이 프레이밍이 학회 제출 기준에 충분한 novelty인지는 별도로 판단이
> 필요하다.

---

## 3. 제안 방법 (Methodology)

### 3.1 CLIP 정합성 점수 산출

```
alignment_score(v) = cosine_similarity(
    CLIP_image(thumbnail_v),
    CLIP_text(title_v)
)
범위: [-1, 1] — 값이 낮을수록 시각-텍스트 불일치
```

### 3.2 클릭베이트 레이블 체계

```
유형 A (시각적 낚시): 썸네일 내용이 영상 내용과 완전 무관 (예: 유명인 얼굴 삽입)
유형 B (텍스트 낚시): 과장 표현·물음표 제목으로 호기심 유발
유형 C (혼합):        A + B 동시
비클릭베이트:         정상
```

### 3.3 탐지 모델 비교

```
M1 — 텍스트 단독:       제목 내 감탄사·과장 표현·물음표 비율 → Logistic Regression
M2 — 시각 단독:         alignment_score < τ → Threshold Classifier (zero-shot, 학습 불필요)
M3 — 멀티모달 결합:     [alignment_score, text_features] → Logistic Regression
M4 — 유형 인식 결합:    유형 A/B/C 레이블로 multi-class 분류
```

> M2는 레이블 데이터 없이 alignment_score 임계값만으로 동작하는 순수 zero-shot 방법이다.
> τ는 validation 분리 없이 훈련 fold 내에서 F1을 최대화하는 값으로 탐색한다(§4.2).

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| 전체 영상 수 | `[DATA: 300]` |
| 클릭베이트 | `[DATA: 150]` |
| 정상 | `[DATA: 150]` |
| 유형 A (시각적 낚시) | `[DATA]`건 |
| 유형 B (텍스트 낚시) | `[DATA]`건 |
| 유형 C (혼합) | `[DATA]`건 |
| 레이블링 인원 | 2인 독립 + 불일치 시 3인 합의 |
| Cohen's Kappa | `[DATA]` (목표: > 0.7) |
| 데이터 소스 | `data_registry` 수집분에서 표본 추출 |

### 4.2 실험 절차

**실험 1 — 데이터셋 구축**
- 수집 영상 중 300건 샘플링 (클릭베이트 150건, 정상 150건 균형)
- 2인 독립 레이블 후 Cohen's Kappa 측정 → Kappa > 0.7 목표
- 불일치 케이스는 3인 합의로 결정
- 클릭베이트 150건에 대해 유형 A/B/C 세부 레이블 부여

**실험 2 — 정합성 점수 분포 분석**
- 클릭베이트 vs. 정상 그룹의 alignment_score 분포를 비교
- Mann-Whitney U-test로 두 그룹 차이의 통계적 유의성을 검정
- alignment_score가 신호로서 유효한지 사전 검증하는 단계

**실험 3 — 탐지 성능 비교**
- `[DATA: 5]`-fold cross-validation으로 M1–M4의 Precision·Recall·F1·ROC-AUC 비교
- 유형 A(시각적 낚시)는 M1이 탐지하기 어려우나 M2·M3는 가능할 것이라는 가설을 유형별 F1/Recall로 확인
- 유형 B(텍스트 낚시)에서 시각 신호(alignment_score)가 오히려 잡음으로 작용할 가능성도 배제하지 않고 함께 관찰

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상

| 방법 | 설명 |
|------|------|
| Random Baseline | 무작위 50% 분류 |
| M1 — Text-only | 제목 텍스트 패턴 → Logistic Regression |
| M2 — Visual-only | alignment_score 임계값 분류 (zero-shot) |
| M3 — Multimodal | alignment_score + 텍스트 특징 결합 |
| M4 — Type-aware | 유형 A/B/C 다중 클래스 분류 |

### 5.2 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| Precision / Recall / F1 | 클릭베이트 탐지 정확도 | 오탐(Precision)과 미탐(Recall) 모두 중요 |
| Cohen's Kappa | 레이블 일치율 | 데이터셋 신뢰성의 필수 검증 지표 |
| ROC-AUC | 임계값 독립 전반 판별력 | 임계값 선택 없이 모델 자체 성능 비교 |
| MWU p-value | 클릭베이트/정상 그룹 점수 분포 차이 | alignment_score가 신호로서 유효한지 사전 검증 |
| 유형별 F1 / Recall | 유형 A/B/C 각각의 탐지 정확도 | 어떤 클릭베이트 유형에 시각 신호가 효과적인지, 반대로 잡음이 되는지 분석 |

### 5.3 주요 개념 설명

**Precision / Recall / F1**
- **Precision(정밀도)**: 클릭베이트라고 예측한 것 중 실제로 클릭베이트인 비율. 낮으면 정상
  영상을 클릭베이트로 잘못 신고(오탐)하는 경우가 많다는 뜻.
- **Recall(재현율)**: 실제 클릭베이트 중 탐지기가 잡아낸 비율. 낮으면 클릭베이트를 정상으로
  놓치는(미탐) 경우가 많다는 뜻.
- **F1**: Precision과 Recall의 조화 평균. 둘 다 높아야 F1이 높다. 오탐과 미탐 모두 중요할
  때 균형 지표로 사용.

**Cohen's Kappa (코헨 카파)**
두 평가자가 얼마나 일치하는지를 "우연에 의한 일치를 제거한 후"의 값으로 표현한다. -1~1
범위. 단순 일치율(Accuracy)의 문제: 클릭베이트가 50% 비율이면 무작위로 레이블해도 50%
일치 — 이를 보정한 게 Kappa. 0.7 이상이면 "상당한 일치(substantial agreement)"로
데이터셋을 신뢰할 수 있다고 판단한다.

**ROC-AUC (Receiver Operating Characteristic - Area Under Curve)**
탐지기의 임계값(threshold)을 0~1 전체 범위에서 변화시켰을 때 전반적 판별 능력을 하나의
숫자로 요약한 지표. 0.5이면 무작위 분류기와 동일, 1.0이면 완벽한 탐지기. 임계값 선택에
독립적으로 모델 자체의 판별력을 비교할 수 있어, M1~M3 모델 간 공정한 성능 비교에 적합하다.

**Mann-Whitney U-test (만-휘트니 U 검정)**
두 그룹의 분포가 같은지를 정규 분포 가정 없이 검정하는 비모수 방법. 여기서는 클릭베이트
그룹과 정상 그룹의 alignment_score 분포가 다른지를 검정한다. p < 0.05이면 두 그룹의
alignment_score 분포가 통계적으로 다르다 → CLIP 정합성 점수가 클릭베이트 탐지의 유효한
신호임을 사전 검증하는 단계.

### 5.4 해석 기준 (성공 조건)

- Cohen's Kappa > 0.7 → 레이블 신뢰 확보
- MWU p < 0.05 → alignment_score가 클릭베이트/정상 그룹을 유의하게 구분하는 신호임을 사전 검증
- M3 F1 > M1 F1 by ≥ 5%p → 시각 정합성 신호의 추가 기여 입증
- ROC-AUC(M3) > 0.75 → 실용적 탐지기 수준
- 유형 A에서 M2 Recall > M1 Recall by ≥ 20%p → "시각적 낚시" 가설 검증

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 레이블 신뢰도

| 항목 | 값 |
|------|-----|
| 2인 독립 레이블 일치 건수 | `[DATA]` / 300 |
| Cohen's Kappa | `[DATA]` |
| 불일치 후 3인 합의 처리 건수 | `[DATA]` |

### 6.2 정합성 점수 분포 비교

| 그룹 | 평균 alignment_score | 표준편차 |
|------|---------------------|---------|
| 클릭베이트 (n=`[DATA]`) | `[DATA]` | `[DATA]` |
| 정상 (n=`[DATA]`) | `[DATA]` | `[DATA]` |

Mann-Whitney U-test: `[DATA: U statistic, p-value]`

`[DATA: 두 그룹 alignment_score 분포 히스토그램/박스플롯 삽입]`

### 6.3 전체 탐지 성능 비교 (`[DATA: 5]`-fold CV)

| 방법 | Precision | Recall | F1 | ROC-AUC |
|------|-----------|--------|-----|---------|
| Random Baseline | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| M1 — Text-only | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| M2 — Visual-only | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| **M3 — Multimodal** | **`[DATA]`** | **`[DATA]`** | **`[DATA]`** | **`[DATA]`** |
| M4 — Type-aware (macro F1) | `[DATA]` | `[DATA]` | `[DATA]` | — |

M3 F1 − M1 F1 = `[DATA]`%p (해석 기준: ≥5%p)

### 6.4 유형별 탐지 성능

| 유형 | n | M1 F1 | M2 F1 | M3 F1 | M1 Recall | M2 Recall |
|------|---|-------|-------|-------|-----------|-----------|
| A (시각적 낚시) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| B (텍스트 낚시) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| C (혼합) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |

유형 A에서 M2 Recall − M1 Recall = `[DATA]`%p (해석 기준: ≥20%p)

### 6.5 정성적 사례 분석

`[DATA: 유형 A에서 M1은 놓쳤지만 M2/M3가 잡은 사례 1~2건 + 유형 B에서 M3가 M1보다
오히려 저조했던 사례가 있다면 그 원인 분석, 썸네일 설명 포함]`

### 6.6 연산 비용

`[DATA: CLIP 이미지/텍스트 인코더 추론 시간 실측치 — 300건 처리 기준]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- MWU 검정 결과가 alignment_score의 유효성을 사전에 뒷받침하는지, 그렇다면 클릭베이트
  그룹의 alignment_score가 정상 그룹보다 얼마나/어떤 방향으로 다른지
- M3가 M1 대비 전체적으로 개선되었는지, 해석 기준(≥5%p)을 충족했는지와 그 폭이 실용적으로
  의미 있는 수준인지
- 유형 A(시각적 낚시)에서 M2/M3가 M1을 크게 앞서는지 — "텍스트로는 원천적으로 탐지 불가능한
  클릭베이트 유형이 실제로 존재하고 시각 신호로 보완 가능하다"는 가설의 지지 여부
- 유형 B(텍스트 낚시)에서 시각 신호가 오히려 잡음으로 작용했는지(즉 M3 < M1) — 만약
  그렇다면 그 원인(예: 텍스트 낚시형은 썸네일 자체는 실제 내용과 정합적이라 alignment_score가
  낮지 않고, 오히려 멀티모달 특징이 텍스트 단독의 결정경계를 흐릴 수 있음)을 논의
- ThumbnailTruth·Multi-Modal-YT-Clickbait-Classifier와의 관계: 본 연구의 zero-shot M2가
  이들의 (추정되는) 성능에 얼마나 근접하는지 — 단, 직접 비교 실험은 수행하지 않았으므로
  추정에 그친다는 점을 명시
- 300건이라는 표본 크기에서 유형별 부분집합(A/B/C 각각 더 작은 n)의 통계적 신뢰도 한계

## 8. 한계 (Limitations)

- 데이터셋 규모가 300건(유형별로는 더 작음)으로, 유형별 세부 비교의 통계적 검정력이 제한적이다
- CLIP은 영어 중심으로 사전학습되어, 한국어 제목에 대한 텍스트 인코더 처리 품질이 사전
  검증되지 않았다 — alignment_score의 신뢰도 자체가 이 품질에 의존한다
- alignment_score는 정적 임계값 기반 신호로, 밈·풍자·반어법처럼 문맥에 의존하는 클릭베이트
  유형은 포착하기 어려울 수 있다
- 2인 레이블러의 판단 기준(특히 유형 A/B/C 경계)이 완전히 객관적이지 않으며, Kappa가
  전체 클릭베이트 여부 레이블에 대해서만 계산되고 유형 세부 레이블의 별도 신뢰도는
  보고되지 않을 수 있다
- ThumbnailTruth·Multi-Modal-YT-Clickbait-Classifier와 동일 데이터셋 기준의 직접 비교
  실험을 수행하지 않아, §2.1에서 제시한 차별화 논거(경량성)는 정량적으로 뒷받침되지 않는다
- 썸네일이 실제 영상 내용과 정합한지(video-thumbnail alignment)는 측정하지 않으며,
  제목-썸네일 정합성만을 신호로 사용한다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- 뉴스 기사 대표 이미지-헤드라인 정합성으로 확장 (뉴스 낚시 탐지)
- 실시간 파이프라인 통합: `data_registry`에 `clickbait_risk_score` 컬럼 추가
- 한국어 특화 CLIP fine-tuning으로 정합성 측정 정확도 향상
- ThumbnailTruth·Multi-Modal-YT-Clickbait-Classifier와의 동일 데이터셋 기준 직접 비교 실험

---

## 참고문헌 (References)

1. Chakraborty, A., Paranjape, B., Kakarla, S., & Ganguly, N. (2016). Stop Clickbait: Detecting and Preventing Clickbaits in Online News Media. *IEEE/ACM ASONAM*.
2. Anand, A., Chakraborty, T., & Park, N. (2017). We Used Neural Networks to Detect Clickbaits: You Won't Believe What Happened Next! arXiv:1710.08347.
3. Chen, C.-C., & Chen, S.-Y. (2022). Detecting Clickbait in Online Social Media: You Won't Believe How We Did It. arXiv:2209.14898.
4. Radford, A., et al. (2021). Learning Transferable Visual Models From Natural Language Supervision. *ICML*.
5. `[TODO]` ThumbnailTruth: A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails Across Diverse Cultural Settings. arXiv:2509.04714 (2025). *(저자명 확인 필요)*
6. `[TODO]` Multi-Modal-YT-Clickbait-Classifier (AlbertBS2). *(정식 서지정보/출처 확인 필요 — GitHub 프로젝트인지 학회 논문인지 포함)*

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 데이터셋 규모 확정 (전체/클릭베이트/정상/유형 A·B·C 각 건수)
- [ ] 6.1 Cohen's Kappa 및 일치 건수 삽입
- [ ] 6.2 alignment_score 분포 통계, MWU 검정 통계량/p-value 삽입 + 시각화
- [ ] 6.3 전체 성능 비교표(Precision/Recall/F1/ROC-AUC) 삽입
- [ ] 6.3 M3 F1 − M1 F1 %p 계산 및 해석 기준 충족 여부 명시
- [ ] 6.4 유형별 성능표 삽입, 유형 A에서 M2 Recall − M1 Recall %p 계산
- [ ] 6.5 정성적 사례 작성 (가설 지지 사례 + 유형 B 반례가 있다면 포함)
- [ ] 6.6 연산 비용 실측치 삽입
- [ ] 7장 논의 작성 (특히 유형 B 교차효과 여부와 선행 연구 관계)
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 참고문헌 5, 6번 `[TODO]` 서지정보 완성
- [ ] 제출 전 novelty 재검색 — ThumbnailTruth·Multi-Modal-YT-Clickbait-Classifier 외
      유사 연구가 추가로 있는지 재확인 (§2.1 경고 참고)
