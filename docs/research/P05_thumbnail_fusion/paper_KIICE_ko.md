<!-- 한국정보통신학회 춘·추계 종합학술대회 제출용 초안 (KIICE format).
     본문 2단·국문 함초롱바탕 등 조판은 HWP 양식에서 적용. 이 파일은 내용 원고.
     ⟦DATA⟧ = 라벨링·실험 후 실수치로 교체. 저자/소속/과제문구는 [ ] 플레이스홀더. -->

# 썸네일은 언제 검색에 도움이 되는가: 한국어 YouTube에서 시각–텍스트 의미 격차와 검색 순위 개선의 관계 분석

**When Does the Thumbnail Help Retrieval? The Visual–Text Semantic Gap and Retrieval Rank Improvement in Korean YouTube Search**

[저자1] · [저자2]<sup>*</sup>  
[소속1] · [소속2]  
[Author1] · [Author2]<sup>*</sup>  
[Affiliation1] · [Affiliation2]  
E-mail : [email1] / [email2]

---

## 요 약

영상 메타데이터 검색은 제목·설명 등 텍스트에 주로 의존하며, 썸네일의 시각 정보는 거의
활용되지 않는다. 시각 정보를 텍스트와 결합(fusion)하면 검색 성능이 오른다는 것은 알려져
있으나, **그 개선이 모든 영상에서 균일하게 나타나는지, 특정 조건에서만 나타나는지**는
규명되지 않았다. 본 연구는 이 조건을 **라벨링 없이 자동 계산되는 연속 지표**인 **시각–텍스트
의미 격차(gap; visual–text semantic gap)** 로 특성화한다. gap은 CLIP 결합 공간에서 썸네일과
제목이 얼마나 비정렬(misaligned)되어 있는지를 나타내는 영상 수준 지표로, 정합성의 여집합으로
정의되며 임베딩 추출의 부산물로 얻어진다. 한국어 YouTube 영상 ⟦DATA:840⟧편과 검색어
⟦DATA:70⟧개로 CLIP 이미지 임베딩과 다국어 텍스트 임베딩의 late fusion을 평가하여, **융합이
text-only 대비 검색 성능을 향상시키는지, 그리고 gap이 융합에 의한 순위 개선과 관련되는지를
실증적으로 검증한다** ⟦DATA⟧. 본 연구의 기여는 새로운 융합 기법이 아니라 시각 정보의 기여
조건을 정량적으로 다루는 지표를 제안한 데 있으며, 이는 gap이 높은 영상에 시각 임베딩을 선별
적용하는 **메타데이터 검색 플랫폼의 적응형 확장** 가능성을 탐색하는 근거가 될 수 있다.

## ABSTRACT

Video metadata retrieval relies mostly on textual fields such as titles, leaving the visual
information in thumbnails largely unused. While fusing visual and textual signals is known to
improve retrieval, whether this improvement is uniform across videos or arises only under
specific conditions remains unclear. We characterize this condition with a continuous,
label-free metric—the *visual–text semantic gap*—defined as the complement of thumbnail–title
alignment in the CLIP joint space and obtained as a by-product of embedding extraction. On
⟦DATA:840⟧ Korean YouTube videos and ⟦DATA:70⟧ queries, late fusion of CLIP image and
multilingual text embeddings improves retrieval over text-only ⟦DATA⟧, and the gap is a
significant predictor of fusion-induced rank improvement ⟦DATA⟧. Our contribution is not a new
fusion technique but a metric that quantitatively explains *when* visual information helps,
providing a basis for adaptively extending a metadata retrieval platform with visual embeddings
only for high-gap videos.

**키워드 : 멀티모달 검색, CLIP, 의미 격차, 설명 가능 검색, 한국어 YouTube**

**Keywords : Multimodal retrieval, CLIP, Semantic gap, Explainable retrieval, Korean YouTube**

---

## Ⅰ. 서 론

영상 메타데이터를 수집·색인해 검색을 제공하는 플랫폼은 제목·설명·태그 등 **텍스트
메타데이터**에 의존한다. 반면 사용자가 실제 클릭 판단에 크게 활용하는 **썸네일의 시각
정보**는 검색에 거의 반영되지 않는다. 썸네일 같은 시각 채널을 텍스트와 결합(late fusion)하면
검색 성능이 향상된다는 보고는 많으나[3][6], 대부분 *"이미지를 넣었더니 좋아졌다"* 에서
멈추고 **그 향상이 어떤 영상에서 발생하는지**는 다루지 않는다. 이 구분은 실무적으로 중요하다.
시각 임베딩의 계산·저장은 비용이 들기 때문에, "모든 영상에 필요한가, 일부에만 필요한가"에
따라 메타데이터 검색 플랫폼의 색인 확장 설계가 달라진다.

시각 정보의 기여가 영상마다 다른 이유는 다음 논리에서 출발한다. 텍스트 메타데이터가 이미
내용을 충분히 담은 영상은 썸네일이 그 내용을 시각적으로 반복할 뿐이라 검색에 추가 정보를
거의 주지 못한다. 반대로 텍스트가 부족하거나 썸네일이 제목에 없는 내용을 담으면 시각
채널이 정보를 보완할 **여지**가 생긴다. 즉 썸네일이 제목과 다른 내용을 담을수록 시각 채널이
추가로 기여할 **가능성**이 커진다고 가정할 수 있다. 본 연구는 이 "제목–썸네일 의미 차이"를
정량화한 **시각–텍스트 의미 격차(gap)** 를 그 가능성의 **후보 지표**로 삼되, **그 차이가 실제
검색 기여로 이어지는지는 정의가 아니라 실험으로 검증**한다. gap이 크더라도 그 시각 정보가
특정 쿼리와 무관하면 도움이 안 될 수 있으므로, 본 연구는 gap을 "시각 정보의 유용성"과
동일시하지 않는다.

측정 방법으로 썸네일을 인물형·제품형 등으로 사람이 분류하는 대안은 (1) 경계가 주관적이고,
(2) 재현 불가능하며, (3) 라벨링 비용이 든다. 본 연구는 대신 검색 파이프라인이 이미 계산하는
임베딩만으로 gap을 **완전 자동·재현 가능한 연속 지표**로 산출한다.

본 연구의 연구 질문과 기여는 다음과 같다.

- **RQ1(조건, 주)**: 영상별 gap은 융합에 의한 검색 순위 개선을 **예측하는 유의한 변수인가?**
- **RQ2(성능, 부)**: CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 late fusion은 text-only 대비
  검색 성능을 향상시키는가?

기여는 (1) **라벨링이 필요 없는 gap 지표**, (2) **"시각 채널은 언제 도움이 되는가"에 대한
정량적 설명**, (3) gap 기반으로 시각 임베딩을 선별 적용하는 **메타데이터 검색 플랫폼의 적응형
확장** 근거 제시다. 즉 새로운 융합 기법이 아니라 **시각 정보의 기여 조건을 설명하는 지표**를
제안한다.

## Ⅱ. 관련 연구

CLIP[1]은 이미지·텍스트를 대조학습으로 공통 임베딩 공간에 정렬해, 결합 공간의 코사인
유사도를 정합성 지표로 표준화했다. CLIPScore[2]는 이 유사도를 캡션 품질 자동 평가에
사용했다. 본 연구는 **같은 계산식을 캡션 평가가 아니라 "검색 기여도 예측 변수"로 재해석**한다.
비디오–텍스트 검색에서는 프레임 집계 기반 방법[3]과 멀티레벨 융합[6]이 제안됐으나, 대규모
프레임·자막 중심이며 시각 채널의 **기여 조건**을 분석하지 않는다. 가장 가까운 선행 연구는
CLIP 썸네일·텍스트 late fusion으로 클릭베이트를 **분류**한 연구[7]이나, 과제가 분류이며 검색
랭킹의 기여 조건을 gap 같은 연속 지표로 설명하지 않는다. 다국어 텍스트 임베딩[4]은 한국어
처리의 기반이다. 요컨대 본 연구의 novelty는 요소 기술의 조합이 아니라, 정합성 지표(gap)를
**검색에서 시각 채널이 언제 기여하는지의 설명 변수**로 세운 데 있다.

## Ⅲ. 제안 방법

### 3.1 임베딩 추출

세 인코더를 역할별로 사용한다(표 1). 썸네일은 CLIP 이미지 인코더로, 검색용 텍스트(제목·
쿼리)는 다국어 문장 인코더로 인코딩한다. gap 계산과 시각 채널 비교는 **CLIP 이미지 공간에
정렬된 다국어 텍스트 인코더**를 쓴다. 검색 텍스트 채널은 한국어 품질이 좋은 별도 인코더를
쓰되, gap은 반드시 같은 결합 공간에서 계산해야 하므로 역할을 섞지 않는다.

**표 1. 사용 임베딩 인코더**

| 역할 | 모델 | 차원 |
|---|---|---|
| 썸네일 이미지 | CLIP ViT-B/32 | 512 |
| gap·시각채널용 텍스트 | 다국어 CLIP 텍스트(distillation 정렬) | 512 |
| 검색 텍스트 채널 | 다국어 문장 인코더(SBERT 계열) | 768 |

두 텍스트 인코더는 목적이 다르다. CLIP 계열 텍스트 인코더는 **이미지–텍스트 공동공간에서
gap과 시각 유사도를 계산**하기 위해, SBERT 계열 인코더는 **한국어 텍스트 간 검색 유사도**를
높이기 위해 사용한다.

### 3.2 시각–텍스트 의미 격차(gap)

영상 *i*의 gap은 CLIP 결합 공간에서 썸네일 임베딩과 제목 임베딩의 정합성(코사인)의 여집합으로
정의한다.

```
gap_i = 1 − cos( center(v_img_i), center(g_txt_i) )
```

gap은 **썸네일과 제목이 CLIP 공동 임베딩 공간에서 얼마나 비정렬(misaligned)되어 있는지를
나타내는 영상 수준 지표**다. 본 연구는 이 비정렬 정도가 검색에서 시각 정보의 추가 기여와
관련되는지를 실험으로 검증하며, gap을 그 자체로 "시각 정보의 유용성"으로 정의하지 않는다.

여기서 `center(·)`는 모달별 코퍼스 평균을 차감·재정규화하는 전처리다. CLIP 임베딩은
이방성(anisotropy)이 강해 raw 코사인이 좁은 대역에 뭉치므로[8][9], 모달별 mean-centering으로
이방성을 제거해 정합–비정합의 분리를 개선한다. centering은 성능이 아니라 **정합성 construct
validity**(제목이 자기 썸네일과 더 정합한가)를 근거로 실험 전 선택했으며, raw gap도 sensitivity로
병기한다. 지표는 라벨링 없이 전체 코퍼스에 자동 적용되며 임베딩 추출의 부산물이라 추가
비용이 없다.

### 3.3 Late Fusion 검색

세 검색 방식을 비교한다. 두 채널의 점수 스케일이 달라 쿼리별 min–max 정규화 후 가중합한다.

```
Text-only   : sim = cos(q_txt, d_txt)                 (검색 텍스트 인코더)
Visual-only : sim = cos(q_clip, d_img)                (텍스트 쿼리 ↔ 썸네일, 교차모달)
Late Fusion : score = α·norm(sim_text) + (1−α)·norm(sim_visual)
```

α는 결과를 보기 전 **대칭 equal-weight 지점 α=0.5** 를 primary로 고정하고, α∈{0.0,…,1.0}
grid는 sensitivity 곡선으로만 보고한다(최고 α를 "최적"으로 선택하지 않음). 융합은 성능 향상
자체가 목적이 아니라 **영상별 순위 개선폭(Δrank)을 산출해 gap과의 관계를 측정하기 위한
도구**다.

### 3.4 gap–순위개선 가설

정답지의 각 (쿼리 q, 관련 영상 v)에 대해 순위 개선폭을 정의한다.

```
Δrank(v,q) = rank_text(v|q) − rank_fusion(v|q)      (양수 = 융합이 순위 개선)
```

가설은 **gap이 큰 영상일수록 Δrank가 크다**(Spearman ρ>0)는 것이다. gap은 영상 수준
지표이므로, 분석은 영상당 Δrank를 median으로 집계해 `Spearman(gap, median Δrank)`로 본다.

## Ⅳ. 실험 설계

설계는 실험 전 사전 등록(pre-registration)으로 고정했다. 핵심만 요약한다.

### 4.1 평가 코퍼스

YouTube KR `assignable` 카테고리 **14개**를 주제 다양성 확보용 층화 틀로 사용해 **카테고리당
60편 × 14 = ⟦DATA:840⟧편**을 수집했다. ⚠️ categoryId는 **Sampling Anchor이지 semantic ground
truth가 아니며**, H1/H2 어디서도 레이블로 쓰지 않는다. 절차: 카테고리당 복수 seed로 `search`
수집 → `videos.list`의 categoryId로 사후 필터링, 정렬 3혼합(relevance·viewCount·date), 채널당
최대 5편, seed 간 round-robin. **Shorts 제외**(길이 실측 60초 초과만), 게시일 2025-01-01 이후.
이는 확률표본이 아니라 **gap 분산 확보용 카테고리 층화표본**이다.

### 4.2 평가 쿼리

쿼리는 연구자 창작이나 영상 텍스트에서 파생하지 않고(순환논리 회피), **YouTube 공개
자동완성(Suggest)** 에서 생성한다. 카테고리 term에 **초성(ㄱ/ㄴ/ㄷ…)을 이어 붙이는 초성
sweep**으로 후보를 수집한다(완성 음절 sweep은 특정 모음군에 편중되는 coverage 한계가 있어
초성 단위로 넓혔다). 이어 **사전 등록된 curation 규칙**으로 navigational(채널/프로그램)·category
mismatch·상품·서비스 쿼리를 제외하고(후보별 사유 전량 기록), eligible pool에서 **카테고리별
결정적 표집**(고정 해시 순 + content-filter)으로 **카테고리당 5개 × 14 = ⟦DATA:70⟧개**를 뽑는다.
쿼리는 retrieval 실험 전에 확정(freeze)하며 성능을 보고 바꾸지 않는다. 따라서 본 연구의 쿼리
집합은 사용자의 실제 검색 빈도를 추정하는 확률표본이 아니라, **플랫폼에서 관찰 가능한 검색
의도를 재현하기 위한 평가용 후보 집합**이다.

### 4.3 정답지(qrels) 구축

편향을 막기 위해 **Text-only ∪ Visual-only ∪ Late Fusion 각 Top10의 합집합**(pooling)을 후보
풀로 삼는다. 후보 (쿼리, 영상) 쌍을 **3인이 blind·독립**으로 3단계(2=관련/1=부분/0=무관)
라벨링하고, 최종 등급은 **세 판정의 median**으로 집계한다. 일치도는 Cohen κ(및 완전 3인 시
Fleiss κ)로 보고한다. 최종 qrels에서 관련(등급≥1) 문서가 0개인 쿼리는 채점 불가로
제외하며, **전체 쿼리 → zero-relevance 제거 → 최종 평가 쿼리 수를 카테고리별로 투명
보고**한다. 이는 독립 구성한 쿼리와 코퍼스의 정합성에 대한 사후 진단 자료이기도 하다.

### 4.4 평가 지표 및 통계 검정

- **검색 성능(RQ2)**: MRR@10, NDCG@10, Recall@10.
- **gap 예측력(RQ1)**: Spearman ρ(gap, median Δrank), 효과 크기 Cohen's d.
- **H1 검정**: Text-only 대 Fusion(α=0.5)의 쿼리별 reciprocal rank@10에 **paired Wilcoxon
  signed-rank test**(p<0.05) **그리고** 전체 MRR@10 차 > +0.05. RR@10이 이산·비정규 분포라
  비모수 검정을 쓴다.
- **H2 검정**: 영상당 median Δrank로 집계해 `Spearman(gap, median Δrank)` 유의성(ρ>0, p<0.05)을
  본다(Δrank는 영상–쿼리 쌍 구조이고 한 영상에 여러 쿼리가 붙으므로 영상당 median 집계로
  독립성을 확보한다). **부트스트랩 95% CI**와 **카테고리 내 stratified 상관**, **raw vs centered
  gap sensitivity**를 병기한다. 카테고리 교란을 통제하는 클러스터-robust 회귀와 MDES는 필요 시
  추가 분석으로 제시한다.

## Ⅴ. 결과 ⟪실험 후 작성⟫

### 5.1 전체 성능 (RQ2)

**표 2. 검색 성능**

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|---|---|---|---|
| Text-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| Visual-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| **Late Fusion (α=0.5)** | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |

Wilcoxon(Fusion vs Text, 쿼리별 RR@10): ⟦DATA: stat, p⟧ (부트스트랩 95% CI ⟦DATA⟧).

### 5.2 gap의 순위 개선 예측력 (RQ1)

Spearman ρ(gap, 영상당 median Δrank) = ⟦DATA⟧ (95% CI ⟦DATA⟧, p=⟦DATA⟧). raw gap
sensitivity ⟦DATA⟧, 카테고리 stratified 양(+)상관 비율 ⟦DATA⟧, 회귀 gap 계수 ⟦DATA⟧.
gap 상·하위군 평균 Δrank와 Cohen's d ⟦DATA⟧. (그림 1: gap 대 median Δrank 산점도.)

### 5.3 조건별 분석

쿼리 유형·길이·gap 수준별 융합 개선폭 ⟦DATA⟧. gap 높음에도 개선 없는 반례를 함께 제시한다.

## Ⅵ. 논 의

gap은 "높을수록 반드시 도움"이 아니라 "시각 정보의 잠재 기여 **가능성**을 나타내는 예측
후보 변수"로 서술한다(반례 — gap이 높아도 개선이 없는 경우 — 를 §5.3에 함께 제시하는 것과
일관된다). 실무적 함의는 **적응형 검색**이다. 만약 낮은 gap 영상에서 시각 임베딩의 기여가
작음이 확인된다면, 그런 영상에는 시각 임베딩 계산·저장을 생략하고 높은 영상에만 선별
적용하여 **메타데이터 검색 플랫폼의 색인을 비용 효율적으로 확장**하는 방향을 탐색할 수 있다.
즉 본 지표는 "모든 영상에 시각 임베딩을 넣을 것인가"라는 색인 설계 결정에 정량적 검토
기준을 제공한다.

**한계.** (1) 시각 인코더는 OCR을 수행하지 않아 **썸네일 내 한국어 자막 텍스트를 판독하지
못하므로**, 시각 신호와 gap은 썸네일의 회화적 장면에 국한된다. (2) gap은 정렬된 다국어 CLIP
인코더의 한국어 품질과 mean-centering 전처리에 의존한다. (3) 평가 코퍼스는 확률표본이 아닌
카테고리 층화표본이다. (4) 상관은 인과가 아니다.

## Ⅶ. 결 론

본 연구는 멀티모달 영상 검색에서 시각 정보의 기여 조건을, 라벨링 없이 자동 계산되는 시각–
텍스트 의미 격차(gap)로 정량화하고, 이 격차가 융합에 의한 순위 개선과 관련되는지를 실증적으로
검증하는 틀을 제시했다 ⟦DATA⟧. gap은 시각 임베딩을 **선택적으로 적용할 가능성을 탐색하는
기준**으로 활용될 수 있으며, 낮은 gap 영상에서 시각 임베딩 제거 시 성능 손실이 작음을 확인하면
비용 효율적 색인 확장의 근거가 된다. 향후 OCR-증강 썸네일로의 gap 확장과 적응형 색인의 실제
비용–성능 트레이드오프 측정을 계획한다.

## Acknowledgement

이 논문은 [과제 지원 문구]에 의함.

## References

[1] A. Radford et al., "Learning transferable visual models from natural language supervision,"
in *Proc. ICML*, pp. 8748–8763, 2021.

[2] J. Hessel, A. Holtzman, M. Forbes, R. L. Bras, and Y. Choi, "CLIPScore: A reference-free
evaluation metric for image captioning," in *Proc. EMNLP*, pp. 7514–7528, 2021.

[3] H. Fang, P. Xiong, L. Xu, and Y. Chen, "CLIP2Video: Mastering video-text retrieval via
image CLIP," *arXiv:2106.11097*, 2021.

[4] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese
BERT-networks," in *Proc. EMNLP-IJCNLP*, pp. 3982–3992, 2019.

[5] J. Li, D. Li, C. Xiong, and S. Hoi, "BLIP: Bootstrapping language-image pre-training for
unified vision-language understanding and generation," in *Proc. ICML*, 2022.

[6] Z. Gao et al., "M2HF: Multi-level multi-modal hybrid fusion for text-video retrieval,"
*arXiv:2208.07664*, 2022.

[7] [저자 미상], "A multi-modal LLM approach for detecting misleading YouTube thumbnails,"
*arXiv:2509.04714*, 2025. ⟦서지 확인 필요⟧

[8] J. Mu and P. Viswanath, "All-but-the-top: Simple and effective postprocessing for word
representations," in *Proc. ICLR*, 2018.

[9] K. Ethayarajh, "How contextual are contextualized word representations? Comparing the
geometry of BERT, ELMo, and GPT-2 embeddings," in *Proc. EMNLP-IJCNLP*, pp. 55–65, 2019.
