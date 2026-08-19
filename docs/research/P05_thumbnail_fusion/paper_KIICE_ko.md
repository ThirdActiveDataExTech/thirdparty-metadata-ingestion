<!-- 한국정보통신학회 춘·추계 종합학술대회 제출용 초안 (KIICE format).
     본문 2단·국문 함초롱바탕 등 조판은 HWP 양식에서 적용. 이 파일은 내용 원고.
     ⟦DATA⟧ = 라벨링·실험 후 실수치로 교체. 저자/소속/과제문구는 [ ] 플레이스홀더.
     ⟦결과 후 재작성⟧ = §6.4·§7의 '낮은 gap→기여 작음/제거 시 손실 작음' 조건부 서술은
     RQ1 결과가 그 방향이 아니면 재작성 필요(해당 절에 인라인 마커 있음). -->

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
규명되지 않았다. 본 연구는 이 개선이 나타나는 조건을 설명할 **후보 변수**로, 라벨링 없이 자동
계산되는 연속 지표인 **썸네일–제목 의미 격차**(넓게는 시각–텍스트 의미 격차; visual–text
semantic gap, 이하 gap)를 제안한다.
gap은 CLIP 공동 임베딩 공간에서 mean-centering 후 썸네일–제목 코사인 유사도를 역변환한(1−cos)
영상 수준의 비정렬 지표로, 값이 클수록 두 표현이 공동공간에서 덜 유사하며 임베딩 추출의
부산물로 얻어진다. 한국어 YouTube 영상 ⟦DATA:840⟧편과 검색어
⟦DATA:70⟧개로 CLIP 이미지 임베딩과 다국어 텍스트 임베딩의 late fusion을 평가하여, **융합이
text-only 대비 검색 성능을 향상시키는지, 그리고 gap이 융합에 의한 순위 개선과 관련되는지를
실증적으로 검증한다** ⟦DATA⟧. 본 연구의 기여는 새로운 융합 기법이 아니라 시각 정보의 기여
조건을 정량적으로 다루는 지표를 제안한 데 있으며, 이는 gap이 높은 영상에 시각 임베딩을 선별
적용하는 **메타데이터 검색 플랫폼의 적응형 확장** 가능성을 탐색하는 근거가 될 수 있다.

## ABSTRACT

Video metadata retrieval relies mostly on textual fields such as titles, leaving the visual
information in thumbnails largely unused. While fusing visual and textual signals is known to
improve retrieval, whether this improvement is uniform across videos or arises only under
specific conditions remains unclear. As a candidate variable for this condition, we propose a
continuous, label-free metric—the *thumbnail–title semantic gap* (broadly, a visual–text semantic
gap)—defined as an inverse transform (1−cos) of the mean-centered thumbnail–title cosine similarity
in the CLIP joint space—higher values indicating less similarity—and obtained as a by-product
of embedding extraction. On
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
메타데이터**에 의존한다. 반면 사용자가 클릭 판단에 크게 활용하는 **썸네일의 시각 정보**는,
텍스트 메타데이터와 달리 검색 색인에 직접 활용하려면 **추가적인 시각 임베딩 계산**이 필요하다.
시각 채널을 텍스트와 결합(late fusion)해 검색 성능을
높이는 접근은 여러 차례 보고돼 왔으나[1][2], 시각 정보의 기여가 **어떤 영상에서 상대적으로
크게 나타나는지**에 대한 분석은 제한적이다. 즉 기존 연구가 주로 "시각 정보를 더하면 검색이
좋아지는가"를 물었다면, 본 연구는 "그 개선이 **어떤 영상에서** 나타나는가", 나아가 "따라서 시각
임베딩을 **모든 영상에 계산·저장해야 하는가**"를 묻는다. 시각 임베딩의 계산·저장은 비용이 들어,
이 구분에 따라 메타데이터 검색 플랫폼의 색인 확장 설계가 달라지기 때문이다.

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
(2) **gap과 융합에 의한 검색 순위 개선의 관계 분석**(시각 정보가 "언제" 검색에 기여하는가),
(3) **한국어 YouTube 환경에서의 실증**이다. 즉 새로운 융합 기법이 아니라 **시각 정보의 기여
조건을 다루는 지표와 분석 틀**을 제안한다. gap 기반으로 시각 임베딩을 선별 적용하는 등의
실무적 활용 가능성은 Ⅵ.4에서 논의한다.

## Ⅱ. 관련 연구

### 2.1 멀티모달 검색

CLIP[3]은 이미지·텍스트를 대조학습으로 공통 임베딩 공간에 정렬해, 결합 공간의 코사인
유사도를 정합성의 표준 지표로 확립했다. 이를 비디오–텍스트 검색에 적용한 프레임 집계 기반
방법[1]과 멀티모달 하이브리드 융합[2]이 제안됐으나, 대규모 프레임·자막 중심이며 시각 채널의 **기여
조건**은 분석하지 않는다. 한국어 텍스트 검색은 다국어 문장 임베딩[4]을 기반으로 한다.

### 2.2 이미지–텍스트 정합성 측정

CLIPScore[5]는 CLIP 유사도를 캡션 품질의 자동 평가에 사용했고, BLIP[6] 등 통합 비전–언어
모델도 정합성 표현을 제공한다. 본 연구는 **CLIPScore와 동일한 코사인 정합성 계산**을, 캡션
품질 평가가 아니라 **검색에서 시각 정보의 기여 조건을 분석하는 변수**로 재해석한다.

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

## Ⅲ. 제안 방법

제안 방법의 전체 처리 과정은 그림 1과 같다. 쿼리·코퍼스 구성부터 세 인코더 임베딩, gap 산출,
세 검색 방식과 late fusion, 그리고 순위 개선(Δrank) 산출·분석까지의 흐름을 나타낸다.

<!-- 최종 HWP: 아래 라우팅을 박스+화살표 도식으로 재작성 — 그림 1.
     핵심: Query와 제목이 각각 mpnet·CLIP-text 두 인코더로 '이중 인코딩'됨을 반드시 시각화. -->
```
[구성]  쿼리 경로 : 자동완성 초성 sweep → curation → 결정적 표집  ⇒  Query 70 (14×5)
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

**그림 1. 제안 방법의 전체 처리 과정** (쿼리·코퍼스 구성 → 임베딩 → gap 산출 → 검색·융합 → 순위 개선·분석)

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
높이기 위해 사용한다. **구현 세부**: 모든 임베딩은 L2 정규화하며, 유사도는 코사인,
채널 결합 전 쿼리별 min–max 정규화를 적용한다. 텍스트는 원문 그대로 인코딩한다.

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

여기서 center(·)는 모달별 코퍼스 평균을 차감한 뒤 재정규화하는 전처리로, CLIP 계열 임베딩의
전역 편향(비등방성·모달별 평균 방향 차이)이 개별 영상의 썸네일–제목 유사도에 미치는 영향을
줄인다[10][11][12].

이 전처리는 **어떤 retrieval 점수·Δrank·qrels도 보기 전에 고정**했으며, 그 적절성은 검색 성능이
아니라 **자기매칭 기반 타당성 점검(self-matching validation)**(각 제목이 무작위 썸네일보다 자기
썸네일과 더 정합한지)으로 사전 점검했다. raw gap도 민감도 분석으로 병기한다(§4.4).

gap은 라벨링 없이 전체 코퍼스에 자동 적용되는 임베딩 추출의 부산물이라 추가 비용이 없다. 또한
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

여기서 rank는 **전체 평가 코퍼스(⟦DATA:840⟧편) 내 순위**로 정의하고, Text-only·Fusion 두 방식
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
| 검색 영상 코퍼스 | ⟦DATA:840⟧ (14 × 60) |
| 평가 쿼리 | ⟦DATA:70⟧ (14 × 5) |
| 쿼리당 pooling 후보(평균) | ⟦DATA⟧ |
| Query–Video 평가 쌍 | ⟦DATA⟧ |
| 평가자 | 3인 (blind·독립) |
| Short 영상 비율 | ⟦DATA:12.5%⟧ |

### 4.1 평가 코퍼스

YouTube KR `assignable` 카테고리 **14개**를 주제 다양성 확보용 층화 틀로 사용해 **카테고리당
60편 × 14 = ⟦DATA:840⟧편**을 수집했다. categoryId는 **표집 기준(Sampling Anchor)일 뿐 semantic
ground truth가 아니며**, 본 연구의 어느 분석에서도 레이블로 쓰지 않는다. 절차: 카테고리당 복수 seed로 `search`
수집 → `videos.list`의 categoryId로 사후 필터링, 정렬 3혼합(relevance·viewCount·date), 채널당
최대 5편, seed 간 round-robin. **60초 초과 영상만 수집**, 게시일 2025-01-01
이후. 이는 확률표본이 아니라 **gap 분산 확보용 카테고리 층화표본**이다. 코퍼스에는 Short(세로형
단편)가 **12.5% 포함**되며, 이를 is_short로 라벨해 유병률 보고와 non-Shorts 민감도 분석에
사용한다(§4.4·§6.5).

### 4.2 평가 쿼리

쿼리는 연구자 창작이나 영상 텍스트에서 파생하지 않고(순환논리 회피), **YouTube 공개
자동완성(Suggest)** 에서 생성한다. 각 카테고리명과 관련어(카테고리당 1~2개)에 **한글 초성
자음을 결합한 질의**를 자동완성에 입력해 반환된 추천 검색어를 후보 pool로 수집하고, **사전
등록된 curation 규칙**으로 navigational(채널/프로그램)·category mismatch·상품·서비스
쿼리를 제외한다(후보별 제외 사유 전량 기록). 이어 eligible pool에서 **고정 해시 기반 결정적
표집**(비콘텐츠·근접중복 제거 포함)으로 **카테고리당 5개 × 14 = ⟦DATA:70⟧개**를 선정한다.
쿼리는 retrieval 실험 전에 확정(freeze)하며 성능을 보고 바꾸지 않는다. 따라서 본 연구의 쿼리
집합은 사용자의 실제 검색 빈도를 추정하는 확률표본이 아니라, **플랫폼에서 관찰 가능한 검색
관심사의 후보를 구성하기 위한 평가용 쿼리 집합**이다.

### 4.3 정답지(qrels) 구축

편향을 막기 위해 **Text-only ∪ Visual-only ∪ Late Fusion 각 Top10의 합집합**(pooling)을 후보
풀로 삼는다. 후보 (쿼리, 영상) 쌍을 **3인이 blind·독립**으로 3단계(2=관련/1=부분/0=무관)로
라벨링한다. 3단계는 순서형(ordinal) 등급이므로 최종 등급은 **세 판정의 중앙값(median)** 으로
집계하도록 사전 고정한다. 등급 폭이 최대인 쌍(0과 2 공존)은 감사 로그로 남긴다.
평가자 간 일치도는 **Fleiss' κ**(3인 전체)로 보고하고, 평가자 쌍별 **Cohen's κ**를 보조로
제시한다. 최종 qrels에서 관련(등급≥1) 문서가 0개인 쿼리는 채점 불가로 제외하며, **전체 쿼리
→ zero-relevance 제거 → 최종 평가 쿼리 수를 카테고리별로 투명 보고**한다. 이는 독립 구성한
쿼리와 코퍼스의 정합성에 대한 사후 진단 자료이기도 하다.

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
  쿼리 수준 Δrank의 **관측 단위를 일치**시키기 위해 영상별 Δrank를 하나로 집계한다(한 영상에
  여러 쿼리가 붙어도 관측치 1개 → 독립성 확보). 집계는 **중앙값(median)** 을 쓰며, 이는 특정
  쿼리에서 나타나는 극단적 순위 변화의 영향을 줄이기 위함이다. 분석은 세 층으로 구분한다. **Primary**:
  `Spearman ρ(gap, median Δrank)`의 유의성(ρ>0, p<0.05)과 **부트스트랩 95% CI**. **Robustness**:
  카테고리 내 stratified 상관과 raw vs centered gap 민감도. **Exploratory**: 카테고리 교란을
  통제하는 cluster-robust 회귀와, gap 상·하위군 간 효과 크기 Cohen's d. 귀무 결과 시 표본의
최소탐지효과(MDES)로 해석을 보강한다.
  상관 유의성은 예측력의 직접 증거가 아니므로, 본 연구는 결과를 "예측"이 아니라 "연관"으로
  해석한다.
- **Short 강건성**: 코퍼스의 12.5%가 Short이므로, Short 유병률을 보고하고 **Short 제외
  부분표본(non-Shorts)으로 RQ1·RQ2를 재실행**해 결과가 Short 포함에 좌우되지 않음을
  확인한다. Short 수가 충분하면 Short/일반 서브그룹 비교를 탐색적으로 병기한다.

## Ⅴ. 결과 ⟪실험 후 작성⟫

### 5.1 전체 성능 (RQ2)

**표 3. 검색 성능**

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|---|---|---|---|
| Text-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| Visual-only | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |
| **Late Fusion (α=0.5)** | ⟦DATA⟧ | ⟦DATA⟧ | ⟦DATA⟧ |

Wilcoxon(Fusion vs Text, 쿼리별 RR@10): ⟦DATA: stat, p⟧ (부트스트랩 95% CI ⟦DATA⟧).

### 5.2 gap과 순위 개선의 연관 (RQ1)

**Primary** — Spearman ρ(gap, 영상당 median Δrank) = ⟦DATA⟧ (95% CI ⟦DATA⟧, p=⟦DATA⟧).
**Robustness** — 카테고리 stratified 양(+)상관 비율 ⟦DATA⟧, raw gap 민감도 ⟦DATA⟧.
**Exploratory** — cluster-robust 회귀 gap 계수 ⟦DATA⟧, gap 상·하위군 Cohen's d ⟦DATA⟧.
gap과 median Δrank의 관계는 그림 2에 산점도로 제시한다.

<!-- 최종 HWP: 그림 2 = gap(x) vs 영상당 median Δrank(y) 산점도. 점=영상, Spearman ρ와
     회귀 추세선(또는 95% CI) 표기, 카테고리 색상은 최소화. 결과 산출 후 생성 -->
**그림 2. 썸네일–제목 의미 격차(gap)와 검색 순위 개선(median Δrank)의 관계** ⟦결과 후 생성⟧

### 5.3 조건별 분석

쿼리 유형·길이·gap 수준별 융합 개선폭 ⟦DATA⟧. gap 높음에도 개선 없는 반례를 그림 3에 함께
제시한다.

<!-- 최종 HWP: 그림 3 = 높은 gap인데 Δrank≤0인 익명화 사례 2~3건. 도식(실제 썸네일 미사용)
     — 썸네일 도식 아이콘 + 제목(익명) + gap 값 + Text/Fusion 순위. 결과 산출 후 생성 -->
**그림 3. 높은 gap에도 순위 개선이 없는 반례**(익명화 도식) ⟦결과 후 생성⟧

## Ⅵ. 논 의

### 6.1 융합은 실제로 효과가 있었는가 (RQ2)

전체 성능(§5.1) 관점에서 late fusion이 text-only 대비 검색을 개선했는지를 논한다 ⟦DATA⟧.
전체 평균 성능은 **시각 정보의 전반적 유용성**을 보여주는 지표이며(RQ2), 본 연구는 이에 더해
**영상별 개선 차이를 설명하는 조건**을 분석한다(RQ1). 두 질문은 상호 보완적이다 — RQ2는 시각
채널이 전반적으로 유용한지를, RQ1은 그 유용성이 어떤 영상에 집중되는지를 다룬다.

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

<!-- ⟦결과 후 재작성⟧ 이 절은 "낮은 gap → 시각 기여 작음"을 전제로 한 조건부 서술이다.
     RQ1 결과가 그 방향(gap↑일수록 Δrank↑, gap↓ 영상은 기여 작음)이 아니면 이 절 전체를
     결과에 맞게 재작성할 것(선별 적용 논리가 성립하지 않을 수 있음). -->
낮은 gap 영상에서 시각 임베딩의 기여가 작음이 확인된다면, 그런 영상에는 시각 임베딩 계산·
저장을 생략하고 높은 gap 영상에만 선별 적용하여 **메타데이터 검색 플랫폼의 색인을 비용
효율적으로 확장**하는 방향을 탐색할 수 있다. 즉 gap은 "모든 영상에 시각 임베딩을 넣을
것인가"라는 색인 설계 결정에 정량적 검토 기준을 제공한다. 다만 실제 선별(임계값·분류 성능)의
검증은 본 연구 범위 밖이며 향후 과제다.

### 6.5 한계

(1) 시각 인코더는 OCR을 수행하지 않아 **썸네일 내 한국어 자막 텍스트를 판독하지 못하므로**,
시각 신호와 gap은 썸네일의 시각적 장면 및 비문자적 시각 정보에 국한된다. (2) gap은 정렬된 다국어 CLIP 인코더의
한국어 품질과 mean-centering 전처리에 의존한다. (3) 평가 코퍼스는 확률표본이 아닌 카테고리
층화표본이다(대표성 주장은 그 범위로 한정). (4) 코퍼스는 short-form(Short)을 **12.5% 포함**한다;
is_short로 라벨해 유병률·non-Shorts 민감도로 통제하나(§4.4), Short의 썸네일은 일반 썸네일과
특성이 달라 gap 해석에 영향을 줄 수 있다. (5) primary 분석은
**상관**이며 인과가 아니다. (6) qrels는 세 검색 방식의 Top-10 pooling으로 구축되므로, **모든
방식에서 낮은 순위에 있는 관련 영상은 라벨링되지 못해 평가에서 누락될 수 있다**(pooling bias).
이는 Recall을 과소추정할 수 있고, gap–Δrank 분석도 어느 한 방식에서라도 Top-10에 든 영상으로
제한된다.

## Ⅶ. 결 론

<!-- ⟦결과 후 재작성⟧ "낮은 gap 영상에서 시각 임베딩 제거 시 성능 손실이 작음을 확인하면…"은
     조건부 서술. RQ1 결과가 그 방향이 아니면 이 문장과 §6.4를 함께 결과에 맞게 조정할 것. -->
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
