# [예시용] 썸네일-텍스트 융합 임베딩을 이용한 한국어 YouTube 영상 검색 성능 향상: 시각 채널은 언제 도움이 되는가

> ⚠️ **이 문서 전체(특히 6장 실험 결과)는 가상 데이터로 작성된 예시 초안입니다.**
> 실제 실험을 수행하지 않았고, 논문 흐름·서술 방식을 미리 검토하기 위한 목적으로
> 그럴듯한 수치를 임의로 채워 넣었습니다. 실제 실험 후에는
> [paper_draft_P05_thumbnail_fusion.md](./paper_draft_P05_thumbnail_fusion.md)의
> `[DATA: ...]` 자리를 실측치로 교체해서 사용하세요.

> 작성일: 2026-07-08 (v2: 카테고리 분류 → 자동 gap 지표 재설계 반영)

---

## 제목 (Title)

**영문:** *Multimodal Video Retrieval via Thumbnail-Text Fusion Embeddings for Korean YouTube Content: When Does the Visual Channel Help?*

**국문:** 썸네일-텍스트 융합 임베딩을 이용한 한국어 YouTube 영상 검색 성능 향상: 시각 채널은 언제 도움이 되는가

---

## 초록

YouTube 영상 검색 시스템은 제목·설명·태그 등 텍스트 메타데이터에 의존하며 썸네일의
시각 정보를 활용하지 못한다. 본 연구는 CLIP ViT-B/32로 추출한 썸네일 시각 임베딩과
다국어 텍스트 임베딩(paraphrase-multilingual-mpnet-base-v2)을 late fusion 방식으로
결합해 검색 성능을 향상시키는 방법을 제안한다. 특정 주제 도메인에 한정하지 않고 여러
채널·주제에서 표본을 구성한 한국어 YouTube 영상 1,000편과 테스트 쿼리 50개로 평가한
결과, 제안 방법은 텍스트 단독 대비 MRR@10을 0.067 향상시켰다(Wilcoxon signed-rank
test, *p* = 0.0084). 사람이 라벨링한 콘텐츠 카테고리 대신 CLIP 결합 공간에서 자동
계산되는 **텍스트-이미지 의미 격차(gap)** 지표를 제안하고, 이 지표가 개별 영상의
순위 개선폭(Δrank)과 유의한 양의 상관관계를 가짐을 확인했다(Spearman ρ = 0.41,
*p* < 0.001). 다만 클릭베이트성 썸네일처럼 gap이 높아도 시각 정보가 오히려 검색에
도움이 되지 않는 예외 사례도 발견해, gap을 "정보성"이 아니라 "의미적 불일치" 자체로
해석해야 함을 논의한다.

**Keywords:** multimodal retrieval, CLIP, late fusion, thumbnail embedding, CLIPScore,
semantic gap, Korean YouTube, information retrieval

---

## 1. 서론

### 1.1 연구 배경 및 문제 정의

YouTube 영상 검색은 대부분 업로더가 입력한 텍스트 메타데이터(제목, 설명, 태그)에
의존한다. 그러나 썸네일은 영상 내용을 압축한 시각 요약으로, 텍스트에서 드러나지 않는
정보를 담고 있다. 시각 정보의 기여도가 영상마다 다를 것이라는 직관을 검증하는 데
있어, 본 연구는 사람이 눈으로 나눈 콘텐츠 카테고리(예: 다이어그램형/인물형/제품형)
대신 CLIP 자체의 이미지-텍스트 결합 공간에서 자동 계산되는 연속 지표를 사용한다.
라벨링이 필요 없고, 같은 모델·데이터로 누구나 동일하게 재현할 수 있다는 점이
핵심이다.

### 1.2 연구 질문

> 썸네일 시각 임베딩을 텍스트 임베딩과 결합했을 때, 텍스트 단독 대비 검색 정확도가
> 유의미하게 향상되는가? 이 향상은 영상별 텍스트-이미지 의미 격차(gap)가 클수록
> 더 크게 나타나는가?

### 1.3 기여점

1. CLIP 썸네일 임베딩 + 다국어 텍스트 임베딩 late fusion 검색 파이프라인 구축
2. 텍스트 단독 / 시각 단독 / late fusion 3방향 비교 실험을 통한 정량적 성능 향상 입증
3. 라벨링이 필요 없는 텍스트-이미지 의미 격차(gap) 지표 제안과 검색 순위 개선과의
   상관 분석
4. gap이 높아도 시각 정보가 도움이 되지 않는 예외(클릭베이트성 콘텐츠)를 실증해 gap
   지표의 해석 범위를 명확히 함
5. 운영 중인 메타데이터 플랫폼(`meta_youtube_video_vec`)에 시각 임베딩 컬럼을 추가하는
   실전 적용 가능한 스키마 확장 설계

---

## 2. 관련 연구

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Radford et al. (2021). "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*. | 이미지-텍스트 대조 학습 기반 모델. CLIP 결합 공간의 유사도가 정합성 지표로 널리 쓰임. | 한국어 YouTube 검색 적용 없음 |
| Hessel et al. (2021). "CLIPScore." *EMNLP*. | CLIP 이미지-텍스트 유사도를 캡션 품질 자동 평가에 사용. | 검색 순위 개선 예측에의 적용 없음 — 본 연구는 같은 계산식을 다른 목적에 사용 |
| Fang et al. (2021). "CLIP2Video." arXiv:2106.11097. | 프레임 단위 CLIP 임베딩의 시간 집계 기반 비디오-텍스트 검색(영어). | 썸네일 단일 프레임·한국어 세팅 아님 |
| Gao et al. (2022). "M2HF." arXiv:2208.07664. | 멀티레벨 프레임-캡션 융합. | 대규모 벤치마크 중심, 한국어·단일 이미지 세팅 아님 |
| Reimers & Gurevych (2019). "Sentence-BERT." *EMNLP*. | 다국어 텍스트 임베딩. | 시각 채널 융합 방법 미제시 |
| Li et al. (2022). "BLIP." *ICML*. | 이미지-텍스트 통합 검색·캡션·VQA. | 한국어 평가 없음; gap-검색기여도 분석 없음 |
| ThumbnailTruth (2025), arXiv:2509.04714 | CLIP 썸네일+텍스트 late fusion으로 클릭베이트 **분류**. | 랭킹 과제 아님, 한국어 없음 |

### 2.1 선행 연구 대비 위치

CLIP late fusion과 CLIPScore류 정합성 지표는 각각 독립적으로 연구되어 왔다. 본
연구의 novelty는 이 둘을 결합해, CLIPScore가 원래 측정하던 "정합성 부재"를 검색
순위 개선의 예측 변수로 재해석하고 실증했다는 점이다. 가장 가까운 선행 연구인
클릭베이트 탐지는 동일한 임베딩 스택을 쓰지만 랭킹이 아닌 분류 과제이며, 본 연구의
실험 결과(§6.4)는 오히려 클릭베이트성 콘텐츠가 gap 지표의 **반례**로 나타난다는
흥미로운 교차점을 보여준다.

---

## 3. 제안 방법

### 3.1 임베딩 추출

```
[검색용 임베딩]
썸네일 URL → CLIP ViT-B/32 (이미지 인코더) → 512-dim v_img
제목 + 설명 → paraphrase-multilingual-mpnet-base-v2 → 768-dim → PCA 512-dim v_txt

[gap 계산 전용 임베딩]
제목 → clip-ViT-B-32-multilingual-v1 (CLIP 이미지 공간 정렬 다국어 인코더) → 512-dim g_txt
```

### 3.2 텍스트-이미지 의미 격차 (gap)

```
gap_i = 1 - cos_sim(v_img_i, g_txt_i)
```

### 3.3 Fusion 방법

```
Late Fusion:    score = α · sim(q_img, d_img) + (1-α) · sim(q_txt, d_txt)
Concat Fusion:  [v_img ; v_txt] → 1024-dim 단순 연결
Learned Fusion: validation 쿼리 20개로 학습한 선형 파라미터
```

### 3.4 gap 가설

```
Δrank(v,q) = rank_text(v|q) - rank_fusion(v|q)
가설: Spearman ρ(gap, Δrank) > 0
```

---

## 4. 실험 설계

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| 영상 수 | 1,000편 (여러 채널·주제에서 표집, 도메인 제한 없음) |
| 테스트 쿼리 수 | 50개 |
| Validation 쿼리 수 | 20개 |
| Relevance 레이블링 | 상위 20개 후보 × 2인 독립 평가, 불일치 시 제3자 조정 |
| gap 분포 | 평균 0.34, 표준편차 0.11, 최소 0.08, 최대 0.71 (전체 1,000편 자동 계산) |
| qrels (쿼리-관련영상) 쌍 수 | 386쌍 (쿼리당 평균 7.7개 관련 영상) |
| 데이터 소스 | `meta_youtube_video`, `meta_youtube_video_vec` |

### 4.2 실험 절차

1. 쿼리셋 50개 구축 및 관련성 레이블링 (2인 독립).
2. Validation 쿼리 20개로 α 그리드 탐색 → α* = 0.3.
3. 1,000편 전체에 대해 gap 자동 계산 (라벨링 없음).
4. qrels 386쌍에서 Δrank 계산 후 gap과의 Spearman 상관 분석.

---

## 5. 평가 방법

### 5.1 비교 대상

| 방법 | 설명 |
|------|------|
| Text-only | 텍스트 임베딩 단독 |
| Visual-only | CLIP 썸네일 임베딩 단독 |
| Late Fusion (α=0.3) | **제안 방법** |
| Concat Fusion | 벡터 단순 연결 |
| Learned Fusion | validation 학습 가중치 |

### 5.2 지표

MRR@10, NDCG@10, Recall@10, Spearman ρ(gap, Δrank)

### 5.3 통계 검정

Wilcoxon signed-rank test (전체 비교), Spearman 순위 상관 검정 (gap 가설)

### 5.4 해석 기준

- Late Fusion MRR@10 > Text-only + 0.05
- Wilcoxon p < 0.05
- Spearman ρ(gap, Δrank) > 0, p < 0.05

---

## 6. 실험 결과

> ⚠️ 이하 수치는 전부 가상 데이터입니다.

### 6.1 전체 성능 비교

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|------|--------|---------|-----------|
| Text-only | 0.591 | 0.624 | 0.712 |
| Visual-only | 0.417 | 0.452 | 0.548 |
| Concat Fusion | 0.605 | 0.631 | 0.719 |
| Learned Fusion | 0.649 | 0.668 | 0.744 |
| **Late Fusion (α=0.3)** | **0.658** | **0.677** | **0.751** |

Wilcoxon signed-rank test (Late Fusion vs. Text-only): W = 312, *p* = 0.0084

Δ(Late Fusion − Text-only) = 0.067 (해석 기준 충족)

### 6.2 α 그리드 탐색 곡선

| α | 0.1 | 0.3 | 0.5 | 0.7 | 0.9 |
|---|-----|-----|-----|-----|-----|
| MRR@10 (validation) | 0.629 | **0.658** | 0.641 | 0.588 | 0.489 |

### 6.3 gap과 순위 개선의 상관관계

| 통계량 | 값 |
|--------|-----|
| Spearman ρ(gap, Δrank) | **0.41** |
| p-value | < 0.001 |
| 표본 수 (쿼리-영상 쌍) | 386 |

gap이 클수록 융합에 의한 순위 개선폭이 유의하게 커지는 경향이 확인되었다 (해석
기준 충족). 참고용 3분위 시각화:

| gap 구간 | 평균 gap | 평균 Δrank |
|---------|---------|-----------|
| 하위 33% (gap < 0.27) | 0.19 | 1.2 |
| 중위 33% (0.27–0.41) | 0.34 | 3.8 |
| 상위 33% (gap > 0.41) | 0.53 | 7.6 |

### 6.4 정성적 사례 분석

**사례 1 (가설 지지, 고gap)** — "HBM4 적층 구조 설명" 검색. 영상 제목은 "차세대
메모리 신제품 소개"로 텍스트만으로는 쿼리와의 연관성이 낮았다(gap=0.62). 썸네일이
적층 다이어그램을 직접 보여주어 Δrank=+11(Text-only 14위 → Late Fusion 3위).

**사례 2 (가설 지지, 고gap)** — "무선 이어폰 언박싱 비교" 검색. 제목이 "이거
실화냐"로 정보성이 낮았으나(gap=0.58) 제품 사진이 뚜렷해 Δrank=+9.

**사례 3 (반례, 고gap이지만 도움 안 됨)** — "AI 반도체 시장 전망" 검색. 관련
영상의 제목은 평이했으나 썸네일이 놀란 표정의 클로즈업 얼굴 사진(클릭베이트성)이라
gap=0.67로 매우 높았다. 그러나 이 썸네일은 실제 영상 내용과도 무관해, 시각
임베딩이 질의와의 유사도를 높이지 못했고 Δrank=-2로 오히려 순위가 하락했다. 즉
gap이 높다는 것은 "썸네일이 제목과 다른 내용을 말한다"는 뜻일 뿐, 그 내용이 쿼리에
유용한 정보인지는 보장하지 않는다.

### 6.5 연산 비용

CLIP 이미지 인코더 추론(썸네일 1,000장, batch=32, CPU 전용, Apple M2): 32분.
gap 계산용 다국어 텍스트 인코더 추론(제목 1,000건): 5분. 검색용 mpnet 텍스트
임베딩(1,000건): 4분. 총 41분으로 GPU 없이도 완료 가능한 수준.

---

## 7. 논의

**gap 가설 지지** — Spearman ρ=0.41(p<0.001)은 중간 정도의 양의 상관으로, gap이
클수록 시각 채널이 검색 순위 개선에 기여한다는 가설을 지지한다. 다만 상관계수가
1에 가깝지 않다는 점은 gap만으로 시각 정보의 기여도를 완전히 설명하지는 못함을
시사한다 — §6.4의 사례 3처럼 gap이 "정보성 격차"가 아니라 단순한 "의미적 불일치"를
잴 뿐이라는 근본적 한계 때문일 수 있다.

**Concat/Learned Fusion과의 비교** — Concat Fusion은 미미한 개선(Δ=0.014)에
그쳤고, 흥미롭게도 Learned Fusion(0.649)은 grid search 기반 Late Fusion(0.658)보다
낮은 성능을 보였다. validation 쿼리가 20개뿐이라는 점을 고려하면 과적합
가능성이 있다 — 파라미터 수가 적더라도 데이터가 부족하면 단순 grid search보다
불안정할 수 있다는 실무적 시사점이다.

**클릭베이트 반례의 함의** — gap이 "정보 유용성"이 아니라 "의미적 불일치"를 잴
뿐이라는 점은 gap 지표를 실무에 적용할 때 중요한 함의를 갖는다. 클릭베이트 탐지
연구(ThumbnailTruth 등)와 본 연구의 gap이 사실상 같은 신호(썸네일-제목 불일치)를
정반대 목적(검색 향상 vs. 오도 탐지)으로 사용하고 있다는 점도 흥미로운
교차점이다 — 두 목적을 구분하려면 gap 외에 "썸네일이 실제 영상 내용과 일치하는가"
라는 별도 신호가 필요할 수 있다.

## 8. 한계

- 테스트 쿼리 50개, 평가자 2인 — 통계적 검정력의 한계
- gap은 CLIP 결합 공간에 정렬된 다국어 텍스트 인코더의 한국어 이해력에 의존하며,
  이 인코더 자체의 한국어 성능을 별도로 검증하지 않았다
- gap은 제목-썸네일 정합성만 측정하며 description이나 실제 영상 내용과의 정합성은
  반영하지 못한다 — §6.4 사례 3처럼 "불일치가 유용한 정보 때문인지, 오도성 콘텐츠
  때문인지"를 gap만으로는 구분할 수 없다
- Spearman 상관관계는 인과관계를 증명하지 않는다
- Learned Fusion의 저조한 성능이 방법 자체의 한계인지 validation 쿼리 수 부족
  때문인지 완전히 분리해 확인할 수 없다

## 9. 결론

본 연구는 CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 late fusion이 한국어 YouTube
검색에서 텍스트 단독 대비 통계적으로 유의한 성능 향상(MRR@10 +0.067,
*p*=0.0084)을 가져옴을 실증했다. 사람이 라벨링한 콘텐츠 카테고리 대신 CLIP
결합 공간에서 자동 계산되는 텍스트-이미지 의미 격차(gap) 지표를 제안했고, 이
지표가 개별 영상의 순위 개선폭과 유의한 양의 상관관계를 가짐을 확인했다(Spearman
ρ=0.41, p<0.001). 다만 클릭베이트성 콘텐츠에서는 gap이 높아도 시각 정보가 도움이
되지 않는 반례가 발견되어, gap을 "정보 유용성"이 아니라 "의미적 불일치"로 해석해야
한다는 점을 명확히 했다.

향후 연구로는 (1) gap과 별도로 "썸네일-실제 영상 내용" 정합성을 측정하는 2차 신호
도입, (2) 썸네일 단일 프레임 대신 대표 프레임 3장으로 확장, (3) 한국어 기술 도메인
특화 CLIP fine-tuning을 통한 임베딩 품질 개선을 고려할 수 있다.

---

## 참고문헌

1. Radford, A., et al. (2021). Learning Transferable Visual Models From Natural Language Supervision. *ICML*.
2. Hessel, J., Holtzman, A., Forbes, M., Bras, R. L., & Choi, Y. (2021). CLIPScore: A Reference-free Evaluation Metric for Image Captioning. *EMNLP*.
3. Fang, H., et al. (2021). CLIP2Video: Mastering Video-Text Retrieval via Image CLIP. arXiv:2106.11097.
4. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP*.
5. Li, J., et al. (2022). BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation. *ICML*.
6. Gao, Z., et al. (2022). M2HF: Multi-level Multi-modal Hybrid Fusion for Text-Video Retrieval. arXiv:2208.07664.
7. ThumbnailTruth: A Multi-Modal LLM Approach for Detecting Misleading YouTube Thumbnails Across Diverse Cultural Settings. arXiv:2509.04714 (2025). *(저자명 확인 필요)*
