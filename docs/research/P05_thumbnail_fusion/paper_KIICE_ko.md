<!-- 한국정보통신학회 춘·추계 종합학술대회 제출용 초안 (KIICE format).
     본문 2단·국문 함초롱바탕 등 조판은 HWP 양식에서 적용. 이 파일은 내용 원고.
     저자/소속/과제문구만 [ ] 플레이스홀더. 실험 수치·그림 모두 확정 반영됨(2026-08-27).
     남은 것 = HWP 붙여넣기용 txt 재동기화. -->

# 영상 검색에서 썸네일 시각정보의 검색 기여 분석: 텍스트–시각 융합과 의미 격차를 중심으로

**Analyzing the Retrieval Contribution of Thumbnail Visual Information in Video Search: Text–Visual Fusion and the Semantic Gap**

<!-- 제목 1안 확정(2026-08-27). 질문형·"제안" 프레이밍 제거, 도메인 일반화(영상 검색);
     실증 도메인(한국어 YouTube)은 초록·본문 §4에 명시. -->

[저자1] · [저자2]<sup>*</sup>  
[소속1] · [소속2]  
[Author1] · [Author2]<sup>*</sup>  
[Affiliation1] · [Affiliation2]  
E-mail : [email1] / [email2]

---

## 요 약

영상 메타데이터 검색은 제목·설명 등 텍스트에 주로 의존하며, 썸네일의 시각 정보는 거의
활용되지 않는다. 본 연구는 한국어 YouTube 영상 840편과 검색어 70개를 대상으로, CLIP 이미지
임베딩과 다국어 텍스트 임베딩의 late fusion이 텍스트 단독 검색을 개선하는지, 그리고 시각
정보의 기여를 **시각–텍스트 의미 격차**(썸네일–제목 기준; visual–text semantic gap, 이하 gap)로
설명할 수 있는지를 분석한다. gap은 CLIP 공동 임베딩 공간에서 mean-centering 후 썸네일–제목
코사인 유사도를 역변환한(1−cos) 영상 수준의 비정렬 지표로, 별도의 라벨링 없이 임베딩 추출
과정에서 산출된다. 실험 결과, 썸네일 단독 검색은 텍스트보다 낮았고 동일가중 융합은 텍스트 대비 유의한
개선을 보이지 않았으며, 관련 영상의 순위 변화는 상위보다 깊은 순위에서 두드러졌다. 탐색적
분석에서는 시각을 낮은 가중으로 결합할 때 일부 지표의 개선 신호가 관찰되었으나 그 효과는
카테고리에 따라 이질적이었다. 또한 사전등록된 gap–순위변화 관계는 유의하지 않았고, 관찰된 단순
상관은 카테고리 수준의 이질성에 영향을 받았다. 요컨대 썸네일은 텍스트 검색을 대체할 강한 신호는
아니었으나 보조적으로 검색 결과의 순위 구성을 변화시키는 양상이 관찰되었으며, 그 기여를 단일
의미 격차 지표만으로 설명하기에는 한계가 있었다.

## ABSTRACT

Video metadata retrieval relies mostly on textual fields such as titles, leaving the visual
information in thumbnails largely unused. On 840 Korean YouTube videos and 70 queries, we analyze
whether late fusion of CLIP image and multilingual text embeddings improves retrieval over
text-only, and whether the contribution of visual information can be explained by a visual–text
semantic gap (thumbnail–title), defined as an inverse transform (1−cos) of the mean-centered
thumbnail–title cosine similarity in the CLIP joint space and obtained label-free as a by-product
of embedding extraction. Thumbnail-only retrieval was weaker than text, and equal-weight fusion
did not significantly improve over text-only; changes in the ranks of relevant videos were more
pronounced at deeper ranks than in the top results. An exploratory analysis showed marginal
improvements when visual information was combined at a low weight, but the effect was heterogeneous
across categories. Moreover, the preregistered association between the gap and rank change was not
significant, and the observed raw association was influenced by category-level heterogeneity. In
sum, thumbnails were not a strong signal capable of replacing text retrieval, yet were observed to
auxiliarily reshape the rank composition of results, and a single semantic-gap metric was
insufficient to characterize their retrieval contribution.

**키워드** : Multimodal retrieval, CLIP, Thumbnail–title semantic gap, Thumbnail, Korean YouTube

---

## Ⅰ. 서 론

영상 메타데이터를 수집·색인해 검색을 제공하는 플랫폼은 제목·설명·태그 등 **텍스트
메타데이터**에 주로 의존하며, 사용자가 클릭 판단에 크게 활용하는 **썸네일의 시각 정보**는
검색에 거의 반영되지 않는다. 시각 채널을 텍스트와 결합해 검색 성능을 높이는
접근이 보고돼 왔으나[1][2], 그 개선이 **모든 영상에서 균일한지, 특정 조건에서만 나타나는지**,
나아가 시각 정보가 실제로 검색에 기여하는지에 대한 분석은 제한적이다. 시각 임베딩의 계산·
저장에는 비용이 들기 때문에, 시각 정보의 검색 기여 여부와 그 조건을 이해하는 것은 메타데이터
검색 플랫폼의 색인 설계에도 함의를 갖는다. 본 연구는 이 문제를 한국어 YouTube 검색 환경에서
실증적으로 분석한다.

시각 정보의 기여가 영상마다 다른 이유는 다음 논리에서 출발한다. 텍스트 메타데이터가 이미
내용을 충분히 담은 영상은 썸네일이 그 내용을 시각적으로 반복할 뿐이라 검색에 추가 정보를
거의 주지 못한다. 반대로 텍스트가 부족하거나 썸네일이 제목에 없는 내용을 담으면 시각
채널이 정보를 보완할 **여지**가 생긴다. 즉 썸네일과 제목의 의미적 차이가 클수록 썸네일이
제목과 **중복되지 않는 시각 정보를 포함할 가능성**이 있다. 본 연구는 이 "썸네일–제목 의미
차이"를 정량화한 **썸네일–제목 의미 격차(gap)** 를 후보 지표로 삼아, **이 차이가 실제 검색
성능의 추가 개선과 관련되는지를 실험으로 검증**한다. gap이 크더라도 그 시각 정보가
특정 쿼리와 무관하면 도움이 안 될 수 있으므로, 본 연구는 gap을 "시각 정보의 유용성"과
동일시하지 않는다.

측정 방법으로 썸네일을 인물형·제품형 등으로 사람이 분류하는 대안은 **분류 기준의 설계와
라벨링 비용**이 필요하며, 경계 사례에서 **주관이 개입**될 수 있다. 본 연구는 대신 검색
파이프라인이 이미 계산하는 임베딩만으로 gap을 **추가 라벨링 없이 자동·재현 가능한 연속
지표**로 산출한다.

본 연구의 연구 질문과 기여는 다음과 같다.

- **RQ1(조건)**: 영상별 gap이 클수록 융합에 의한 검색 순위 개선(Δrank)이 큰가?
- **RQ2(성능)**: CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 late fusion은 text-only 대비
  검색 성능을 향상시키는가?

기여는 (1) **라벨링이 필요 없는 썸네일–제목 의미 격차(gap) 지표의 정의 및 자동 계산**,
(2) **텍스트–시각 융합의 검색 효과와 gap–순위변화 관계에 대한 분석 틀**, (3) **한국어 YouTube
환경에서의 실증**이다. 즉 새로운 융합 기법이 아니라, 시각 정보의 검색 기여와 그 설명 변수를
다루는 분석을 제시한다. 시각 정보의 검색 활용에 대한 실무적 함의는 §6.4에서 논의한다.

## Ⅱ. 관련 연구

### 2.1 멀티모달 검색

CLIP[3]은 이미지·텍스트를 대조학습으로 공통 임베딩 공간에 정렬하여, 두 모달리티 간 유사도를
코사인 유사도로 측정할 수 있게 한다. 이를 비디오–텍스트 검색에 적용한 프레임 집계 기반
방법[1]과 멀티모달 하이브리드 융합[2]이 제안됐으나, 대규모 프레임·자막 중심이며 시각 채널의 **기여
조건**은 분석하지 않는다. 한국어 텍스트 검색에는 문장 임베딩 기법[4]에 기반한 다국어 모델을 사용한다.

### 2.2 이미지–텍스트 정합성 측정

CLIPScore[5]는 CLIP 유사도를 캡션 품질의 자동 평가에 사용했고, BLIP[6] 등 통합 비전–언어
모델도 정합성 표현을 제공한다. 본 연구는 **CLIP 기반 이미지–텍스트 코사인 유사도와 동일한
형태의 계산**을, 캡션 품질 평가가 아니라 **검색에서 시각 정보의 기여를 분석하는 변수**로
활용한다.

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
**검색 성능·모달 간 점수 관계에 기반한 적응 메커니즘**으로 조정한다[8,9]. 이와 달리 본 연구는
새로운 융합 기법이 아니라, **썸네일–제목 간 의미적 비정렬 정도(gap)를 영상 수준의 연속 변수로
정의하고 이를 실제 순위 개선과 연결해 분석하는 관점**을 취한다.

## Ⅲ. 연구 방법

전체 처리 과정은 그림 1과 같다. 쿼리·코퍼스 구성부터 세 인코더 임베딩, gap 산출,
세 검색 방식과 late fusion, 그리고 순위 개선(Δrank) 산출·분석까지의 흐름을 나타낸다.

<!-- 최종 HWP: 아래 라우팅을 박스+화살표 도식으로 재작성 — 그림 1.
     핵심: Query와 제목이 각각 mpnet·CLIP-text 두 인코더로 '이중 인코딩'됨을 반드시 시각화. -->
```
[구성]  쿼리 경로 : 자동완성 초성 sweep → 기준 기반 큐레이션  ⇒  Query 70 (14×5)
        코퍼스 경로: search + videos.list                        ⇒  Video Corpus 840 (14×60; 제목+썸네일)

[인코더 3종]   mpnet(검색 텍스트, 768d) · CLIP-text(CLIP정렬 다국어 텍스트, 512d) · CLIP-image(썸네일, 512d)

[이중 인코딩 라우팅]
        Query  ─┬─►[mpnet]──────► 쿼리 텍스트 임베딩
                └─►[CLIP-text]──► 쿼리 CLIP 임베딩
        제목   ─┬─►[mpnet]──────► 제목 텍스트 임베딩
                └─►[CLIP-text]──► 제목 CLIP 임베딩
        썸네일 ────►[CLIP-image]► 썸네일 이미지 임베딩

[채널 계산]
        Text sim   = cos( 쿼리 텍스트 , 제목 텍스트 )            → Text Retrieval
        Visual sim = cos( 쿼리 CLIP  , 썸네일 이미지 )           → Visual Retrieval
        gap        = 1 − cos( 제목 CLIP , 썸네일 이미지 )  (mean-centered)

[검색·분석]  Text Retrieval + Visual Retrieval ─► Late Fusion(α=0.5) ─► Δrank
             ⇒  RQ1: gap ↔ Δrank 연관   /   RQ2: 검색 성능
```

**그림 1. 전체 처리 과정** (쿼리·코퍼스 구성 → 임베딩 → gap 산출 → 검색·융합 → 순위 개선·분석) [results/fig1_pipeline.png/.svg]

### 3.1 임베딩 추출

세 인코더를 역할별로 사용한다(표 1). 썸네일은 CLIP 이미지 인코더로, 검색용 텍스트(제목·
쿼리)는 다국어 문장 인코더로 인코딩한다. gap 계산과 시각 채널 비교는 **CLIP 이미지 공간에
정렬된 다국어 텍스트 인코더**를 쓴다. 검색 텍스트 채널은 한국어 품질이 좋은 별도 인코더를
쓰되, gap은 반드시 같은 결합 공간에서 계산해야 하므로 역할을 섞지 않는다.

**표 1. 사용 임베딩 인코더** (텍스트 인코더가 둘인 이유: 입력은 같아도 목적·표현 공간이 다름)

| 역할 | 인코더 | 입력 | 출력 | 용도 |
|---|---|---|---|---|
| 이미지 | `sentence-transformers/clip-ViT-B-32` | 썸네일 | 512 | 시각 검색·gap의 이미지 표현 |
| CLIP 정렬 텍스트 | `sentence-transformers/clip-ViT-B-32-multilingual-v1` | 제목·쿼리 | 512 | CLIP 이미지와 **같은 공간**에서 gap·시각 검색용 텍스트 표현 |
| 검색 텍스트 | `paraphrase-multilingual-mpnet-base-v2` | 제목·쿼리 | 768 | 한국어 텍스트 검색 유사도 |

두 텍스트 인코더는 목적이 다르다. CLIP 계열 텍스트 인코더는 **이미지–텍스트 공동공간에서
gap과 시각 유사도를 계산**하기 위해, mpnet 계열 인코더는 **한국어 텍스트 간 검색 유사도**를
높이기 위해 사용한다. 따라서 **Text-only의 검색 점수와 gap은 서로 다른 표현 공간에서 산출되며,
gap을 검색 점수 자체의 일부로 사용하지 않는다**(검색용 텍스트 표현과 시각–텍스트 관계 측정용
CLIP 표현의 분리). **구현 세부**: 모든 임베딩은 L2 정규화하며, 유사도는 코사인, 채널 결합 전
쿼리별 min–max 정규화를 적용한다. 텍스트는 원문 그대로 인코딩한다.

### 3.2 썸네일–제목 의미 격차(gap)

영상 *i*의 gap은 CLIP 결합 공간에서 모달별 mean-centering을 적용한 썸네일·제목 임베딩의 코사인
유사도를 역변환(1 − cos)하여 정의하는 영상 수준의 비정렬 지표다.

<!-- 최종 HWP: 아래 식을 수식편집기로 정식 조판(식 (1)) -->
$$
\mathrm{gap}_i = 1 - \cos\!\big(\,\mathrm{center}(v^{\mathrm{img}}_i),\ \mathrm{center}(g^{\mathrm{txt}}_i)\,\big) \tag{1}
$$

즉 **gap이 클수록 썸네일과 제목의 표현이 공동공간에서 덜 유사하다**. 여기서 '의미 격차'는
**인간의 의미 판단에 따른 직접적 의미 차이가 아니라, CLIP 공동 임베딩 공간에서 측정한
썸네일–제목 표현 간 비유사도**를 가리킨다. 본 연구는 이 비정렬 정도가 검색에서 시각 정보의
추가 기여와 관련되는지를 실험으로 검증하며, gap을 그 자체로 "시각 정보의 유용성"으로 정의하지
않는다.

여기서 center(·)는 모달별 코퍼스 평균을 차감한 뒤 재정규화하는 전처리다. 이는 원 임베딩의
전역적 평균 방향 차이(비등방성·모달 간 평균 방향 차이)가 개별 영상 간 유사도에 미치는 영향을
줄여, **영상별 상대적 비정렬 정도를 비교**하기 위한 것이다[10][11][12].

이 전처리는 **어떤 retrieval 점수·Δrank·qrels도 보기 전에 고정**했으며, 그 적절성은 검색 성능이
아니라 **자기매칭 기반 타당성 점검(self-matching validation)**(각 제목이 무작위 썸네일보다 자기
썸네일과 더 정합한지)으로 사전 점검했다. raw gap도 민감도 분석으로 병기한다(§4.4).

gap은 라벨링 없이 전체 코퍼스에 임베딩 추출 과정에서 산출되어 추가 비용이 없다. 또한
gap은 영상 자체의 썸네일–제목 관계를 나타내는 **영상 수준 변수로 쿼리를 포함하지 않으며**,
검색 단계에서 동일 영상에 대한 **쿼리별 순위 변화(Δrank)** 와 결합되어 시각 정보의 검색 기여
조건을 분석하는 데 쓰인다(§3.3–3.4).

### 3.3 Late Fusion 검색

세 검색 방식을 비교한다. 두 채널의 점수 스케일이 달라 쿼리별 min–max 정규화 후 가중합한다.

<!-- 최종 HWP: Late Fusion score 식을 수식편집기로 식 (2)로 조판 -->
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

<!-- 최종 HWP: Δrank 식을 수식편집기로 식 (3)으로 조판 -->
```
Δrank(v,q) = rank_text(v|q) − rank_fusion(v|q)      (양수 = 융합이 순위 개선)
```

여기서 rank는 **전체 평가 코퍼스(840편) 내 순위**로 정의하고, Text-only·Fusion 두 방식
모두 전체 코퍼스에 대해 동일하게 계산한다. Top-K로 절단하지 않으므로 관련 영상이 Top-10
밖이라도 Δrank가 항상 정의된다(검색 성능 지표는 @10 절단을 쓰나, Δrank는 관련 영상의 순위
이동을 온전히 반영하기 위해 전체 순위를 사용한다).

가설은 **gap이 큰 영상일수록 Δrank가 크다**(Spearman ρ>0)는 것이다. gap은 영상 수준
지표이므로, 분석은 영상당 Δrank를 median으로 집계해 `Spearman(gap, median Δrank)`로 본다.

## Ⅳ. 실험 설계

설계는 실험 전 사전 등록(pre-registration)으로 고정했다. 실험 데이터 구성은 표 2와 같으며,
핵심만 요약한다.

**표 2. 실험 데이터 구성**

| 구분 | 값 |
|---|---|
| 영상 카테고리 | 14 |
| 검색 영상 코퍼스 | 840 (14 × 60) |
| 평가 쿼리 | 70 (14 × 5) |
| 쿼리당 pooling 후보(평균) | 23.0 |
| Query–Video 평가 쌍 | 1,607 |
| 평가자 | 3인 (blind·독립) |
| Short 영상 비율 | 12.5% |

### 4.1 평가 코퍼스

YouTube KR `assignable` 카테고리 **14개**를 주제 다양성 확보용 층화 틀로 사용해 **카테고리당
60편 × 14 = 840편**을 수집했다. categoryId는 **표집 기준(Sampling Anchor)일 뿐 semantic
ground truth가 아니며**, 본 연구의 어느 분석에서도 레이블로 쓰지 않는다. 절차: 카테고리당 복수 seed로 `search`
수집 → `videos.list`의 categoryId로 사후 필터링, 정렬 3혼합(relevance·viewCount·date), 채널당
최대 5편, seed 간 round-robin. **60초 초과 영상만 수집**, 게시일 2025-01-01
이후. 이는 확률표본이 아니라 **gap 분산 확보용 카테고리 층화표본**이다. 코퍼스에는 Short가
**12.5% 포함**되며, Short 포함 여부가 결과에 미치는 영향은 non-Shorts 부분표본 민감도 분석으로
확인하였다(§5.2).

### 4.2 평가 쿼리

쿼리는 연구자 창작이나 영상 텍스트에서 파생하지 않고(순환논리 회피) **YouTube 공개
자동완성(Suggest)** 에서 생성하였다. 카테고리명·관련어에 한글 초성을 결합해 후보 pool을 만든
뒤, **사전 정의된 기준**으로 navigational(채널·프로그램·작품·인물·기관명)·category mismatch·
상품/서비스·무의미 후보를 제외하고, 카테고리 내 주제 다양성을 고려해 **카테고리당 5개 × 14 =
70개**를 선정하였다. 선정은 검색·라벨링 **이전**에 완료(가설 결과에 blind)하였고 이후 성능을
보고 바꾸지 않는다(freeze). 따라서 이 쿼리 집합은 사용자 검색 빈도의 확률표본이 아니라
**평가용 쿼리 집합**이다.

### 4.3 정답지(qrels) 구축

편향을 막기 위해 **Text-only ∪ Visual-only ∪ Late Fusion 각 Top10의 합집합**(pooling)을 후보
풀로 삼는다. 후보 (쿼리, 영상) 쌍을 **3인이 blind·독립**으로 3단계(2=관련/1=부분/0=무관)로
라벨링한다. 3단계는 순서형(ordinal) 등급이므로 최종 등급은 **세 판정의 중앙값(median)** 으로
집계하도록 사전 고정한다. 평가자 간 일치도는 **Fleiss' κ**(3인 전체)로 보고하고, 평가자 쌍별
**Cohen's κ**를 보조로 제시한다. 최종 qrels에서 관련(등급≥1) 문서가 0개인 쿼리는 채점 불가로
제외하고, 제외 수를 카테고리별로 투명 보고한다.

### 4.4 평가 지표 및 통계 검정

지표는 검색 성능(RQ2)에 MRR@10·NDCG@10·Recall@10, gap–개선 연관(RQ1)에 Spearman ρ(gap,
median Δrank)를 쓴다. 본 논문은 연구 질문 RQ1·RQ2로 명칭을 통일하며,
각각을 아래 검정으로 확인한다.

- **RQ2 검정(융합 효과)**: 유의성은 Text-only 대 Fusion(α=0.5)의 쿼리별 reciprocal rank@10에
  대한 **paired Wilcoxon signed-rank test**(p<0.05)를 primary로 쓴다(RR@10이 이산·비정규
  분포라 비모수). 효과의 크기는 **MRR@10·NDCG@10·Recall@10의 절대 변화량과 부트스트랩 95%
  CI**로 별도 보고하고, Wilcoxon의 짝지음 효과 크기로 **rank-biserial correlation**을 병기한다.
  즉 유의성과 효과 크기를 분리하며, 임의의 개선 임계값은 두지 않는다.
- **RQ1 검정(gap–개선 연관)**: 하나의 영상이 여러 쿼리에서 평가될 수 있으므로, 영상 수준 gap과
  쿼리 수준 Δrank의 **관측 단위를 영상 수준으로 일치**시키기 위해 영상별 Δrank를 하나의
  대표값으로 집계한다. 집계는 **중앙값(median)** 을 쓰며, 이는 특정 쿼리에서 나타나는 극단적
  순위 변화의 영향을 줄이기 위함이다(다만 영상이 카테고리에 내포되고 동일 검색 시스템·pooling을
  공유하므로 완전한 통계적 독립을 주장하지는 않는다). 분석은 세 층으로 구분한다. **Primary**:
  `Spearman ρ(gap, median Δrank)`의 유의성(ρ>0, p<0.05)과 **부트스트랩 95% CI**. **Robustness**:
  raw vs centered gap 민감도, 카테고리 간/내(between/within) 상관 분해, 카테고리별 상관. **Exploratory**:
  카테고리별 융합 효과와 α 민감도. 귀무 결과는 표본 규모의 한계를 함께 고려해 해석한다.
  상관 유의성은 예측력의 직접 증거가 아니므로, 본 연구는 결과를 "예측"이 아니라 "연관"으로
  해석한다.
- **Short 강건성**: 코퍼스의 12.5%가 Short이므로, Short 유병률을 보고하고 **Short 제외
  부분표본(non-Shorts)으로 RQ1·RQ2를 재실행**해 결과가 Short 포함에 좌우되지 않음을
  확인한다. Short 수가 충분하면 Short/일반 서브그룹 비교를 탐색적으로 병기한다.

## Ⅴ. 결 과

### 5.1 데이터셋 및 라벨링 신뢰도

전체 라벨링 단위는 70개 쿼리 × 쿼리당 평균 23.0개 후보 = **1,607개 (쿼리, 영상) 쌍**이다.
세 라벨러 간 일치도를 평가한 결과 **Fleiss' κ는 0.486**, 단순 일치율은 **77.7%** 였다. 라벨러
쌍별 **Cohen's κ는 0.462–0.523** 범위로, 특정 라벨러에 불일치가 집중되는 양상은 관찰되지
않았다. 전체 사례의 **69.0%** 는 세 라벨러가 동일 등급을 부여하였고, **17.2%** 는 인접 등급 간,
**13.8%** 는 0과 2가 함께 나타나는 극단적 불일치였다. 불일치는 주로 의미 범위가 넓거나 관련성
경계가 모호한 쿼리에서 나타났다. 최종 관련도는 세 판단의 **중앙값(median)** 으로 결정하였다.

최종 관련도가 0인(관련 영상 0개) **7개 쿼리를 사전 정의된 zero-relevance 규칙에 따라 제외**하여
**63개 쿼리**로 검색 평가를 수행하였다. 쿼리당 관련 영상은 평균 **7.0개**(중앙값 6)였으며,
관련 영상이 1개인 일부 쿼리는 평가 지표의 변동성이 클 수 있어 해석 시 이를 고려하였다.

### 5.2 검색 성능과 융합 효과 (RQ2)

**표 3. 시스템별 검색 성능** (63개 쿼리, macro-average)

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|---|---|---|---|
| Text-only | 0.690 | 0.556 | 0.627 |
| Visual-only | 0.432 | 0.301 | 0.316 |
| Late Fusion (α=0.5) | 0.673 | 0.561 | 0.637 |

**썸네일 단독(Visual-only)은 텍스트 검색보다 크게 낮았다**(MRR 0.432 vs 0.690). 사전등록된
**동일가중 late fusion(α=0.5)은 텍스트 대비 유의한 개선을 보이지 않았다** — 쿼리별 RR@10의
Wilcoxon 검정 결과 ΔMRR = −0.016(부트스트랩 95% CI [−0.089, +0.055]), p=0.761로, MRR은
오히려 소폭 감소하였고 NDCG·Recall의 차이도 작았다.

**가중치 민감도(탐색적).** 사전등록 밖의 α를 탐색적으로 비교하면(표 4), 세 지표 모두 시각을
100%(α=0) 또는 50%(α=0.5)로 강하게 넣을 때보다 **텍스트를 주 신호로 유지하고 시각을 보조로
결합하는 중간 가중치(α≈0.6–0.7)에서 상대적으로 높게** 나타났다. 다만 이는 결과를 본 뒤 검토한
탐색적 sensitivity 분석이며 다중비교를 통제하지 않았으므로 확증적으로 해석하지 않는다(α=0.7에서
Text 대비 ΔNDCG +0.039(p=0.034), ΔRecall +0.071(p=0.019)의 개선 신호가 관찰되는 정도).

**표 4. 융합 가중치 α별 성능**(α=1은 Text-only, 탐색적)

| α (시각 비중) | 0.5 (50%) | 0.6 (40%) | 0.7 (30%) | 0.8 (20%) | 1.0 (0%) |
|---|---|---|---|---|---|
| MRR@10 | 0.673 | 0.677 | 0.701 | 0.695 | 0.690 |
| NDCG@10 | 0.561 | 0.584 | 0.594 | 0.587 | 0.556 |
| Recall@10 | 0.637 | 0.681 | 0.698 | 0.671 | 0.627 |

<!-- 최종 HWP: results/fig2_alpha_curve.png 삽입 -->
**그림 2. 융합 가중치 α에 따른 검색 성능 변화**(탐색적) [results/fig2_alpha_curve.png]

**순위 수준 분석.** 융합은 관련 영상의 전체 코퍼스 순위를 변화시켰다. 관련 (query, video) 쌍의
Δrank(=rank_text − rank_fusion@0.5, 양수=융합이 순위 상승)를 Text 순위 구간별로 보면(표 5), Text
순위가 1–10위인 관련 영상의 median Δrank는 **−2.0(개선 24%)** 인 반면, 11위 이하의 관련 영상에서는
대부분 양(+)이었다(11–50위 93%, 51위 이하 100%). 상위 10위 진입/이탈은 진입 103·이탈 93(순증
+10), 첫 관련 결과의 순위는 개선 14·악화 11·동일 33이었으며, 쿼리별 median Δrank는 +1(양수
비율 59%)이었다.

**표 5. Text 순위 구간별 Δrank**(양수=융합이 순위 상승; 관련 쌍 기술통계)

| Text 순위 구간 | n | median Δrank | 개선(>0) 비율 |
|---|---|---|---|
| 1–10 | 253 | −2.0 | 24% |
| 11–50 | 132 | +13.0 | 93% |
| 51–100 | 18 | +53.5 | 100% |
| 101+ | 37 | +201.0 | 100% |

**Short 강건성.** Short를 제외한 부분표본(735편)으로 재실행해도 결론은 유지되었다 — 동일가중
융합은 유의한 개선을 보이지 않았고(ΔMRR +0.033, Wilcoxon p=0.30), 아래 gap–순위변화 관계도
유의하지 않았다(centered ρ = −0.06). 즉 결과는 Short 포함 여부에 좌우되지 않았다.

### 5.3 의미 격차와 순위 변화의 관계 (RQ1)

**Primary는 유의하지 않았다.** 영상 수준에서 category-centered gap과 영상당 median Δrank의
Spearman 상관은 **ρ = −0.049(95% CI [−0.175, +0.080], p=0.42)** 로, 사전등록된 관계(ρ>0)는
확인되지 않았다.

**Robustness — 관계는 카테고리 수준에 영향받았다.** raw gap에서는 약한 음의 상관이 관찰되었으나
(ρ = −0.226, p<0.001), 이를 **카테고리 간(between; 카테고리 평균값끼리의 상관)과 카테고리 내
(within; 각 변수에서 카테고리 평균을 제거한 뒤의 상관)** 로 분해하면 between-category 상관은
상당히 큰 음의 값(ρ = −0.679, 카테고리 14개 평균값으로 계산), within-category 상관은 약했다
(ρ = −0.120). 즉 raw association은 카테고리별 평균 차이에 상당 부분 영향을 받은 것으로 해석할 수 있다. 카테고리별 within 상관은 대부분
비유의하며 유의한 두 카테고리(과학기술 −0.46, 스포츠 +0.52)조차 부호가 반대여서, **카테고리
내부의 gap–Δrank 관계는 일관되지 않았다**. 따라서 단일 의미 격차 지표만으로 영상 수준에서
시각정보의 검색 기여를 설명하는 데에는 한계가 있었다.

<!-- 최종 HWP: 그림 3 = centered gap(x) vs 영상당 median Δrank(y) 산점도(카테고리 색상 최소).
     binned median 평평(ρ≈0). results/fig3_gap_scatter.png 삽입 -->
**그림 3. 의미 격차(centered gap)와 영상당 median Δrank의 관계**(ρ≈0) [results/fig3_gap_scatter.png]

### 5.4 카테고리별 융합 효과 (탐색적)

전체 평균은 정체였으나 **융합 효과의 방향이 카테고리에 따라 상이**하였다. ΔMRR 기준 뉴스·여행·
과학기술 등에서는 양(+), 코미디·노하우 등에서는 음(−)의 경향이 관찰되었고, 낮은 시각 가중
(α=0.7)에서 Recall이 개선된 쿼리도 뉴스·과학·여행에 상대적으로 많았다. 다만 카테고리당 쿼리
수가 적어(3~5개) **탐색적 결과로만** 해석하며, 특정 카테고리에서 썸네일이 유효하다고
일반화하지는 않는다.

## Ⅵ. 논 의

### 6.1 썸네일 시각정보와 융합의 검색 효과 (RQ2)

썸네일 단독 검색이 텍스트보다 크게 낮았던 것(§5.2)은, CLIP 기반 썸네일–쿼리 유사도가 이
환경에서 텍스트 메타데이터를 대체할 만큼 강한 검색 신호가 아니었음을 보여준다. 썸네일은
클릭 유도를 위해 제작되어 쿼리 매칭에 최적화되어 있지 않고, 본 시각 인코더는 OCR을 하지 않아
썸네일 내 한국어 자막을 활용하지 못하며, 다국어 CLIP의 한국어 품질 한계도 작용했을 수 있다.
동일가중 late fusion(α=0.5)이 개선을 보이지 못한 것도 이와 부합한다. 이는 시각 채널의 상대적
신호 강도가 텍스트보다 낮은 상황에서 동일가중 결합이 텍스트 신호를 희석했을 가능성과 부합하는
관찰이며, 인과를 직접 입증한 것은 아니다.

한편 융합이 검색 결과 구성 자체를 바꾸지 않은 것은 아니다. 관련 영상의 전체 코퍼스 순위는
상당히 이동하였으나, 그 개선은 **상위 10위 이후의 깊은 순위에서 강하게 나타났고 이미 상위에
있던 관련 영상은 오히려 소폭 밀렸다**(§5.2, 표 5). 이 패턴은 순위 이동(Δrank)이 있음에도 상위
결과 품질 지표(MRR)가 개선되지 않은 이유를 잘 설명한다. 즉 전체 순위의 변화와 상위 검색
결과의 효과성은 서로 다른 축이며, 본 결과에서 융합의 효과는 주로 전자에 국한되었다.

### 6.2 의미 격차의 설명력 (RQ1)

사전등록된 centered gap과 순위 변화의 관계는 유의하지 않았다(§5.3). raw gap에서 관찰된 약한
음의 상관은 카테고리 간 차이(between)에 크게 기인하였고 카테고리 내부(within)에서는 약화되었다.
gap이 크다는 것은 썸네일이 제목과 의미적으로 멀다는 뜻이지만, 그 거리가 영상 수준에서 융합에
의한 순위 개선으로 이어지지는 않았다. 오히려 카테고리 수준의 연관은 원래 가정과 반대 방향
(gap이 큰 카테고리일수록 개선이 작음)이었고, 이는 영상 수준의 기전이라기보다 카테고리 구성의
반영으로 보인다. 따라서 **단일 의미 격차 지표만으로 시각정보의 검색 기여 조건을 설명하기에는
한계가 있었다.** 이는 연구 질문이 잘못되었다기보다, "하나의 gap 값으로 시각 기여를 설명할 수
있는가"에 대해 본 데이터·설정에서는 충분하지 않았다는 답으로 해석된다.

### 6.3 카테고리 이질성과 탐색적 개선 신호

전체 평균은 정체였으나 융합 효과의 방향은 카테고리에 따라 달랐고(뉴스/여행/과학 등 +, 코미디/
노하우 등 −), 탐색적으로 텍스트를 주 신호로 두고 시각을 낮은 가중으로 결합한 중간 가중치
(α≈0.6–0.7)에서 일부 지표가 상대적으로 높았다(§5.4, 표 4). 이는 시각적 단서가 검색 의도와
연결될 가능성이 높은 영역에서 시각정보의 보조적 활용 가능성을 **시사**한다. 그러나 카테고리당
표본이 작고(3~5 쿼리) α 선택이 사후적이며 다중비교를 통제하지 않았으므로, 이들은 확증이
아니라 후속 연구에서 검증할 가설로 남긴다.

### 6.4 실무적 함의

당초 구상했던 "gap 기반 시각 임베딩 선별 색인"(낮은 gap 영상은 시각 임베딩 생략)은 본 결과로
뒷받침되지 않는다 — 동일가중 융합이 평균 성능을 개선하지 못했고 gap도 기여 영상을 안정적으로
식별하지 못했기 때문이다. 오히려 본 결과가 시사하는 바는, 텍스트 메타데이터 기반 영상 검색에
단순 late fusion으로 썸네일 유사도를 더하는 것은 제한적이고 일관되지 않은 이득에 그치며,
사용한다면 **시각을 낮은 가중의 보조 신호로 두는 편(텍스트 주도)** 이 낫다는 것이다. 시각정보가
언제 도움이 되는지를 판별하려면 단일 gap보다 풍부한 신호가 필요하다(§6.5). 따라서 실무적
결론은 배포 가능한 규칙이라기보다 **적용상의 주의와 후속 연구 방향**이다.

### 6.5 한계

(1) 시각 인코더는 OCR을 하지 않아 **썸네일 내 한국어 자막을 판독하지 못하며**, gap·시각 유사도는
다국어 CLIP의 한국어 품질과 mean-centering 전처리에 의존한다. (2) 평가 코퍼스는 확률표본이 아닌
카테고리 층화표본이며 쿼리·표본 규모가 제한적이다(대표성·일반화는 그 범위로 한정). (3) 코퍼스는
Short를 12.5% 포함하며(§4.4), Short 썸네일은 특성이 달라 해석에 영향을 줄 수 있다. (4) qrels는 세
방식의 Top-10 pooling으로 구축되어 모든 방식에서 낮은 순위인 관련 영상은 누락될 수 있고
(pooling bias), 이에 따라 Recall 과소추정 및 Δrank 분석의 상위-편향 가능성이 있으며 primary
분석은 상관이지 인과가 아니다. (5) 카테고리별·α 분석은 탐색적(소표본·다중비교 미통제)이며,
Δrank는 전체 코퍼스 순위 기준이라 상위 결과 효과성과 구분된다.

## Ⅶ. 결 론

본 연구는 영상 검색에서 텍스트 정보와 함께 썸네일의 시각정보를 활용할 때 검색 성능이 어떻게
변화하는지, 그리고 시각정보의 기여 조건을 시각–텍스트 의미 격차(gap)로 설명할 수 있는지를
한국어 YouTube 검색 환경에서 분석하였다.

실험 결과, 썸네일 단독 검색은 텍스트 검색보다 낮은 성능을 보였으며, 사전등록된 동일가중 late
fusion 역시 텍스트 대비 유의한 향상을 보이지 않았다. 다만 순위 수준에서는 관련 영상의 위치가
변화하였고, 이 변화는 상위 10위보다 그 이후의 깊은 순위에서 더 뚜렷하였다. **특히 융합은 상위
10위 내 첫 관련 결과를 안정적으로 개선하기보다, 기존 텍스트 검색에서 후순위에 위치한 관련
영상의 순위를 재배치하는 양상을 보였다.** 이는 썸네일 정보가 검색 결과의 구성에는 영향을 줄 수
있으나, 첫 관련 결과의 노출이나 상위 결과의 품질을 안정적으로 개선하는 강한 신호로 작동하지는
않았음을 시사한다. 즉 검색 결과의 순위 구성 변화와 상위 결과의 효과성은 서로 다른 축이었다.

가중치 민감도 분석에서는 텍스트를 주 신호로 유지하고 시각정보를 낮은 가중으로 결합한 중간
가중치에서 일부 지표가 상대적으로 높게 나타났으며, 카테고리별 융합 효과의 방향도 상이하였다.
다만 이들은 탐색적 결과이므로 특정 조건에서 썸네일이 유효하다고 일반화하지는 않는다.

한편 시각–텍스트 의미 격차와 순위 변화의 관계에서는, 사전등록된 centered gap과 Δrank 사이에
유의한 관계가 확인되지 않았다. raw gap에서 관찰된 연관은 카테고리 수준의 이질성에 영향을 받은
것으로 나타났고 카테고리 내부에서는 일관되지 않았다. 따라서 단일 의미 격차 지표만으로 시각
정보의 검색 기여 조건을 설명하는 데에는 한계가 있었다.

종합하면, **썸네일은 텍스트 검색을 대체할 만큼 강한 검색 신호는 아니었으나, 텍스트 검색을
보조하여 검색 결과의 순위 구성을 변화시키는 양상이 관찰되었으며, 그 기여를 단일 시각–텍스트
의미 격차로 설명하기에는 한계가 있었다.** 향후에는 단일 gap 값에 의존하기보다 객체·장면·자막(OCR)·
구도 등 썸네일의 구체적 시각 특성을 분해하고, 쿼리 의도 및 영상 장르와의 상호작용을 함께
고려할 필요가 있다. 또한 본 연구는 제한된 쿼리와 표본을 대상으로 하였으므로, 다양한 검색 환경과
데이터셋에서 동일한 패턴이 재현되는지 검증할 필요가 있다.

## Acknowledgement

이 논문은 2024년도 정부(과학기술정보통신부)의 재원으로 정보통신기획평가원의 지원을 받아
수행된 연구임 (No.RS-2024-00340834, 써드파티 데이터의 활용성 증대를 위한 액티브 메타데이터
기반 능동형 데이터 확장 기술 개발).

## References

[1] H. Fang, P. Xiong, L. Xu, and Y. Chen, "CLIP2Video: Mastering video-text retrieval via
image CLIP," *arXiv:2106.11097*, Jun. 2021.

[2] S. Liu, W. Quan, M. Zhou, et al., "M2HF: Multi-branch multi-modal hybrid fusion for
text–video retrieval," *Comput. Vis. Media*, Vol. 12, No. 2, pp. 449–471, 2026.

[3] A. Radford et al., "Learning transferable visual models from natural language supervision,"
in *Proc. Int. Conf. Machine Learning (ICML)*, Vol. 139, pp. 8748–8763, Jul. 2021.

[4] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese
BERT-networks," in *Proc. EMNLP-IJCNLP*, pp. 3982–3992, Nov. 2019.

[5] J. Hessel, A. Holtzman, M. Forbes, R. L. Bras, and Y. Choi, "CLIPScore: A reference-free
evaluation metric for image captioning," in *Proc. EMNLP*, pp. 7514–7528, Nov. 2021.

[6] J. Li, D. Li, C. Xiong, and S. Hoi, "BLIP: Bootstrapping language-image pre-training for
unified vision-language understanding and generation," in *Proc. Int. Conf. Machine Learning
(ICML)*, Vol. 162, pp. 12888–12900, Jul. 2022.

[7] W. Naveed, Z. A. Uzmi, and Z. A. Qazi, "ThumbnailTruth: A multi-modal LLM approach for
detecting misleading YouTube thumbnails across diverse cultural settings," *arXiv:2509.04714*,
Sep. 2025.

[8] W. Ma, Q. Chen, F. Liu, T. Zhou, and Z. Cai, "Query-adaptive late fusion for hierarchical
fine-grained video-text retrieval," *IEEE Trans. Neural Netw. Learn. Syst.*, Vol. 35, No. 5,
pp. 7150–7161, May 2024.

[9] E. Loweimi, M. Qian, K. Knill, et al., "To be multimodal or not to be: Query-adaptive
audio-visual person retrieval via active modality detection," in *Proc. INTERSPEECH*, 2026.

[10] J. Mu and P. Viswanath, "All-but-the-top: Simple and effective postprocessing for word
representations," in *Proc. Int. Conf. Learning Representations (ICLR)*, 2018.

[11] K. Ethayarajh, "How contextual are contextualized word representations? Comparing the
geometry of BERT, ELMo, and GPT-2 embeddings," in *Proc. EMNLP-IJCNLP*, pp. 55–65, Nov. 2019.

[12] W. Liang, Y. Zhang, Y. Kwon, S. Yeung, and J. Zou, "Mind the gap: Understanding the
modality gap in multi-modal contrastive representation learning," in *Proc. Adv. Neural Inf.
Process. Syst. (NeurIPS)*, Vol. 35, pp. 17612–17625, Dec. 2022.
