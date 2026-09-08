<!-- 한국정보통신학회 춘·추계 종합학술대회 제출용 초안 (KIICE format).
     본문 2단·국문 함초롱바탕 등 조판은 HWP 양식에서 적용. 이 파일은 내용 원고.
     저자/소속/과제문구만 [ ] 플레이스홀더. 실험 수치·그림 모두 확정 반영됨(2026-08-27).
     HWP 붙여넣기용 txt는 code/build_hwp_txt.py로 자동 생성(이 파일 수정 후 재실행). -->

# 영상 검색에서 썸네일과 텍스트의 후기 융합에 따른 검색 순위 변화와 의미 간극 분석

**Analysis of Search Ranking Changes and Semantic Gap in Video Retrieval with Late Fusion of Thumbnail and Textual Information**

<!-- 제목 개정(2026-09-08): 발견 중심(검색 순위 변화) + 두 축(순위 변화·의미 간극)으로 국문 제목 변경.
     ※ 영문 제목·초록 동기화 및 용어 '의미 간극' 본문 통일 반영(2026-09-08). -->

[저자1] · [저자2]<sup>*</sup>  
[소속1] · [소속2]  
[Author1] · [Author2]<sup>*</sup>  
[Affiliation1] · [Affiliation2]  
E-mail : [email1] / [email2]

---

## 요 약

본 연구는 YouTube 영상 검색에서 썸네일과 텍스트의 후기 융합(late fusion)에 따른 검색 순위 변화를
사전등록 기반으로 분석하였다. 한국어 YouTube 영상 840편과 검색어 70개를 대상으로 CLIP 이미지
임베딩과 다국어 텍스트 임베딩을 활용하여 텍스트 단독, 썸네일 단독, 후기 융합 검색을 비교하고,
썸네일과 제목 간 의미 간극(semantic gap)과 검색 순위 변화의 관계를 분석하였다. 분석 결과, 썸네일
단독 검색은 텍스트 단독 검색보다 성능이 낮았으며, 동일가중 후기 융합도 평균 검색 성능을 유의하게
개선하지 못했다. 그러나 후기 융합은 검색 결과의 순위를 재배치했으며, 변화의 양상은 순위 깊이와 영상
카테고리에 따라 달랐다. 반면 사전등록된 의미 간극과 순위 변화 간의 유의한 관계는 확인되지 않았다.
결과적으로 썸네일 단독 정보로는 텍스트 검색을 대체하지 못했으나, 텍스트와의 후기 융합은 검색 결과의
순위 구성을 변화시킬 수 있음을 보여주며, 이러한 순위 변화를 단일 의미 간극 지표만으로 설명하기에는
한계가 있음을 확인하였다.

## ABSTRACT

This study analyzes, under a pre-registered protocol, the ranking changes induced by late fusion of
thumbnail and text in YouTube video search. On 840 Korean YouTube videos and 70 queries, using CLIP
image embeddings and multilingual text embeddings, we compare text-only, thumbnail-only, and
late-fusion retrieval, and analyze the relationship between the thumbnail–title semantic gap and the
change in retrieval ranking. Thumbnail-only retrieval performed worse than text-only retrieval, and
equal-weight late fusion did not significantly improve average retrieval performance. However, late
fusion recomposed the ranking of results, and the pattern of change varied with rank depth and video
category. In contrast, the pre-registered association between the semantic gap and ranking change was
not observed. Overall, thumbnail information alone did not replace text retrieval, but its late fusion
with text could reshape the rank composition of results, and a single semantic-gap metric was
insufficient to characterize this ranking change.

**키워드** : Multimodal retrieval, CLIP, Late fusion, Thumbnail–title semantic gap, Ranking change, Korean YouTube

---

## Ⅰ. 서 론

영상 검색 플랫폼은 제목·설명·태그 등 **텍스트
메타데이터**를 주로 색인하며, 사용자의 클릭 판단에 크게 작용하는 **썸네일의 시각 정보**를
검색 색인에 직접 반영하는 사례는 제한적이다. 시각 채널을 텍스트와 결합해 검색 성능을 높이는
접근이 보고돼 왔다[1][2]. 그러나 그 개선이 **모든 영상에서 균일한지, 특정 조건에서만
나타나는지**에 대한 분석은 제한적이다. 시각 임베딩의 계산·
저장에는 비용이 들기 때문에, 시각 정보의 검색 기여 여부와 그 조건을 이해하는 것은 메타데이터
검색 플랫폼의 색인 설계에도 함의를 갖는다. 본 연구는 이 문제를 한국어 YouTube 검색 환경에서
실증적으로 분석한다.

시각 정보의 기여는 영상마다 다를 수 있다. 텍스트가 이미 내용을 충분히 담은 영상에서는 썸네일이
추가 정보를 제공하기 어려울 수 있는 반면, 텍스트와 썸네일의 정보가 다를 경우 시각 채널이 추가
정보를 제공할 **가능성**이 있다. 이에 본 연구는
**썸네일과 제목의 의미적 차이가 시각 정보의 검색 기여와 관련될 가능성**에 주목하여, 이를 정량화한
**썸네일–제목 의미 간극(gap)**을 후보 지표로 삼고 그 관련성을 실험으로 검증한다. 다만 gap이
크더라도 그 시각 정보가 특정 검색어와 무관하면 도움이 안 될 수 있으므로, 본 연구는 gap을 "시각
정보의 유용성"과 동일시하지 않는다.

썸네일을 사람이 유형별로 분류하는 대안은 분류 기준 설계·라벨링 비용과 경계 사례의 주관이
개입된다. 본 연구는 대신 임베딩 추출 과정에서 얻는 표현만으로 gap을 **추가 라벨링 없이
자동·재현 가능한 연속 지표**로 산출한다.

본 연구의 연구 질문과 기여는 다음과 같다.

- **RQ1(조건)**: 영상별 gap이 클수록 융합에 의한 검색 순위 개선(Δrank)이 큰가?
- **RQ2(성능)**: CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 후기 융합(late fusion)은 Text-only 대비
  검색 성능을 향상시키는가?

기여는 (1) **라벨링이 필요 없는 썸네일–제목 의미 간극 지표의 정의 및 자동 계산**,
(2) **텍스트–시각 융합의 검색 효과와 gap–순위변화 관계를 검증하는 분석 프레임**, (3) **한국어
YouTube를 대상으로 한 실증 평가**이다. 시각 정보의 검색 활용에 대한 실무적 함의는 §6.4에서
논의한다.

본 연구는 가설, 표집 절차, 평가 지표 및 주요 검정 방법을 결과 관찰 이전에 사전등록하고,
사전등록된 분석과 결과 이후의 탐색적 분석을 구분하여 보고하였다. 본 연구의 주요 관찰은 동일가중
융합이 평균적인 검색 성능을 향상시키지는 않았으나, 관련 영상의 순위를 특히 깊은 순위 영역에서
재배치하는 양상이 나타났다는 점이다. 또한 이러한 순위 변화는 단일한 텍스트–시각 의미 간극
만으로 일관되게 설명되지 않았다.

## Ⅱ. 관련 연구

### 2.1 멀티모달 검색

CLIP[3]은 이미지·텍스트를 대조학습으로 공통 임베딩 공간에 정렬하여, 두 모달리티 간 유사도를
코사인 유사도로 측정할 수 있게 한다. 이를 영상–텍스트 검색에 적용한 프레임 집계 기반
방법[1]과 멀티모달 하이브리드 융합[2]이 제안됐으나, 이들은 시각·텍스트 정보를 통합하되 시각 채널의 **기여
조건**을 주된 분석 대상으로 삼지는 않는다. 한국어 텍스트 검색에는 문장 임베딩 기법[4]에 기반한 다국어 모델을 사용한다.

### 2.2 이미지–텍스트 정합성 측정

CLIPScore[5]는 CLIP 유사도를 캡션 품질의 자동 평가에 사용했고, BLIP[6] 등 통합 비전–언어
모델도 정합성 표현을 제공한다. 본 연구는 **CLIP 기반 이미지–텍스트 코사인 유사도**를, 캡션 품질
평가가 아니라 **검색에서 시각 정보의 기여를 분석하는 변수**로 활용한다.

### 2.3 썸네일과 검색어 적응적 모달 활용

썸네일을 직접 다룬 연구로는 **멀티모달 LLM**(영상→텍스트 설명·썸네일·자막을 통합)으로 **오도성
(misleading) 썸네일을 탐지**한 연구[7]가 있으나, 과제가 오도성 판정, 즉 분류 과제이며 임베딩 기반 검색
랭킹에서 시각 정보의 **기여 조건**을 연속 지표로 설명하는 데 주된 초점을 두지는 않는다.

한편 검색에서 **모달을 언제 활용할지**를 다룬 계열도 있다. 검색어별로 다중 수준 표현의 유효성을
추정해 late fusion 가중을 조정하는 방법[8]과, 모달 간 점수 일치(cross-modal agreement)로 각
검색어에서 활용할 모달을 능동 선택하는 방법[9]이 그것이다. 다만 이들은 검색 **성능을 높이기 위한
적응 가중·모달 선택 메커니즘**을 제안하는 데 초점이 있으며, 정합성의 차이 자체를 시각 기여의
조건 변수로 다루는 것은 본 연구와 목적이 다르다.

### 2.4 연구 공백

요컨대 기존 연구는 주로 **검색 성능**이나 **정합성 자체**를 다루거나[1–6], 모달 활용 여부를
**검색 성능·모달 간 점수 관계에 기반한 적응 메커니즘**으로 조정한다[8,9]. 이와 달리 본 연구는
**썸네일–제목 간 의미적 비정렬 정도(gap)를 영상 수준의 연속 변수로 정의하고, 이를 실제 순위
변화와 연결해 시각 정보의 검색 기여를 분석하는 관점**을 취한다.

## Ⅲ. 연구 방법

전체 처리 과정은 그림 1과 같다. 검색어·코퍼스 구성부터 세 인코더 임베딩, gap 산출,
세 검색 방식과 후기 융합, 그리고 순위 개선(Δrank) 산출·분석까지의 흐름을 나타낸다.

<!-- 최종 HWP: 아래 라우팅을 박스+화살표 도식으로 재작성 — 그림 1.
     핵심: Query와 제목이 각각 mpnet·CLIP-text 두 인코더로 '이중 인코딩'됨을 반드시 시각화. -->
```
[구성]  검색어 경로 : 자동완성 초성 sweep → 기준 기반 큐레이션  ⇒  Query 70 (14×5)
        코퍼스 경로: search + videos.list                        ⇒  Video Corpus 840 (14×60; 제목+썸네일)

[인코더 3종]   mpnet(검색 텍스트, 768d) · CLIP-text(CLIP정렬 다국어 텍스트, 512d) · CLIP-image(썸네일, 512d)

[이중 인코딩 라우팅]
        Query  ─┬─►[mpnet]──────► 검색어 텍스트 임베딩
                └─►[CLIP-text]──► 검색어 CLIP 임베딩
        제목   ─┬─►[mpnet]──────► 제목 텍스트 임베딩
                └─►[CLIP-text]──► 제목 CLIP 임베딩
        썸네일 ────►[CLIP-image]► 썸네일 이미지 임베딩

[채널 계산]
        Text sim   = cos( 검색어 텍스트 , 제목 텍스트 )            → Text Retrieval
        Visual sim = cos( 검색어 CLIP  , 썸네일 이미지 )           → Visual Retrieval
        gap        = 1 − cos( 제목 CLIP , 썸네일 이미지 )  (mean-centered)

[검색·분석]  Text Retrieval + Visual Retrieval ─► Late Fusion(α=0.5) ─► Δrank
             ⇒  RQ1: gap ↔ Δrank 연관   /   RQ2: 검색 성능
```

**그림 1. 처리 과정** (검색어·코퍼스 구성 → 임베딩 → gap 산출 → 검색·융합 → 순위 개선·분석) [results/fig1_pipeline.png/.svg]

### 3.1 임베딩 추출

세 인코더를 역할별로 사용한다(표 1). 썸네일은 CLIP 이미지 인코더로, 검색용 텍스트(제목·검색어)는
다국어 문장 인코더로, gap·시각 채널용 텍스트는 CLIP 이미지 임베딩과 공동 공간에 정렬된 다국어
텍스트 인코더로 인코딩한다.

**표 1. 사용 임베딩 인코더** (모델은 sentence-transformers 제공)

| 역할 | 인코더 | 입력 | 출력 | 용도 |
|---|---|---|---|---|
| 이미지 | `clip-ViT-B-32` | 썸네일 | 512 | 시각 검색·gap의 이미지 표현 |
| CLIP 정렬 텍스트 | `clip-ViT-B-32-multilingual-v1` | 제목·검색어 | 512 | CLIP 이미지와 **같은 공간**에서 gap·시각 검색용 텍스트 표현 |
| 검색 텍스트 | `paraphrase-multilingual-mpnet-base-v2` | 제목·검색어 | 768 | 한국어 텍스트 검색 유사도 |

mpnet은 한국어 검색 유사도, CLIP-text는 이미지와의 공동공간에서 gap·시각 유사도 계산에 쓴다.
따라서 **Text-only 검색 점수와 gap은 서로 다른 표현 공간에서 산출되며, gap을 검색 점수의 일부로
사용하지 않는다**. 구현: 모든 임베딩은 L2 정규화, 유사도는 코사인, 채널 결합 전 검색어별 min–max
정규화를 적용한다.

### 3.2 썸네일–제목 의미 간극(gap)

영상 *i*의 gap은 CLIP 결합 공간에서 모달별 mean-centering을 적용한 썸네일·제목 임베딩의 코사인
유사도를 역변환(1 − cos)하여 정의하는 영상 수준의 비정렬 지표다.

<!-- 최종 HWP: 아래 식을 수식편집기로 정식 조판(식 (1)) -->
$$
\mathrm{gap}_i = 1 - \cos\!\big(\,\mathrm{center}(v^{\mathrm{img}}_i),\ \mathrm{center}(g^{\mathrm{txt}}_i)\,\big) \tag{1}
$$

즉 **gap이 클수록 썸네일과 제목의 표현이 공동공간에서 유사도가 낮다**. 여기서 '의미 간극'은
**인간의 의미 판단에 따른 직접적 의미 차이가 아니라, CLIP 공동 임베딩 공간에서 측정한
썸네일–제목 표현 간 비유사도**를 가리킨다. 본 연구는 이 비정렬 정도가 검색에서 시각 정보의
추가 기여와 관련되는지를 실험으로 검증한다.

여기서 center(·)는 모달별 코퍼스 평균을 차감한 뒤 재정규화하는 전처리로, 임베딩의 전역적 평균
방향 차이(비등방성·모달 간 차이)의 영향을 줄여 **영상별 상대적 비정렬 정도를 비교**하기 위한
것이다[10][11][12].

이 전처리는 **검색 점수·Δrank·qrels를 보기 전에 고정**했으며, 이 표현이 영상별 대응
관계를 반영하는지는 검색 성능이 아니라 **자기매칭 기반 점검(self-matching validation)**으로 사전
확인했다 — 각 영상의 자기 제목–썸네일 정합도를 다른 영상의 제목과 짝지었을 때와 비교하면, 전체
840편 중 **84.6%**에서 자기 조합의 정합도가 더 높았다. raw gap도 민감도 분석으로 병기한다(§4.4).

gap은 추가 라벨링 없이 산출되는 영상 수준 변수로, 검색 단계의 **검색어별 순위 변화(Δrank)**와
결합해 시각 정보의 검색 기여 조건을 분석하는 데 쓴다(§3.3–3.4).

### 3.3 후기 융합 검색

세 검색 방식을 비교한다. 두 채널의 점수 스케일이 달라, 각 검색어에서 전체 코퍼스(840편)의 유사도를
기준으로 min–max 정규화한 뒤 가중합한다.

<!-- 최종 HWP: Late Fusion score 식을 수식편집기로 식 (2)로 조판 -->
```
Text-only   : s_text   = cos(q_txt, d_txt)            (검색 텍스트 인코더)
Visual-only : s_visual = cos(q_clip, d_img)           (텍스트 검색어 ↔ 썸네일, 교차모달)
Late Fusion : score = α·norm(s_text) + (1−α)·norm(s_visual)
```

α는 결과를 보기 전 **동일가중 지점 α=0.5**를 primary로 고정한다. α∈{0.0, 0.1, …, 1.0} grid로
sensitivity를 계산하고, 표 4에는 α≥0.5 구간을, 전체 곡선은 그림 2에
제시하며, 최고 α를 '최적'으로 선택하지 않는다. 후기 융합은 RQ2에서
텍스트 단독 검색과의 성능 차이를 평가하고, RQ1에서는 융합에 따른 영상별 순위 변화(Δrank)를
산출하는 데 사용한다.

### 3.4 gap–순위개선 가설

정답지의 각 (검색어 q, 관련 영상 v)에 대해 순위 개선폭을 정의한다.

<!-- 최종 HWP: Δrank 식을 수식편집기로 식 (3)으로 조판 -->
```
Δrank(v,q) = rank_text(v|q) − rank_fusion(v|q)      (양수 = 융합이 순위 개선)
```

여기서 rank는 **전체 평가 코퍼스(840편) 내 순위**로 정의한다. 검색 성능은 @10으로 평가하지만,
Δrank는 Top-10 밖의 관련 영상까지 포함한 순위 이동을 반영하기 위해 전체 순위를 사용한다.

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
| 평가 검색어 | 70 (14 × 5) |
| 검색어당 pooling 후보(평균) | 23.0 |
| Query–Video 평가 쌍 | 1,607 |
| 평가자 | 3인 (blind·독립) |
| Short 영상 비율 | 12.5% |

### 4.1 평가 코퍼스

YouTube KR `assignable` 카테고리 **14개**를 주제 다양성 확보용 층화 틀로 사용해 **카테고리당
60편 × 14 = 840편**을 수집했다. categoryId는 **표집 기준일 뿐 의미적 정답 레이블이 아니며**,
본 연구의 어느 분석에서도 레이블로 쓰지 않는다. 카테고리당 복수 seed로 `search` 수집 후
`videos.list`의 categoryId로 필터링했으며(relevance · viewCount · date 세 정렬 혼합·채널당 최대 5편·60초 초과·2025-01-01 이후),
이는 확률표본이 아니라 **gap 분산 확보용 카테고리 층화표본**이다. 코퍼스의 Short **12.5%**에
대해서는 non-Shorts 부분표본 민감도 분석으로 영향을 확인하였다(§5.2).

### 4.2 평가 검색어

순환논리를 피하기 위해 검색어는 연구자 창작이나 영상 텍스트에서 파생하지 않고 **YouTube 공개
자동완성(Suggest)**에서 생성하였다. 카테고리명·관련어에 한글 초성을 결합해 후보 pool을 만든
뒤, **사전 정의된 기준**으로 navigational(채널·프로그램·작품·인물·기관명) · category mismatch ·
상품/서비스 · 무의미 후보를 제외하고, 카테고리 내 주제 다양성을 고려해 **카테고리당 5개 × 14 =
70개**를 선정하였다. 검색어 선정은 검색 및 라벨링 전에 완료했으며, 실험 결과에 따라 변경하지
않았다. 따라서 이 검색어 집합은 사용자 검색 빈도의 확률표본이 아니라
**평가용 검색어 집합**이다.

### 4.3 정답지(qrels) 구축

편향을 막기 위해 **Text-only ∪ Visual-only ∪ Late Fusion 각 Top-10의 합집합**(pooling)을 후보
풀로 삼는다. 이는 세 방식이 각각 상위로 올린 관련 후보를 포괄하되, 세 방식 모두에서 낮은
순위인 관련 영상은 누락될 수 있음을 한계로 명시한다(§6.5). 후보 (검색어, 영상) 쌍을 **3인이 blind·독립**으로 3단계(2=관련/1=부분/0=무관)로
라벨링한다. 3단계는 순서형(ordinal) 등급이므로 최종 등급은 **세 판정의 중앙값(median)**으로
집계하도록 사전 고정한다. 평가자 간 일치도는 **Fleiss' κ**(3인 전체)로 보고하고, 평가자 쌍별
**Cohen's κ**를 보조로 제시한다. 최종 qrels에서 관련(등급≥1) 문서가 0개인 검색어는 채점 불가로
제외하고, 제외 수를 카테고리별로 투명 보고한다.

### 4.4 평가 지표 및 통계 검정

지표는 검색 성능(RQ2)에 MRR@10 · NDCG@10 · Recall@10, gap–개선 연관(RQ1)에 Spearman ρ(gap,
median Δrank)를 쓴다. 본 논문은 연구 질문 RQ1·RQ2로 명칭을 통일하며,
각각을 아래 검정으로 확인한다.

- **RQ2 검정(융합 효과)**: 유의성은 Text-only 대 Fusion(α=0.5)의 검색어별 reciprocal rank@10에
  대한 **paired Wilcoxon signed-rank test**(p<0.05)를 primary로 쓴다(RR@10이 이산·비정규
  분포라 비모수). 효과의 크기는 **MRR@10 · NDCG@10 · Recall@10의 절대 변화량과 부트스트랩 95%
  CI(1,000회)**로 별도 보고하고, Wilcoxon의 짝지음 효과 크기로 **rank-biserial correlation**을
  병기한다. 즉 유의성과 효과 크기를 분리하며, 임의의 개선 임계값은 두지 않는다. 융합 가중치 α의
  민감도는 사전등록 밖 탐색 분석으로 별도 보고한다.
- **RQ1 검정(gap–개선 연관)**: 영상별 gap과 검색어별 Δrank의 관측 단위를 맞추기 위해 영상별 Δrank를
  **중앙값**으로 집계한다(극단적 순위 변화의 영향 완화; 영상이 카테고리에 내포되어 완전한
  독립은 주장하지 않는다). **Primary**는 `Spearman ρ(gap, median Δrank)`의 유의성(ρ>0)과 **부트스트랩
  95% CI**, **Robustness**는 raw/centered 민감도 · between/within 분해 · cluster-robust 회귀, **Exploratory**는
  카테고리별 분석이며, 귀무 결과의 정보성을 평가하기 위해 **MDES**를 함께 보고한다. 상관은 예측의 직접 증거가 아니므로
  결과를 "예측"이 아니라 "연관"으로 해석한다.
- **Short 강건성**: 코퍼스의 12.5%가 Short이므로, Short 유병률을 보고하고 **Short 제외
  부분표본(non-Shorts)으로 RQ1·RQ2를 재실행**해 결과가 Short 포함에 좌우되지 않음을
  확인한다. Short 수가 충분하면 Short/일반 서브그룹 비교를 탐색적으로 병기한다.

## Ⅴ. 결 과

### 5.1 데이터셋 및 라벨링 신뢰도

전체 라벨링 단위는 70개 검색어에 걸친 **1,607개 (검색어, 영상) 쌍**(검색어당 평균 약 23개)이다.
세 라벨러 간 일치도를 평가한 결과 **Fleiss' κ는 0.486**(3인 전체)였고, 쌍별 단순 일치율은
**77.2–77.8%**였다. 라벨러
쌍별 **Cohen's κ는 0.462–0.523** 범위로, 특정 라벨러에 불일치가 집중되는 양상은 관찰되지
않았다. 전체 사례의 **69.0%**는 세 라벨러가 동일 등급을 부여하였고, 극단적 불일치(0과 2)는 **13.8%**였다. 불일치는 일부 의미 범위가 넓거나 관련성
경계가 모호한 검색어에서 관찰되었다. 최종 관련도는 세 판단의 **중앙값**으로 결정하였다.

최종 관련도가 0인(관련 영상 0개) **7개 검색어를 사전 정의된 zero-relevance 규칙에 따라 제외**하여
**63개 검색어**로 검색 평가를 수행하였다. 제외된 7개는 6개 카테고리에 분산(음악 2, 그 외 각 1)되어
특정 카테고리에 편중되지 않았다. 검색어당 관련 영상은 평균 **7.0개**(중앙값 6)였다.

### 5.2 검색 성능과 융합 효과 (RQ2)

**표 3. 시스템별 검색 성능** (63개 검색어, macro-average)

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|---|---|---|---|
| Text-only | 0.690 | 0.556 | 0.627 |
| Visual-only | 0.432 | 0.301 | 0.316 |
| Late Fusion (α=0.5) | 0.673 | 0.561 | 0.637 |

**썸네일 단독(Visual-only)은 텍스트 검색보다 낮은 성능을 보였다**(MRR 0.432 vs 0.690). 사전등록된
**동일가중 후기 융합(α=0.5)은 텍스트 대비 유의한 개선을 보이지 않았다** — 검색어별 RR@10의
Wilcoxon 검정 결과 ΔMRR = −0.016(부트스트랩 95% CI [−0.089, +0.055]), p=0.761이었다. 짝지음
효과크기인 rank-biserial r = −0.06으로, 융합과 텍스트 단독 간 차이가 크지 않았다.
NDCG·Recall의 변화도 작아 신뢰구간이 모두 0을 포함하였다(ΔNDCG +0.005 [−0.057, +0.070], ΔRecall
+0.010 [−0.079, +0.100]). 이 표본(63개 검색어)은 RR@10 기준 약 0.11(dz≈0.35)의 개선을 80% 검정력으로
탐지할 수 있는 규모이므로, 본 결과는 적어도 이 정도 규모의 개선은 뒷받침하지 않는다.

**가중치 민감도.** 사전등록 밖의 α를 탐색적으로 비교하면(표 4), **세 지표 모두 α=0.7(텍스트
가중 70%·시각 30%)에서 가장 높았으며, 이때 성능은 Text-only(α=1.0)와 동일가중 융합(α=0.5)보다 모두
높았다.** 다만 이는 결과를 본 뒤 검토한 탐색적 sensitivity
분석이며 다중비교를 통제하지 않았으므로 확증적으로 해석하지 않는다.

**표 4. 융합 가중치 α에 따른 검색 성능**(α=1.0=Text-only, 탐색적)

| α | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 1.0 |
|---|---|---|---|---|---|---|
| MRR@10 | 0.673 | 0.677 | 0.701 | 0.695 | 0.698 | 0.690 |
| NDCG@10 | 0.561 | 0.584 | 0.594 | 0.587 | 0.585 | 0.556 |
| Recall@10 | 0.637 | 0.681 | 0.698 | 0.671 | 0.668 | 0.627 |

<!-- 최종 HWP: results/fig2_alpha_curve.png 삽입 -->
**그림 2. 융합 가중치 α에 따른 검색 성능 변화**(탐색적) [results/fig2_alpha_curve.png]

**순위 수준 분석.** 융합은 관련 영상의 전체 코퍼스 순위를 재배치했으며, 검색어별 median Δrank는
+1(양수 59%)이었다. 변화가 어디에서 나타났는지 관련 (query, video) 쌍의
Δrank(=rank_text − rank_fusion@0.5, 양수=융합이 순위 상승)를 Text 순위 구간별로 보면(표 5), Text
순위가 1–10위인 관련 영상의 median Δrank는 **−2.0(개선 24%)** 인 반면, 11위 이후의 관련 영상에서는
대부분 양(+)의 Δrank를 보였다(11–50위 93%, 51위 이후 100%). 상위 10위 진입/이탈은 진입 103·이탈
93(순증 +10)이었고, MRR@10에 직접 반영되는 첫 관련 결과의 순위 변화는 개선 14건·악화 11건·동일
33건(양쪽 모두 Top-10에 첫 관련 결과가 있는 58개 검색어)이었다.

**표 5. Text 순위 구간별 Δrank**(양수=융합이 순위 상승; 관련 쌍 기술통계)

| Text 순위 구간 | n | median Δrank | 개선(>0) 비율 |
|---|---|---|---|
| 1–10 | 253 | −2.0 | 24% |
| 11–50 | 132 | +13.0 | 93% |
| 51–100 | 18 | +53.5 | 100% |
| 101+ | 37 | +201.0 | 100% |

**카테고리별 융합 효과.** 카테고리별로는 융합 효과의 방향이 상이했으며, 뉴스·여행·과학기술
등에서 양(+), 코미디·노하우 등에서 음(−)의 경향이 관찰되었다. 다만 카테고리당 검색어 수가 적어
(3~5개) 탐색적 결과로 해석한다.

**Short 강건성.** Short를 제외한 부분표본(735편)으로 재실행해도 결론은 유지되었다 — 동일가중
융합은 유의한 개선을 보이지 않았고(ΔMRR +0.033, Wilcoxon p=0.30), 아래 gap–순위변화 관계도
유의하지 않았다(centered ρ=−0.06). 따라서 본 결과가 Short 포함 여부에 크게 좌우되지는 않은 것으로 나타났다.

### 5.3 의미 간극과 순위 변화의 관계 (RQ1)

**Primary는 유의하지 않았다.** 영상 수준에서 category-centered gap과 영상당 median Δrank의
Spearman 상관은 **ρ=−0.049(95% CI [−0.175, +0.080], p=0.42)**로, 사전등록된 관계(ρ>0)는
확인되지 않았다. 이 표본(n=270)은 |ρ|≥0.17을 80% 검정력으로 탐지할 수 있으므로, 본 자료는
적어도 |ρ|≈0.17 이상의 관계는 뒷받침하지 않는다.

**Robustness — raw 상관은 카테고리 간 차이에 민감했다.** raw gap에서는 약한 음의 상관이 관찰되었으나
(ρ=−0.226, p<0.001), 이를 **카테고리 간(between; 카테고리 평균값끼리의 상관)과 카테고리 내
(within; 각 변수에서 카테고리 평균을 제거한 뒤의 상관)**으로 분해하면 between-category 상관은
강한 음의 상관(ρ=−0.679, 카테고리 14개 평균값으로 계산), within-category 상관은 약했다
(ρ=−0.120). 즉 raw association은 카테고리별 평균 차이의 영향을 받은 것으로 해석할 수 있다. 카테고리별 within 상관은 대부분
비유의하며 유의한 두 카테고리(과학기술 −0.46, 스포츠 +0.52)조차 부호가 반대여서, **카테고리
내부의 gap–Δrank 관계는 일관되지 않았다**.

**Additional robustness — 명세에 따라 방향이 뒤집혔다.** 사전등록된 2차 분석(카테고리 통제
cluster-robust 회귀, n=440 검색어–영상 쌍)에서는 gap 계수가 유의한 양(+)으로 나타났으나(p=0.024), 이는
within 분석의 음(−)의 상관과 방향이 달랐다. 또한 14개 카테고리 중 8개에서만 양의 상관이 나타나
방향도 일관되지 않아, gap과 순위 변화의 관계는 분석 명세에 따라 달라지는 것으로 나타났다. 따라서
**단일 의미 간극 지표만으로 영상 수준에서 시각정보의 검색 기여를 설명하는 데에는 한계가 있었다.**

<!-- 최종 HWP: 그림 3 = centered gap(x) vs 영상당 median Δrank(y) 산점도(카테고리 색상 최소).
     binned median 평평(ρ≈0). results/fig3_gap_scatter.png 삽입 -->
**그림 3. 의미 간극(centered gap)과 영상당 median Δrank의 관계**(ρ≈0) [results/fig3_gap_scatter.png]

## Ⅵ. 논 의

### 6.1 썸네일 시각정보와 융합의 검색 효과 (RQ2)

썸네일 단독 검색이 텍스트보다 낮았던 것(§5.2)은, CLIP 기반 썸네일과 검색어의 유사도가 이
환경에서 텍스트 메타데이터를 대체할 만큼 강한 검색 신호가 아니었음을 보여준다. 가능한 원인으로는
썸네일의 클릭 유도 특성, OCR 미지원, 다국어 CLIP의 한국어 표현 한계 등을 생각할 수 있으나, 본
연구에서는 이를 직접 검증하지 않았다. 동일가중 후기 융합(α=0.5)이 개선을 보이지 못한 것도 이와 부합한다. 이는 시각 채널의 상대적 신호 강도가
텍스트보다 낮은 상황에서 동일가중 결합이 텍스트 신호를 희석했을 가능성을 시사하며, 인과를 직접
입증한 것은 아니다.

그러나 융합은 검색 결과의 구성 자체에는 변화를 주었다. 전체 순위의 이동이 상위 결과의 품질
개선으로 반드시 이어지는 것은 아니며, 본 결과에서 그 효과는 주로 순위 구성 변화에 국한되었다(§5.2,
표 5). 다만 이 심층 순위 관찰은 Top-10 pooling으로
구성된 qrels 내 관련 영상에 한정된 기술통계임을 고려해야 한다. 이러한 순위 재배치는 상위 노출을
직접 개선하지는 않으나, recall 지향
검색이나 재순위(re-ranking) 단계에서는 활용될 여지가 있다.

### 6.2 의미 간극의 설명력 (RQ1)

사전등록된 centered gap과 순위 변화의 관계는 유의하지 않았다(§5.3). raw gap에서 관찰된 약한
음의 상관은 카테고리 간 차이(between)에 주로 기인하였고 카테고리 내부(within)에서는 약화되었다.
gap이 크다는 것은 썸네일과 제목이 표현 공간에서 멀다는 것을 의미하지만, 그 거리가 영상 수준에서
융합에 의한 순위 개선으로 이어지지는 않았다. 또한 분석 명세에 따라 관계의 방향도 달라져, 단일 gap
지표의 설명력이 일관되지 않았다. 따라서 **단일 의미 간극 지표만으로 시각정보의 검색 기여 조건을
설명하기에는 한계가 있었다.** 즉 "하나의 gap 값으로 시각 기여를 설명할 수 있는가"라는 물음에 대해, 본
데이터·설정에서는 충분하지 않다는 답을 얻었다.

### 6.3 카테고리 이질성과 탐색적 관찰

융합 효과의 방향은 카테고리에 따라 달랐고(뉴스·여행·과학 등 +, 코미디·노하우 등 −), 시각을
낮은 가중으로 결합한 α=0.7에서 세 지표가 가장 높았다(§5.2, 표 4). 이는 일부 카테고리에서
시각정보를 포함한 융합 효과가 다르게 나타날 **가능성**을 시사하지만, 그 원인을 직접 검증한 것은
아니다. 다만 카테고리당 표본이 작고(3~5 검색어) α 선택이 사후적이며 다중비교를 통제하지 않았으므로,
확증이 아니라 후속 연구에서 검증할 가설로 남긴다.

### 6.4 실무적 함의

당초 구상했던 "gap 기반 시각 임베딩 선별 색인"(낮은 gap 영상은 시각 임베딩 생략)은 본 결과로
뒷받침되지 않는다 — 동일가중 융합이 평균 성능을 개선하지 못했고 gap도 기여 영상을 안정적으로
식별하지 못했기 때문이다. 오히려 본 결과는, 텍스트 메타데이터 기반 영상 검색에
단순 후기 융합으로 썸네일 유사도를 추가하는 것만으로는 일관된 성능 개선을 기대하기 어렵다는 점을 시사한다.
탐색 결과만 놓고 보면, 시각정보를 텍스트보다 낮은 가중의 추가 정보로 결합하는 설정이 상대적으로
유망해 보인다. 시각정보가
언제 도움이 되는지를 판별하려면 단일 gap보다 풍부한 신호가 필요하다(§6.5). 따라서 실무적
결론은 배포 가능한 규칙이라기보다 **적용상의 주의와 후속 연구 방향**이다.

### 6.5 한계

(1) 시각 인코더는 OCR을 하지 않아 **썸네일 내 한국어 자막을 판독하지 못하며**, gap·시각 유사도는
다국어 CLIP의 한국어 품질과 mean-centering 전처리에 의존한다. (2) 평가 코퍼스는 확률표본이 아닌
카테고리 층화표본이며 검색어·표본 규모가 제한적이다(대표성·일반화는 그 범위로 한정). (3) 코퍼스에
Short가 12.5% 포함되어 있어(§4.1) 표본 구성의 차이가 해석에 영향을 줄 가능성이 있으나, Short 제외
분석에서도 주요 결론은 유지되었다(§5.2). (4) qrels는 세
방식의 Top-10 pooling으로 구축되어 모든 방식에서 낮은 순위인 관련 영상은 누락될 수 있다(pooling
bias). 이에 따라 Recall이 과소추정될 수 있고, 낮은 순위 관련 영상의 누락으로 Δrank 분석의 관련
영상 집합도 완전하지 않을 수 있다. (5) 카테고리별·α 분석은 탐색적(소표본·다중비교 미통제)이다.

## Ⅶ. 결 론

본 연구는 한국어 YouTube 환경에서 썸네일 시각정보가 텍스트 기반 영상 검색에 어떤 변화를
가져오는지, 그리고 그 변화를 썸네일–제목 의미 간극으로 설명할 수 있는지를 분석하였다.

썸네일 단독 검색은 텍스트보다 약했고 동일가중 융합도 평균적으로 개선하지 못했다. 다만 융합은
관련 영상의 전체 순위를 변화시켰으며, 이 변화는 상위 10위 내 첫 관련 결과를 안정적으로 개선하기보다
그 이후 깊은 순위의 후순위 관련 영상을 재배치하는 양상으로 나타났다. 이는 **검색 결과의
순위 구성 변화와 상위 결과의 효과성이 서로 다른 축**임을 보여준다. 또한 융합 효과의 방향은
카테고리에 따라 달라, 평균 성능만으로는 시각정보의 기여 양상을 충분히 설명하기 어려웠다.

사전등록된 centered gap과 순위 변화의 관계는 확인되지 않았다. raw 상관은 카테고리 수준의
이질성에 영향을 받았고 카테고리 내부에서도 일관되지 않아, **단일 의미 간극 지표만으로 시각정보의
검색 기여 조건을 설명하기는 어려웠다.**

따라서 본 결과에서 썸네일은 텍스트 검색을 대체하는 강한 신호라기보다 융합 과정에서 검색 결과의
순위 구성에 변화를 줄 수 있는 정보로 관찰되었으나, 본 연구의 설정에서는 그 기여를 안정적으로
예측하는 단순한
지표를 확인하지 못했다. 향후에는 단일 gap을 넘어 객체·장면·OCR 등 구체적인 시각 특성과 검색어 특성의 상호작용을 고려하여,
어떤 조건에서 시각정보가 검색에 기여하는지를 검증할 필요가 있다. 아울러 다양한 검색 환경에서 이
패턴의 재현성을 확인할 필요가 있다.

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
