# 논문 초안: YouTube 썸네일+텍스트 멀티모달 임베딩을 이용한 영상 검색 성능 향상

> 기반 기획서: [research_proposals.md](./research_proposals.md) P05
> 작성일: 2026-07-08 (v2: 카테고리 분류 → 자동 gap 지표로 재설계)
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)
>
> **v1 → v2 변경 요약**: 기존 설계는 썸네일을 "기술설명형/인물형/제품형"으로 사람이
> 수동 분류해 카테고리별 효과를 비교했다. 이 방식은 (1) 분류 기준이 주관적이고
> 재현 불가능하며, (2) 2인 라벨링 비용이 든다는 문제가 있었다. v2는 카테고리 분류를
> 완전히 제거하고, CLIP 자체의 이미지-텍스트 결합 공간에서 자동 계산되는 연속 지표
> **"텍스트-이미지 의미 격차(gap)"**로 대체했다. 라벨링 비용 없이 전체 코퍼스에
> 자동 적용되며, 회귀/상관 분석으로 가설을 검증한다.

---

## 제목 (Title)

**영문:** *Multimodal Video Retrieval via Thumbnail-Text Fusion Embeddings for Korean YouTube Content: When Does the Visual Channel Help?*

**국문:** 썸네일-텍스트 융합 임베딩을 이용한 한국어 YouTube 영상 검색 성능 향상: 시각 채널은 언제 도움이 되는가

---

## Abstract

YouTube video search systems predominantly rely on textual metadata (title, description, tags),
leaving the visual information encoded in thumbnails largely unexploited. We propose a
late-fusion retrieval method that combines CLIP-derived thumbnail embeddings with multilingual
text embeddings, and evaluate it on a Korean YouTube corpus of `[DATA: N videos]` videos sampled
across multiple topics (not restricted to a single domain), with `[DATA: 50]` test queries. Rather
than relying on manually annotated content categories — which are subjective and costly to
label — we introduce a fully automatic, reproducible metric: the **text-image semantic gap**,
computed as the CLIP-space cosine distance between a video's thumbnail and its title. We test
whether this gap predicts the per-video rank improvement gained from fusion. We show that fusion
improves MRR@10 by `[DATA: Δ]` over the text-only baseline (Wilcoxon signed-rank test,
`[DATA: p-value]`), and that gap is positively correlated with rank improvement (Spearman ρ =
`[DATA]`, `[DATA: p-value]`), supporting the hypothesis that the visual channel contributes most
when the thumbnail conveys information absent from the text.

**국문 초록 (draft):** YouTube 영상 검색 시스템은 제목·설명·태그 등 텍스트 메타데이터에
의존하며 썸네일의 시각 정보를 활용하지 못한다. 본 연구는 CLIP ViT-B/32로 추출한 썸네일
시각 임베딩과 다국어 텍스트 임베딩을 late fusion 방식으로 결합해 검색 성능을 향상시키는
방법을 제안한다. 특정 주제 도메인에 한정하지 않고 여러 채널·주제에서 표본을 구성한
한국어 YouTube 영상 `[DATA: N]`개와 `[DATA: 50]`개 테스트 쿼리로 평가한다. 사람이 수동
분류한 콘텐츠 카테고리 대신, CLIP 결합 공간에서 자동 계산되는 **텍스트-이미지 의미
격차(gap)** 지표를 제안하고, 이 지표가 개별 영상의 순위 개선폭을 예측하는지 검증한다.

**Keywords:** multimodal retrieval, CLIP, late fusion, thumbnail embedding, CLIPScore,
semantic gap, Korean YouTube, information retrieval

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

YouTube 영상 검색은 대부분 업로더가 입력한 텍스트 메타데이터(제목, 설명, 태그)에
의존한다. 그러나 썸네일은 영상 내용을 압축한 시각 요약으로, 텍스트에서 드러나지 않는
정보(등장 제품, 화면 구성, 감성 톤)를 담고 있다.

시각 정보가 검색에 기여하는 정도는 영상마다 다를 것이다. 이를 설명하는 자연스러운
접근은 "기술 설명형·인물형·제품형" 같은 콘텐츠 카테고리를 사람이 눈으로 나누고
카테고리별 효과를 비교하는 것이다. 그러나 이 접근은 두 가지 근본적인 문제를 갖는다.
(1) 카테고리 경계가 주관적이다 — 다이어그램과 발표자 얼굴이 함께 있는 썸네일은
어느 쪽인가? (2) 재현 불가능하다 — 다른 연구자가 같은 데이터를 다시 라벨링하면
다른 카테고리 정의를 쓸 수 있다. 게다가 라벨링 자체에 인력 비용이 든다.

### 1.2 연구 질문

> 썸네일 시각 임베딩을 텍스트 임베딩과 결합했을 때, 텍스트 단독 대비 검색 정확도가
> 유의미하게 향상되는가? 이 향상은 영상별 **텍스트-이미지 의미 격차(gap)** — 썸네일이
> 제목에 없는 정보를 얼마나 담고 있는지를 CLIP 결합 공간에서 잰 값 — 이 클수록 더
> 크게 나타나는가?

카테고리 대신 gap을 쓰는 이유는 라벨링 없이 이미 계산 중인 임베딩만으로 완전 자동·
재현 가능하게 산출되기 때문이다.

### 1.3 기여점 (Contributions)

1. CLIP 썸네일 임베딩 + 다국어 텍스트 임베딩(paraphrase-multilingual-mpnet-base-v2) late
   fusion 검색 파이프라인 구축
2. 텍스트 단독 / 시각 단독 / late fusion 3방향 비교 실험을 통한 정량적 성능 향상 입증
3. 라벨링이 필요 없는 **텍스트-이미지 의미 격차(gap)** 지표 제안 — CLIP 이미지 인코더와
   CLIP 이미지 공간에 정렬된 다국어 텍스트 인코더로 계산
4. gap과 융합에 의한 검색 순위 개선(Δrank)의 상관/회귀 분석을 통한 "시각 정보는 언제
   도움이 되는가"에 대한 정량적 답변
5. 운영 중인 메타데이터 플랫폼(`meta_youtube_video_vec`)에 시각 임베딩 컬럼을 추가하는
   실전 적용 가능한 스키마 확장 설계

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Radford et al. (2021). "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*. | 이미지-텍스트 대조 학습으로 zero-shot 이미지 분류·검색의 기반 모델 확립. CLIP 결합 공간의 코사인 유사도가 두 모달의 의미적 정합성 지표로 널리 쓰임. | 한국어 도메인 YouTube 검색 적용·평가 없음 |
| Hessel et al. (2021). "CLIPScore: A Reference-free Evaluation Metric for Image Captioning." *EMNLP*. | CLIP 이미지-텍스트 유사도를 캡션 품질의 자동 평가 지표로 확립. | 캡션 품질 평가가 목적이며, 검색 성능 기여도 예측에의 적용은 없음 — 본 연구는 같은 계산식을 다른 목적(검색 기여도 예측)에 사용 |
| Fang et al. (2021). "CLIP2Video: Mastering Video-Text Retrieval via Image CLIP." arXiv:2106.11097. | 프레임 단위 CLIP 임베딩을 시간 집계해 비디오-텍스트 검색에 적용(영어 MSR-VTT). | 다중 프레임 시간 집계 필요 — 본 연구는 썸네일 단일 프레임으로 비용을 낮춘 대안 |
| Gao et al. (2022). "M2HF: Multi-level Multi-modal Hybrid Fusion for Text-Video Retrieval." arXiv:2208.07664. | 전체 비디오 프레임 시퀀스와 텍스트 캡션 간의 멀티레벨 융합. | 프레임 시퀀스·자막 기반 대규모 벤치마크 중심, 한국어·썸네일 단일 이미지 세팅 아님 |
| Reimers & Gurevych (2019). "Sentence-BERT." *EMNLP*. | 다국어 텍스트 임베딩 모델. | 시각 채널과의 융합 방법·최적 가중치 미제시 |
| Li et al. (2022). "BLIP." *ICML*. | 이미지-텍스트 통합 검색·캡션·VQA 아키텍처. | 한국어 도메인 평가 없음; gap과 검색 기여도의 관계 분석 없음 |
| AlbertBS2, "Multi-Modal YT Clickbait Classifier"; ThumbnailTruth, arXiv:2509.04714 (2025) | CLIP 썸네일 임베딩 + 텍스트의 late fusion으로 클릭베이트 **분류**. 임베딩 스택이 유사. | 과제가 이진 분류이며 랭킹 지표(MRR/NDCG) 평가가 아님. 한국어 데이터 없음 |

### 2.1 선행 연구 대비 위치 (Positioning)

- CLIP 기반 late fusion 자체와 CLIPScore류 이미지-텍스트 정합성 지표는 각각 널리
  연구된 요소다. 본 연구의 기여는 **이 둘을 결합**한 데 있다 — CLIPScore가 원래
  측정하던 "정합성"을 캡션 품질이 아니라 **검색 순위 개선의 예측 변수**로 재해석하고
  실증한 연구는 확인되지 않았다.
- 가장 가까운 선행 연구(클릭베이트 탐지)는 동일한 임베딩 스택을 쓰지만 과제가
  분류이지 랭킹이 아니며, 카테고리/연속 지표 어느 쪽으로도 콘텐츠를 세분화해
  검색 기여도를 분석하지 않는다.
- 전체 프레임 시퀀스를 쓰는 CLIP4Clip류와 달리 썸네일 단일 이미지만 사용해 프레임
  추출·시간 집계 비용이 없다.
- 한국어 YouTube 도메인에서의 실증 평가는 확인된 선행 연구가 없다.

> **⚠️ 검증 필요:** 위 novelty 주장은 2026-07-08 웹 검색 결과 기준이며, 학회 제출 전
> 최신 arXiv/ACL Anthology/DBLP 재검색으로 최근 6개월 내 유사 연구가 없는지 재확인할 것.
> 특히 "CLIPScore rank improvement retrieval", "image-text gap retrieval fusion" 키워드로
> ACL/SIGIR/CIKM 최근 프로시딩을 직접 확인 권장.

---

## 3. 제안 방법 (Methodology)

### 3.1 임베딩 추출

```
[검색용 임베딩]
썸네일 URL → 다운로드 → CLIP ViT-B/32 (이미지 인코더) → 512-dim 시각 벡터 v_img
제목 + 설명 → paraphrase-multilingual-mpnet-base-v2 → 768-dim → PCA 512-dim v_txt

[gap 계산 전용 임베딩 — 검색 파이프라인과 별개]
제목 → clip-ViT-B-32-multilingual-v1 (CLIP 이미지 공간에 정렬된 다국어 텍스트 인코더)
     → 512-dim g_txt
```

> **왜 두 개의 서로 다른 텍스트 인코더를 쓰는가**: 검색 채널의 v_txt(mpnet)는
> 한국어 검색 품질이 좋지만 CLIP의 이미지 인코더와 같은 공간에서 학습되지 않았다.
> late fusion에서는 `sim(q_img, d_img)`와 `sim(q_txt, d_txt)`를 각각 독립적으로
> 계산해 가중합하므로 두 공간이 달라도 문제없다. 그러나 "이미지와 텍스트가 서로
> 얼마나 같은 내용을 말하는가"를 재는 gap 지표는 반드시 **같은 결합 공간**에서
> 계산해야 의미가 있다. 따라서 gap 전용으로 CLIP 이미지 임베딩에 정렬되도록
> distillation 학습된 다국어 CLIP 텍스트 인코더(`clip-ViT-B-32-multilingual-v1`)를
> 별도로 사용한다.

### 3.2 텍스트-이미지 의미 격차 (gap)

```
gap_i = 1 - cos_sim(v_img_i, g_txt_i)     # i = 영상 인덱스, 0(완전 중복)~1(완전 무관)
```

CLIPScore(Hessel et al., 2021)와 계산식은 동일하나 용도가 다르다 — 원 논문은 캡션
품질의 자동 평가에 썼고, 본 연구는 "썸네일이 제목에 없는 정보를 얼마나 담는가"를
재는 데 쓴다. 라벨링 없이 전체 코퍼스에 자동 적용되며, 임베딩 추출 파이프라인의
부산물이므로 추가 비용이 거의 없다.

### 3.3 Fusion 방법

```
Late Fusion:    score = α · sim(q_img, d_img) + (1-α) · sim(q_txt, d_txt)
                α ∈ {0.1, 0.3, 0.5, 0.7, 0.9}

Concat Fusion:  [v_img ; v_txt] → 1024-dim 단순 연결

Learned Fusion: validation 쿼리 20개로 학습한 선형 파라미터 α*
```

### 3.4 gap 가설

```
qrels의 모든 (쿼리, 관련 영상) 쌍에 대해:
  rank_text(v|q)   = Text-only 순위
  rank_fusion(v|q) = Late Fusion 순위
  Δrank(v,q) = rank_text(v|q) - rank_fusion(v|q)    (양수 = 순위 개선)

가설: Δrank는 해당 영상의 gap과 양의 상관관계를 갖는다
      (Spearman ρ(gap, Δrank) > 0)
```

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

주제 도메인으로 영상을 필터링하지 않는다. gap 가설 검증에 필요한 것은 카테고리
균형이 아니라 **gap 값 자체의 분산**(낮은 gap과 높은 gap 영상이 고루 섞여 있는 것)
이므로, 여러 주제의 채널에서 다양하게 표집하면 충분하다. 카테고리 라벨링 단계가
없으므로 기존 운영 파이프라인(`data_registry`) 수집분을 그대로 활용할 수 있다.

| 항목 | 값 |
|------|-----|
| 영상 수 | `[DATA: N]` (제안서 목표: 1,000편) |
| 표본 구성 기준 | 주제 도메인 무관, 여러 채널에서 표집 (gap 분산 확보 목적) |
| 테스트 쿼리 수 | `[DATA: 50]` |
| Validation 쿼리 수 (α 탐색용) | `[DATA: 20]` |
| Relevance 레이블링 | 상위 20개 후보 × 2인 독립 평가 (관련/부분관련/무관) |
| gap 계산 | 1,000편 전체에 대해 자동 계산 (사람 라벨링 없음) |
| 데이터 소스 | `meta_youtube_video`, `meta_youtube_video_vec` |

### 4.2 실험 절차

1. **쿼리셋 구축 및 레이블링** — 테스트 쿼리 `[DATA: 50]`개 작성, 영상별 상위 20개 후보
   관련성 2인 독립 평가.
2. **가중치 탐색 (Validation)** — validation 쿼리 `[DATA: 20]`개로 α 그리드 탐색,
   MRR@10 최대 α 선택 → `[DATA: α* = ?]`
3. **gap 계산** — 1,000편 전체에 대해 v_img, g_txt를 뽑아 gap_i 산출 (자동, 라벨링 없음).
4. **gap-Δrank 상관 분석** — qrels의 모든 (쿼리, 관련 영상) 쌍에서 Δrank를 계산하고
   Spearman 상관계수 산출.

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상 (Baselines)

| 방법 | 설명 |
|------|------|
| Text-only | 텍스트 임베딩 단독 |
| Visual-only | CLIP 썸네일 임베딩 단독 |
| Late Fusion (최적 α) | **제안 방법** |
| Concat Fusion | 벡터 단순 연결 |
| Learned Fusion | validation으로 학습된 가중치 |

### 5.2 지표

| 지표 | 측정 대상 |
|------|----------|
| MRR@10 | 첫 관련 결과의 순위 역수 평균 |
| NDCG@10 | 상위 10개 순위 가중 품질 |
| Recall@10 | 정답 중 상위 10개 안에 포함된 비율 |
| Spearman ρ(gap, Δrank) | gap이 순위 개선을 예측하는 정도 |

### 5.3 통계 검정

- **Wilcoxon signed-rank test**(비모수, paired) — 쿼리별 MRR 차이에 순위를 매겨
  Late Fusion과 Text-only 간 전체 성능 차이의 유의성을 검정 (p < 0.05 기준).
- **Spearman 순위 상관 검정** — gap과 Δrank의 단조 관계 유의성을 검정 (p < 0.05 기준).

### 5.4 해석 기준 (성공 조건)

- Late Fusion MRR@10 > Text-only + 0.05
- Wilcoxon signed-rank test p < 0.05 (전체 비교)
- Spearman ρ(gap, Δrank) > 0, p < 0.05 (gap 가설)

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 전체 성능 비교

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|------|--------|---------|-----------|
| Text-only | `[DATA]` | `[DATA]` | `[DATA]` |
| Visual-only | `[DATA]` | `[DATA]` | `[DATA]` |
| Concat Fusion | `[DATA]` | `[DATA]` | `[DATA]` |
| Learned Fusion | `[DATA]` | `[DATA]` | `[DATA]` |
| **Late Fusion (α=`[DATA]`)** | **`[DATA]`** | **`[DATA]`** | **`[DATA]`** |

Wilcoxon signed-rank test (Late Fusion vs. Text-only): `[DATA: statistic, p-value]`

### 6.2 α 그리드 탐색 곡선

`[DATA: α ∈ {0.1, 0.3, 0.5, 0.7, 0.9}에 대한 MRR@10 곡선 — 그래프 또는 표로 삽입]`

### 6.3 gap과 순위 개선의 상관관계

| 통계량 | 값 |
|--------|-----|
| Spearman ρ(gap, Δrank) | `[DATA]` |
| p-value | `[DATA]` |
| 표본 수 (쿼리-영상 쌍) | `[DATA]` |

`[DATA: gap(x축) vs. Δrank(y축) 산점도 + 회귀선 삽입]`

참고용 시각화 (연속 변수를 3분위로 나눈 것일 뿐, 분석의 근거가 되는 그룹 정의가 아님):

| gap 구간 | 평균 gap | 평균 Δrank |
|---------|---------|-----------|
| 하위 33% | `[DATA]` | `[DATA]` |
| 중위 33% | `[DATA]` | `[DATA]` |
| 상위 33% | `[DATA]` | `[DATA]` |

### 6.4 정성적 사례 분석

`[DATA: gap이 높고 Δrank가 큰 사례 1~2건 + gap이 높은데도 Δrank가 작은(가설에 어긋나는) 사례 1건, 썸네일 설명 포함]`

### 6.5 연산 비용

`[DATA: CLIP 이미지 인코더 + gap용 다국어 텍스트 인코더 추론 시간 실측치]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- gap 가설 지지 여부와 그 이유
- Concat/Learned Fusion 대비 단순 Late Fusion이 경쟁력 있는 이유 (또는 없는 이유)
- gap이 높은데도 융합이 도움 되지 않은 예외 사례가 있다면 그 원인 (예: 텍스트-이미지가
  둘 다 질의와 무관한 경우 — gap은 높지만 어느 쪽도 검색에 유용하지 않음)
- gap 지표 자체의 신뢰도: 다국어 CLIP 텍스트 인코더의 한국어 이해력이 gap 계산
  정확도에 미치는 영향

## 8. 한계 (Limitations)

- 테스트 쿼리 `[DATA: 50]`개, 평가자 2인 — 통계적 검정력의 한계
- gap은 CLIP 결합 공간에 정렬된 다국어 텍스트 인코더의 품질에 의존한다. 이 인코더
  자체의 한국어 성능이 검증되지 않으면 gap 값의 신뢰도도 함께 흔들린다
- gap은 제목-썸네일 정합성만 측정하며, 설명(description)이나 영상 내용 자체와의
  정합성은 반영하지 못한다
- 상관관계(Spearman ρ)는 인과관계를 증명하지 않는다 — gap이 높은 영상이 우연히
  다른 요인(예: 채널 인기도)과 함께 움직일 가능성을 배제하지 못한다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- 썸네일 단일 프레임 → 영상 대표 프레임 3장 샘플링으로 확장
- 썸네일 변경 감지: 리그랜트 후 A/B 썸네일 교체 탐지
- CLIP fine-tuning으로 한국어 기술 도메인 특화
- gap을 실시간 파이프라인에 적재해 시각 임베딩 계산을 gap이 높은 영상에만 선별
  적용하는 비용 절감 전략으로 확장

---

## 참고문헌 (References)

1. Radford, A., et al. (2021). Learning Transferable Visual Models From Natural Language Supervision. *ICML*.
2. Hessel, J., Holtzman, A., Forbes, M., Bras, R. L., & Choi, Y. (2021). CLIPScore: A Reference-free Evaluation Metric for Image Captioning. *EMNLP*.
3. Fang, H., et al. (2021). CLIP2Video: Mastering Video-Text Retrieval via Image CLIP. arXiv:2106.11097.
4. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP*.
5. Li, J., et al. (2022). BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation. *ICML*.
6. Gao, Z., et al. (2022). M2HF: Multi-level Multi-modal Hybrid Fusion for Text-Video Retrieval. arXiv:2208.07664.
7. `[TODO]` ThumbnailTruth: A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails Across Diverse Cultural Settings. arXiv:2509.04714 (2025).

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 데이터셋 규모 (N, 쿼리 수) 확정
- [ ] 4.2 α* (최적 융합 가중치) 확정
- [ ] 6.1 전체 성능 비교표 수치 삽입
- [ ] 6.1 Wilcoxon 검정 통계량/p-value 삽입
- [ ] 6.2 α 그리드 곡선 삽입
- [ ] 6.3 Spearman ρ(gap, Δrank), p-value, 산점도 삽입
- [ ] 6.4 정성적 사례 작성 (가설 지지 사례 + 반례)
- [ ] 6.5 연산 비용 실측치 삽입
- [ ] 7장 논의 작성
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 참고문헌 7번 `[TODO]` 서지정보 완성
- [ ] 제출 전 novelty 재검색 (2.1절 경고 참고)
