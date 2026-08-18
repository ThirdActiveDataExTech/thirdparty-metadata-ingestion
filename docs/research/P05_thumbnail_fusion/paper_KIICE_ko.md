<!-- 한국정보통신학회 춘·추계 종합학술대회 제출용 초안 (KIICE format).
     본문 2단·국문 함초롱바탕 등 조판은 HWP 양식에서 적용. 이 파일은 내용 원고.
     ⟦DATA⟧ = 라벨링·실험 후 실수치로 교체. 저자/소속/과제문구는 [ ] 플레이스홀더. -->

# 영상 검색에서 썸네일–제목 의미 격차와 시각 정보의 기여 분석

**Thumbnail–Title Semantic Gap and the Contribution of Visual Information in Video Retrieval**

<!-- 제목 C안 확정(2026-08-15). 주 표기 = 썸네일–제목 의미 격차(thumbnail–title semantic gap);
     넓은 개념명 '시각–텍스트 의미 격차(visual–text semantic gap)'는 초록 첫 등장에서 1회 병기.
     실증 도메인(한국어 YouTube)은 초록·본문·한계에 명시. -->

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
규명되지 않았다. 본 연구는 이 조건을 **라벨링 없이 자동 계산되는 연속 지표**인 **썸네일–제목
의미 격차**(넓게는 시각–텍스트 의미 격차; visual–text semantic gap, 이하 gap)로 특성화한다.
gap은 CLIP 결합 공간에서 썸네일과 제목이 얼마나 비정렬(misaligned)되어 있는지를 나타내는
영상 수준 지표로, 정합성의 여집합으로 정의되며 임베딩 추출의 부산물로 얻어진다. 한국어 YouTube 영상 ⟦DATA:840⟧편과 검색어
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
label-free metric—the *thumbnail–title semantic gap* (broadly, a visual–text semantic gap)—
defined as the complement of thumbnail–title alignment in the CLIP joint space and obtained as
a by-product of embedding extraction. On
⟦DATA:840⟧ Korean YouTube videos and ⟦DATA:70⟧ queries, we empirically examine whether late
fusion of CLIP image and multilingual text embeddings improves retrieval over text-only, and
whether the gap is associated with fusion-induced rank improvement ⟦DATA⟧. Our contribution is
not a new fusion technique but a metric and analysis for characterizing *when* visual
information may help, providing a basis for exploring the adaptive extension of a metadata
retrieval platform with visual embeddings for high-gap videos.

**키워드 : 멀티모달 검색, CLIP, 썸네일–제목 의미 격차, 썸네일, 한국어 YouTube**

**Keywords : Multimodal retrieval, CLIP, Thumbnail–title semantic gap, Thumbnail, Korean YouTube**

---

## Ⅰ. 서 론

영상 메타데이터를 수집·색인해 검색을 제공하는 플랫폼은 제목·설명·태그 등 **텍스트
메타데이터**에 의존한다. 반면 사용자가 실제 클릭 판단에 크게 활용하는 **썸네일의 시각
정보**는 검색에 거의 반영되지 않는다. 썸네일 같은 시각 채널을 텍스트와 결합(late fusion)하면
검색 성능이 향상된다는 보고는 많으나[1][2], 대부분 *"이미지를 넣었더니 좋아졌다"* 에서
멈추고 **그 향상이 어떤 영상에서 발생하는지**는 다루지 않는다. 이 구분은 실무적으로 중요하다.
시각 임베딩의 계산·저장은 비용이 들기 때문에, "모든 영상에 필요한가, 일부에만 필요한가"에
따라 메타데이터 검색 플랫폼의 색인 확장 설계가 달라진다.

시각 정보의 기여가 영상마다 다른 이유는 다음 논리에서 출발한다. 텍스트 메타데이터가 이미
내용을 충분히 담은 영상은 썸네일이 그 내용을 시각적으로 반복할 뿐이라 검색에 추가 정보를
거의 주지 못한다. 반대로 텍스트가 부족하거나 썸네일이 제목에 없는 내용을 담으면 시각
채널이 정보를 보완할 **여지**가 생긴다. 즉 썸네일이 제목과 다른 내용을 담을수록 시각 채널이
추가로 기여할 **가능성**이 커진다고 가정할 수 있다. 본 연구는 이 "썸네일–제목 의미 차이"를
정량화한 **썸네일–제목 의미 격차(gap)** 를 그 가능성의 **후보 지표**로 삼되, **그 차이가 실제
검색 기여로 이어지는지는 정의가 아니라 실험으로 검증**한다. gap이 크더라도 그 시각 정보가
특정 쿼리와 무관하면 도움이 안 될 수 있으므로, 본 연구는 gap을 "시각 정보의 유용성"과
동일시하지 않는다.

측정 방법으로 썸네일을 인물형·제품형 등으로 사람이 분류하는 대안은 **분류 기준의 설계와
라벨링 비용**이 필요하며, 경계 사례에서 **주관이 개입**될 수 있다. 본 연구는 대신 검색
파이프라인이 이미 계산하는 임베딩만으로 gap을 **추가 라벨링 없이 자동·재현 가능한 연속
지표**로 산출한다.

본 연구의 연구 질문과 기여는 다음과 같다.

- **RQ1(조건, 주)**: 영상별 gap이 클수록 융합에 의한 검색 순위 개선(Δrank)이 큰가?
- **RQ2(성능, 부)**: CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 late fusion은 text-only 대비
  검색 성능을 향상시키는가?

기여는 (1) **라벨링이 필요 없는 썸네일–제목 의미 격차(gap) 지표의 정의 및 자동 계산**,
(2) **gap과 융합에 의한 검색 순위 개선의 관계 분석**(시각 정보가 "언제" 검색에 기여하는가),
(3) **한국어 YouTube 환경에서의 실증**이다. 즉 새로운 융합 기법이 아니라 **시각 정보의 기여
조건을 다루는 지표와 분석 틀**을 제안한다. gap 기반으로 시각 임베딩을 선별 적용하는 등의
실무적 활용 가능성은 Ⅵ.4에서 논의한다.

## Ⅱ. 관련 연구

### 2.1 멀티모달 검색

CLIP[3]은 이미지·텍스트를 대조학습으로 공통 임베딩 공간에 정렬해, 결합 공간의 코사인
유사도를 정합성의 표준 지표로 확립했다. 이를 비디오–텍스트 검색에 적용한 프레임 집계 기반
방법[1]과 멀티레벨 융합[2]이 제안됐으나, 대규모 프레임·자막 중심이며 시각 채널의 **기여
조건**은 분석하지 않는다. 한국어 텍스트 검색은 다국어 문장 임베딩[4]을 기반으로 한다.

### 2.2 이미지–텍스트 정합성 측정

CLIPScore[5]는 CLIP 유사도를 캡션 품질의 자동 평가에 사용했고, BLIP[6] 등 통합 비전–언어
모델도 정합성 표현을 제공한다. 본 연구는 **같은 정합성 계산을 캡션 평가가 아니라 검색
기여도의 조건 변수로 재해석**한다.

### 2.3 썸네일과 쿼리 적응적 모달 활용

썸네일을 직접 다룬 연구로는 **멀티모달 LLM**(영상→텍스트 설명·썸네일·자막을 통합)으로 **오도성
(misleading) 썸네일을 탐지**한 연구[7]가 있으나, 과제가 오도성 판정(분류)이며 임베딩 기반 검색
랭킹에서 시각 정보의 **기여 조건**을 연속 지표로 설명하지는 않는다.

한편 검색에서 **모달을 언제 활용할지**를 다룬 계열도 있다. 쿼리별로 다중 수준 표현의 유효성을
추정해 late fusion 가중을 조정하는 방법[8]과, 모달 간 점수 일치(cross-modal agreement)로 각
쿼리에서 활용할 모달을 능동 선택하는 방법[9]이 그것이다. 다만 이들은 검색 **성능을 높이기 위한
적응 가중·모달 선택 메커니즘**을 제안하는 데 초점이 있으며, 정합성의 차이 자체를 시각 기여의
조건 변수로 **기술·분석**하지는 않는다.

### 2.4 연구 공백

요컨대 기존 연구는 주로 **검색 성능**이나 **정합성 자체**를 다루거나[1–6], 모달 활용 여부를
**성능 최적화 메커니즘**으로 조정한다[8,9]. 반면 **정합성의 차이(gap)가 검색에서 시각 채널의
기여 조건으로 작동하는지를 연속 지표로 기술하는 분석**은 상대적으로 덜 다루어진 문제다. 본
연구는 이 문제를 대상으로, 새로운 융합 기법이 아니라 **고정 융합 위에서 gap과 시각 기여의 연관을
분석**한다.

## Ⅲ. 제안 방법

### 3.1 임베딩 추출

세 인코더를 역할별로 사용한다(표 1). 썸네일은 CLIP 이미지 인코더로, 검색용 텍스트(제목·
쿼리)는 다국어 문장 인코더로 인코딩한다. gap 계산과 시각 채널 비교는 **CLIP 이미지 공간에
정렬된 다국어 텍스트 인코더**를 쓴다. 검색 텍스트 채널은 한국어 품질이 좋은 별도 인코더를
쓰되, gap은 반드시 같은 결합 공간에서 계산해야 하므로 역할을 섞지 않는다.

**표 1. 사용 임베딩 인코더**

| 역할 | 모델(체크포인트) | 차원 |
|---|---|---|
| 썸네일 이미지 | `sentence-transformers/clip-ViT-B-32` | 512 |
| gap·시각채널용 텍스트 | `sentence-transformers/clip-ViT-B-32-multilingual-v1` | 512 |
| 검색 텍스트 채널 | `paraphrase-multilingual-mpnet-base-v2` | 768 |

두 텍스트 인코더는 목적이 다르다. CLIP 계열 텍스트 인코더는 **이미지–텍스트 공동공간에서
gap과 시각 유사도를 계산**하기 위해, mpnet 계열 인코더는 **한국어 텍스트 간 검색 유사도**를
높이기 위해 사용한다. **구현 세부(재현용)**: 모든 임베딩은 L2 정규화하며, 유사도는 코사인,
채널 결합 전 쿼리별 min–max 정규화를 적용한다. 썸네일 이미지 전처리(리사이즈·crop)는 CLIP
기본 설정을 따르고, 텍스트는 원문 그대로(추가 형태소 처리 없이) 인코딩한다. 라이브러리·버전과
전체 하이퍼파라미터는 부록/공개 저장소에 명시한다.

### 3.2 썸네일–제목 의미 격차(gap)

영상 *i*의 gap은 CLIP 결합 공간에서 썸네일 임베딩과 제목 임베딩의 정합성(코사인)의 여집합으로
정의한다.

```
gap_i = 1 − cos( center(v_img_i), center(g_txt_i) )
```

gap은 **썸네일과 제목이 CLIP 공동 임베딩 공간에서 얼마나 비정렬(misaligned)되어 있는지를
나타내는 영상 수준 지표**다. 본 연구는 이 비정렬 정도가 검색에서 시각 정보의 추가 기여와
관련되는지를 실험으로 검증하며, gap을 그 자체로 "시각 정보의 유용성"으로 정의하지 않는다.

여기서 `center(·)`는 모달별 코퍼스 평균을 차감·재정규화하는 전처리다. CLIP 등 대조학습
임베딩은 이방성(anisotropy)과 modality gap이 강해 raw 코사인이 좁은 대역에 뭉치므로[10][11][12],
모달별 mean-centering으로 이 성분을 제거해 정합–비정합의 분리를 개선한다. **centering 선택의
근거(엄밀화)**: (1) 어떤 retrieval 점수·Δrank·qrels도 보기 전에 centering을 고정했다. (2) 판단
기준은 **자기매칭(self-matching) construct validity** — 각 제목이 무작위 썸네일보다 자기 자신의
썸네일과 더 정합한가(self-match rate) — 이며, **성능 지표가 아니다**. (3) 이 판단에 qrels·Δrank는
일절 사용하지 않았다. 따라서 "데이터를 보고 잘 분리되는 전처리를 고른 것"이 아니다. raw gap도
sensitivity로 병기한다(§4.4). 지표는 라벨링 없이 전체 코퍼스에 자동 적용되며 임베딩 추출의
부산물이라 추가 비용이 없다.

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
truth가 아니며**, 본 연구의 어느 분석에서도 레이블로 쓰지 않는다. 절차: 카테고리당 복수 seed로 `search`
수집 → `videos.list`의 categoryId로 사후 필터링, 정렬 3혼합(relevance·viewCount·date), 채널당
최대 5편, seed 간 round-robin. **60초 초과 영상만 수집**(초단편 클립 배제), 게시일 2025-01-01
이후. 이는 확률표본이 아니라 **gap 분산 확보용 카테고리 층화표본**이다. 공식 API에 Short 여부
필드가 없어, 각 영상을 `youtube.com/shorts/{id}` 접근의 리다이렉트 여부로 **Shorts와 일반
영상을 사후 분리**했다(is_short; 코퍼스의 12.5%가 Short). is_short는 유병률 보고와 non-Shorts
민감도 분석에 사용한다(§4.4·§6.5).

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

지표는 검색 성능(RQ2)에 MRR@10·NDCG@10·Recall@10, gap–개선 연관(RQ1)에 Spearman ρ(gap,
median Δrank)와 효과 크기 Cohen's d를 쓴다. 본 논문은 연구 질문 RQ1·RQ2로 명칭을 통일하며,
각각을 아래 검정으로 확인한다.

- **RQ2 검정(융합 효과)**: Text-only 대 Fusion(α=0.5)의 쿼리별 reciprocal rank@10에 **paired
  Wilcoxon signed-rank test**(p<0.05) **그리고** 전체 MRR@10 차 > +0.05. RR@10이 이산·비정규
  분포라 비모수 검정을 쓴다.
- **RQ1 검정(gap–개선 연관)**: 영상당 median Δrank로 집계해 `Spearman(gap, median Δrank)`의
  유의성(ρ>0, p<0.05)을 **상관 수준**에서 본다(Δrank는 영상–쿼리 쌍 구조이고 한 영상에 여러
  쿼리가 붙으므로 영상당 median 집계로 독립성을 확보한다). **부트스트랩 95% CI**와 **카테고리
  내 stratified 상관**, **raw vs centered gap sensitivity**를 병기한다. 카테고리 교란을 통제하는
  클러스터-robust 회귀와 MDES는 필요 시 추가 분석으로 제시한다. 상관 유의성은 예측력의 직접
  증거가 아니므로, 본 연구는 결과를 "예측"이 아니라 "연관"으로 해석한다.
- **Short 강건성**: 코퍼스의 12.5%가 Short이므로, Short 유병률을 보고하고 **Short 제외
  부분표본(non-Shorts)으로 H1·H2(RQ1·RQ2)를 재실행**해 결과가 Short 포함에 좌우되지 않음을
  확인한다. Short 수가 충분하면 Short/일반 서브그룹 비교를 탐색적으로 병기한다.

## Ⅴ. 결과 ⟪실험 후 작성⟫

### 5.1 전체 성능 (RQ2)

**표 2. 검색 성능**

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|---|---|---|---|
| Text-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| Visual-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| **Late Fusion (α=0.5)** | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |

Wilcoxon(Fusion vs Text, 쿼리별 RR@10): ⟦DATA: stat, p⟧ (부트스트랩 95% CI ⟦DATA⟧).

### 5.2 gap과 순위 개선의 연관 (RQ1)

Spearman ρ(gap, 영상당 median Δrank) = ⟦DATA⟧ (95% CI ⟦DATA⟧, p=⟦DATA⟧). raw gap
sensitivity ⟦DATA⟧, 카테고리 stratified 양(+)상관 비율 ⟦DATA⟧, 회귀 gap 계수 ⟦DATA⟧.
gap 상·하위군 평균 Δrank와 Cohen's d ⟦DATA⟧. (그림 1: gap 대 median Δrank 산점도.)

### 5.3 조건별 분석

쿼리 유형·길이·gap 수준별 융합 개선폭 ⟦DATA⟧. gap 높음에도 개선 없는 반례를 함께 제시한다.

## Ⅵ. 논 의

### 6.1 융합은 실제로 효과가 있었는가 (RQ2)

전체 성능(§5.1) 관점에서 late fusion이 text-only 대비 검색을 개선했는지를 논한다 ⟦DATA⟧.
설령 평균 개선이 크지 않더라도, 본 연구의 초점은 "평균 성능"이 아니라 "개선이 나타나는
조건"이므로 RQ1이 핵심이다.

### 6.2 gap이 그 효과를 설명했는가 (RQ1)

§5.2의 gap–Δrank 관계를 논한다 ⟦DATA⟧. gap이 클수록 융합에 의한 순위 개선이 큰 경향이
관찰된다면, 시각 정보의 추가 기여는 **균일하지 않고 제목–썸네일의 의미 격차와 관련**된다는
것을 시사한다. 다만 이는 상관 관계이며 인과가 아니다.

### 6.3 gap이 높은데도 개선되지 않는 영상 (반례)

§5.3의 반례를 논한다. gap이 높다는 것은 썸네일이 제목과 다른 정보를 담는다는 뜻이지, 그
정보가 특정 쿼리에 유용함을 보장하지 않는다. 썸네일과 제목이 모두 쿼리와 약하게만 관련되면
gap이 높아도 개선이 없을 수 있다. 이는 gap을 결정적 규칙이 아니라 순위 개선과 **연관을 보이는
변수**(상관 수준)로 서술하는 근거이며, 반례를 숨기지 않는 것과 일관된다. 본 연구의 primary
분석은 Spearman 상관이므로 "예측"이 아니라 "연관"으로 해석함을 명시한다.

### 6.4 실무적 함의: 시각 임베딩의 선별 적용

낮은 gap 영상에서 시각 임베딩의 기여가 작음이 확인된다면, 그런 영상에는 시각 임베딩 계산·
저장을 생략하고 높은 gap 영상에만 선별 적용하여 **메타데이터 검색 플랫폼의 색인을 비용
효율적으로 확장**하는 방향을 탐색할 수 있다. 즉 gap은 "모든 영상에 시각 임베딩을 넣을
것인가"라는 색인 설계 결정에 정량적 검토 기준을 제공한다. 다만 실제 선별(임계값·분류 성능)의
검증은 본 연구 범위 밖이며 향후 과제다.

### 6.5 한계

(1) 시각 인코더는 OCR을 수행하지 않아 **썸네일 내 한국어 자막 텍스트를 판독하지 못하므로**,
시각 신호와 gap은 썸네일의 회화적 장면에 국한된다. (2) gap은 정렬된 다국어 CLIP 인코더의
한국어 품질과 mean-centering 전처리에 의존한다. (3) 평가 코퍼스는 확률표본이 아닌 카테고리
층화표본이다(대표성 주장은 그 범위로 한정). (4) 코퍼스는 short-form을 **12.5% 포함**한다;
`/shorts` 판별로 is_short를 라벨해 유병률·non-Shorts 민감도로 통제하나(§4.4), Short의 썸네일
(세로 자동 프레임)은 일반 썸네일과 특성이 달라 gap 해석에 영향을 줄 수 있다. (5) primary 분석은
**상관**이며 인과가 아니다.

## Ⅶ. 결 론

본 연구는 멀티모달 영상 검색에서 시각 정보의 기여 조건을, 라벨링 없이 자동 계산되는 시각–
텍스트 의미 격차(gap)로 정량화하고, 이 격차가 융합에 의한 순위 개선과 관련되는지를 실증적으로
검증하는 틀을 제시했다 ⟦DATA⟧. gap은 시각 임베딩을 **선택적으로 적용할 가능성을 탐색하는
기준**으로 활용될 수 있으며, 낮은 gap 영상에서 시각 임베딩 제거 시 성능 손실이 작음을 확인하면
비용 효율적 색인 확장의 근거가 된다. 향후 OCR-증강 썸네일로의 gap 확장과 적응형 색인의 실제
비용–성능 트레이드오프 측정을 계획한다.

## Acknowledgement

이 논문은 2024년도 정부(과학기술정보통신부)의 재원으로 정보통신기획평가원의 지원을 받아
수행된 연구임 (No.RS-2024-00340834, 써드파티 데이터의 활용성 증대를 위한 액티브 메타데이터
기반 능동형 데이터 확장 기술 개발).

This work was supported by Institute for Information & communications Technology
Promotion(IITP) grant funded by the Korea government(MSIT) (No.RS-2024-00340834, Development
active metadata-driven active data expansion technology to increase third-party data
utilization).

## References

[1] H. Fang, P. Xiong, L. Xu, and Y. Chen, "CLIP2Video: Mastering video-text retrieval via
image CLIP," *arXiv:2106.11097*, 2021.

[2] Z. Gao et al., "M2HF: Multi-level multi-modal hybrid fusion for text-video retrieval,"
*arXiv:2208.07664*, 2022.

[3] A. Radford et al., "Learning transferable visual models from natural language supervision,"
in *Proc. ICML*, pp. 8748–8763, 2021.

[4] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese
BERT-networks," in *Proc. EMNLP-IJCNLP*, pp. 3982–3992, 2019.

[5] J. Hessel, A. Holtzman, M. Forbes, R. L. Bras, and Y. Choi, "CLIPScore: A reference-free
evaluation metric for image captioning," in *Proc. EMNLP*, pp. 7514–7528, 2021.

[6] J. Li, D. Li, C. Xiong, and S. Hoi, "BLIP: Bootstrapping language-image pre-training for
unified vision-language understanding and generation," in *Proc. ICML*, 2022.

[7] W. Naveed, Z. A. Uzmi, and Z. A. Qazi, "ThumbnailTruth: A multi-modal LLM approach for
detecting misleading YouTube thumbnails across diverse cultural settings," *arXiv:2509.04714*,
2025.

[8] W. Ma, Q. Chen, F. Liu, T. Zhou, and Z. Cai, "Query-adaptive late fusion for hierarchical
fine-grained video-text retrieval," *IEEE Trans. Neural Netw. Learn. Syst.*, 2022.

[9] E. Loweimi, M. Qian, K. Knill, et al., "To be multimodal or not to be: Query-adaptive
audio-visual person retrieval via active modality detection," in *Proc. INTERSPEECH*, 2026.

[10] J. Mu and P. Viswanath, "All-but-the-top: Simple and effective postprocessing for word
representations," in *Proc. ICLR*, 2018.

[11] K. Ethayarajh, "How contextual are contextualized word representations? Comparing the
geometry of BERT, ELMo, and GPT-2 embeddings," in *Proc. EMNLP-IJCNLP*, pp. 55–65, 2019.

[12] W. Liang, Y. Zhang, Y. Kwon, S. Yeung, and J. Zou, "Mind the gap: Understanding the
modality gap in multi-modal contrastive representation learning," in *Proc. NeurIPS*, 2022.
