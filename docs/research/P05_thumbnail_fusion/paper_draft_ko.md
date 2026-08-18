# [논문 초안 · 한국어 · Analysis 중심 리라이팅]
# 썸네일은 언제 검색에 도움이 되는가: 한국어 YouTube에서 시각-텍스트 의미 격차 분석

> **버전**: v3.3 (2026-08-14) — v3.2 이후 [PREREGISTRATION.md](PREREGISTRATION.md) 갱신 반영.
> v3.2 반영: **gap = centered**, 코퍼스 840(14×60, Shorts만 제외), dev/eval 분리,
> categoryId=Sampling Anchor, 융합 α=0.5 primary + α grid, H2 다층 구조.
> **v3.3 추가 갱신**: (1) **쿼리 생성 = 초성(jamo) sweep**(음절 sweep의 단일모음 coverage 결함
> 수정, §PREREG 2026-08-14b) → **카테고리별 MD5+content-filter 표집**(3-way audit로 medoid 대비
> 선택), (2) **평가 쿼리 N=70(14×5)**, (3) **라벨링 3인 median-of-3**(Cohen κ + 완전3인시
> Fleiss κ; 기존 2인·합의 규칙은 백스톱), (4) **한계에 OCR 미수행(썸네일 한국어 자막 미판독)** 추가.
> 프레임(When-does-it-help 분석)은 유지. **원본 v2(영문) 초안 보존**(비교/롤백용).
> **상태**: 초안 (결과 §6~9는 실험 후) — `[DATA: ...]`는 실험 후 실수치로 교체.
> **분량 목표**: 학술대회 단편, **최대 5페이지**.
> **설계 고정**: 가설·표집·평가·분석 방법은 [PREREGISTRATION.md](PREREGISTRATION.md)에
> 실험 전 고정됨.

---

## 제목 (Title)

**국문:** 썸네일은 언제 검색에 도움이 되는가: 한국어 YouTube에서 시각-텍스트 의미 격차 분석

**영문:** *When Does the Thumbnail Help Retrieval? An Analysis of the Visual–Text
Semantic Gap in Korean YouTube Search*

> 프레임 변경 근거: v2 제목("Thumbnail-Text Fusion Embeddings")은 Fusion **기술**
> 논문으로 읽혀 novelty가 약하다(CLIP+SBERT late fusion은 이미 포화). 실제 기여는
> "시각 정보가 **언제** 검색에 기여하는지"를 라벨링 없이 자동 계산되는 gap 지표로
> **설명(explain)**한 데 있다. 제목을 분석(When/Analysis) 중심으로 재배치한다.

---

## 초록 (Abstract)

YouTube 영상 검색은 제목·설명·태그 등 텍스트 메타데이터에 의존하며, 썸네일의 시각
정보는 거의 활용되지 않는다. 시각 정보를 텍스트와 결합(fusion)하면 검색 성능이
오른다는 것은 알려져 있으나, **"모든 영상에서 균일하게 도움이 되는가, 아니면 특정
조건에서만 도움이 되는가"**는 규명되지 않았다. 본 연구는 이 조건을 **라벨링 없이 자동
계산되는 연속 지표**로 설명한다: 썸네일이 제목과 의미적으로 얼마나 어긋나는지를 CLIP
결합 공간에서 잰 **시각-텍스트 의미 격차(gap)**다. 우리는 CLIP 이미지 임베딩과 다국어
텍스트 임베딩의 late fusion을 **성능 향상 자체가 아니라 영상별 기여도를 측정하는
도구**로 사용하고, gap이 이 기여도(순위 개선폭)를 예측하는지 검증한다. 한국어 YouTube
**840편**(YouTube 공식 카테고리 14개 × 60, 규칙 표집)과 `[DATA: N_q]`개 쿼리로
평가한 결과, 융합은 text-only 대비 MRR@10을 `[DATA: Δ]` 향상시키며(Wilcoxon,
`[DATA: p]`), **gap은 융합에 의한 순위 개선을 예측하는 유의한 변수**로 나타난다
(Spearman ρ=`[DATA]`, `[DATA: p]`; gap 상위군 Cohen's d=`[DATA]`). 나아가 쿼리
유형·쿼리 길이·gap 수준별로 효과가 어떻게 달라지는지 분석한다. **본 연구의 기여는 새로운
융합 기법이 아니라, 멀티모달 검색에서 시각 정보의 기여 조건을 라벨링 없이 정량적으로
설명하는 gap 지표를 제안한 데 있다.** 함의로서, gap이 높은 영상에만 시각 임베딩을 선별
적용하는 **적응형 검색(adaptive retrieval)** 전략의 근거를 제시한다.

**Keywords:** multimodal retrieval, CLIP, semantic gap, CLIPScore, explainable
retrieval, Korean YouTube, information retrieval

---

## 1. 서론 (Introduction)

### 1.1 문제 정의 — "성능이 오른다"에서 "언제 오르는가"로

멀티모달 검색에서 시각 채널을 텍스트와 결합하면 성능이 오른다는 보고는 많다. 그러나
대부분은 **"이미지를 넣었더니 좋아졌다"**에서 멈추고, **그 향상이 어떤 영상에서
발생하는지**는 다루지 않는다. 실무적으로 이 구분은 중요하다 — 시각 임베딩 계산은
비용이 들기 때문에, "모든 영상에 필요한가, 일부에만 필요한가"에 따라 시스템 설계가
달라진다.

시각 정보의 기여가 영상마다 다른 이유는 무엇인가? 우리는 다음 논리에서 출발한다.
영상마다 **텍스트 메타데이터(제목·설명)가 정보를 충분히 담은 영상**이 있고 **그렇지
못한 영상**이 있다. (1) 텍스트가 이미 충분하면, 썸네일은 대체로 그 내용을 시각적으로
반복할 뿐이라 검색에 **추가 정보를 거의 주지 못한다**. (2) 반대로 텍스트가 부족하거나
썸네일이 제목에 없는 내용을 담고 있으면, 시각 채널이 **정보를 보완할 여지**가 생긴다.
(3) 따라서 "시각 채널이 기여할 여지"는 곧 **썸네일이 제목과 얼마나 다른 내용을 담는가**로
환원되고, 이를 정량화한 것이 본 연구의 **시각-텍스트 의미 격차(gap)**다. 즉 gap은
임의로 도입한 지표가 아니라 위 논리에서 필연적으로 도출되는 양이다.

그렇다면 이 "기여 여지"를 무엇으로 측정할 것인가? 자연스러운 대안은 썸네일을
"인물형·제품형·그래프형" 같은 유형으로 사람이 나누는 것이지만, 이는 (1) 경계가
주관적이고(혼합형 처리 불명확), (2) 재현 불가능하며, (3) 라벨링 비용이 든다. 본 연구는
대신, 검색 파이프라인이 이미 계산하는 임베딩만으로 gap을 **완전 자동·재현 가능한 연속
지표**로 산출한다.

### 1.2 연구 질문 (핵심)

> **RQ1 (조건 분석 · 주):** 영상별 **시각-텍스트 의미 격차(gap)** — 썸네일이 제목에
> 없는 정보를 얼마나 담는지를 CLIP 결합 공간에서 잰 값 — 은 융합에 의한 검색 순위
> 개선을 **예측하는 유의한 변수인가?** (gap을 "높으면 좋다"는 결정적 규칙이 아니라
> 확률적 예측 변수로 본다.)
>
> **RQ2 (성능 · 부):** CLIP 썸네일 임베딩과 다국어 텍스트 임베딩의 late fusion은
> text-only 대비 검색 성능을 향상시키는가?

RQ2(성능)는 시각 채널이 "전반적으로" 유효함을 확인하는 기반이고, **RQ1(조건)이 본
연구의 기여**다. late fusion은 RQ1을 측정하기 위한 도구이지 그 자체가 novelty가 아니다.

### 1.3 기여점 (Contributions)

> **한 줄 novelty**: 본 연구는 "검색 성능을 높이는 새로운 융합 기법"을 제안하는 것이
> 아니라, **멀티모달 검색에서 시각 정보의 기여 조건을 라벨링 없이 정량적으로 설명하는
> gap 지표를 제안**한다.

1. **라벨링이 필요 없는 시각-텍스트 의미 격차(gap) 지표** — CLIP 이미지 인코더와 CLIP
   이미지 공간에 정렬된 다국어 텍스트 인코더로 계산. 주관적 유형 분류를 대체한다.
2. **"시각 채널은 언제 도움이 되는가"에 대한 정량적 설명** — gap과 융합에 의한 순위
   개선(Δrank)의 상관·회귀 분석, 그리고 쿼리 유형·쿼리 길이·gap 수준별 효과 분석.
   단순 "성능 향상"을 넘어 **기여 조건을 설명(explain)**한다.
3. **효과 크기(effect size)까지 보고** — 통계적 유의성뿐 아니라 gap 수준별 Cohen's d로
   실질적 효과 크기를 정량화.
4. (도구·재현성) CLIP + 다국어 텍스트 임베딩 late fusion 검색 파이프라인, 및 운영
   메타데이터 플랫폼(`meta_youtube_video_vec`)에의 시각 임베딩 컬럼 확장 설계.

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Radford et al. (2021), CLIP, *ICML* | 이미지-텍스트 대조학습, 결합 공간 코사인 유사도가 정합성 표준 지표. | 한국어 YouTube 검색 적용·조건 분석 없음 |
| Hessel et al. (2021), CLIPScore, *EMNLP* | CLIP 유사도를 캡션 품질 자동 평가에 사용. | **본 연구는 같은 계산식을 캡션 평가가 아니라 "검색 기여도 예측 변수"로 재해석** |
| Fang et al. (2021), CLIP2Video, arXiv:2106.11097 | 프레임 집계 비디오-텍스트 검색(영어 MSR-VTT). | 썸네일 단일 프레임으로 비용↓, 한국어, 기여 조건 분석 |
| Gao et al. (2022), M2HF, arXiv:2208.07664 | 멀티레벨 멀티모달 융합. | 대규모 프레임/자막 중심, 조건 분석 아님 |
| Reimers & Gurevych (2019), Sentence-BERT, *EMNLP* | 다국어 텍스트 임베딩. | 시각 채널 기여 조건 미분석 |
| Li et al. (2022), BLIP, *ICML* | 이미지-텍스트 통합 모델. | 기여 조건-지표 관계 분석 없음 |
| ThumbnailTruth (2025), arXiv:2509.04714 | CLIP 썸네일+텍스트 late fusion으로 클릭베이트 **분류**. | 과제가 분류이며 검색 랭킹·조건 분석 아님 |

### 2.1 선행 연구 대비 위치 (Positioning)

- CLIP late fusion과 CLIPScore류 정합성 지표는 각각 성숙한 요소다. **본 연구의 novelty는
  이 둘의 조합이 아니라, 정합성 지표(gap)를 "검색에서 시각 채널이 언제 기여하는지"의
  설명 변수로 세운 데 있다.** "이미지를 넣으니 좋아졌다"가 아니라 "언제·왜 좋아지는지
  설명한다"(explainable retrieval).
- 가장 가까운 선행(클릭베이트 탐지)은 동일 임베딩 스택을 쓰나 과제가 분류이며, 검색
  기여도를 gap 같은 연속 지표로 설명하지 않는다.
- 한국어 YouTube 도메인에서의 실증·조건 분석은 확인된 선행이 없다.

> **⚠️ 검증 필요:** novelty 주장은 2026-07-08 검색 기준. 제출 전 최신 arXiv/ACL/DBLP
> 재검색으로 최근 6개월 유사 연구 재확인(특히 "CLIPScore rank improvement retrieval",
> "image-text gap retrieval"). 재검색 로그는 [references.md](references.md)에 기록.

---

## 3. 방법 (Method)

### 3.1 임베딩 추출

```
[검색용 — RQ2 측정 도구]
썸네일 → CLIP ViT-B/32 (이미지 인코더) → 512-dim  v_img
제목  → paraphrase-multilingual-mpnet-base-v2 → 768-dim  ret_txt   (검색 텍스트 채널)

[gap 계산용 — RQ1 핵심, 검색 파이프라인과 별개]
제목 → clip-ViT-B-32-multilingual-v1 (CLIP 이미지 공간에 정렬된 다국어 텍스트 인코더)
     → 512-dim  g_txt   (v_img와 같은 CLIP 결합 공간)
```

> **왜 텍스트 인코더가 두 개인가**: v_txt(mpnet)는 한국어 검색 품질이 좋지만 CLIP 이미지
> 공간과 정렬돼 있지 않다. late fusion은 `sim(q_img,d_img)`와 `sim(q_txt,d_txt)`를 각각
> 독립적으로 가중합하므로 두 공간이 달라도 무방하다. 그러나 "이미지와 텍스트가 같은
> 내용을 말하는가"를 재는 gap은 **반드시 같은 결합 공간**에서 계산해야 하므로, CLIP
> 이미지 임베딩에 distillation으로 정렬된 다국어 CLIP 텍스트 인코더를 gap 전용으로 쓴다.

### 3.2 시각-텍스트 의미 격차 (gap) — 본 연구의 핵심 지표

```
gap_i = 1 - cos_sim( center(v_img_i), center(g_txt_i) )   # center = 모달별 코퍼스 평균 차감 후 재정규화
       # cos∈[-1,1] → gap∈[0,2]; centering 후 일부 cos<0라 gap>1도 정상
```

**왜 코사인 기반(1−cos)인가**: 이미지-텍스트 의미 정합성을 CLIP 결합 공간의 코사인
유사도로 재는 것은 CLIPScore(Hessel et al., 2021) 이후 표준화된 방식이다. gap은 mean-centering
후 그 코사인 유사도를 **역변환(1−cos)** 해 "얼마나 어긋나는가 = 시각 채널이 보완할 여지"로
해석한 것이다(cos∈[−1,1]이라 '여집합'이 아니라 역변환으로 표현). 즉 새 수식을 발명한 게 아니라, **검증된 CLIPScore 계산을 검색 기여도
예측이라는 다른 목적에 재사용**한다. 라벨링 없이 전체 코퍼스에 자동 적용되며 임베딩
추출의 부산물이라 추가 비용이 없다.

**왜 mean-centering인가 (전처리)**: CLIP 임베딩은 이방성(anisotropy)이 강해 raw 코사인이
좁은 대역에 뭉친다(우리 코퍼스 실측: raw gap std ≈ 0.03). 이를 그대로 쓰면 영상 간
차이가 노이즈에 지배된다. 모달별 평균 벡터를 차감(mean-centering; Mu & Viswanath, 2018)
하면 이방성·modality-gap offset이 제거되어 **정합(제목↔자기 썸네일)과 비정합의 분리가
크게 개선**된다(자기매칭 R@1이 raw 대비 상승, §5). ⚠️ **표현 주의**: centering은 "정답
gap"이 아니라 **construct validity를 높이는 전처리**이며(CLIPScore가 raw인 것과 이 점만
다름), **retrieval 성능이 아니라 정합-비정합 construct validity를 근거로 실험 전에
선택**했다(HARKing 아님). raw gap 결과도 sensitivity로 함께 보고한다(§5.3, §6.2). µ는
최종 평가 코퍼스로 1회 계산해 이후 전 단계에 동일 적용한다.

> **인코더 두 개(§3.1) 재확인**: gap은 반드시 같은 CLIP 결합 공간에서 재야 하므로 이미지
> `clip-ViT-B-32`와 그 공간에 distillation 정렬된 다국어 텍스트 인코더
> `clip-ViT-B-32-multilingual-v1`을 쓴다. 검색용 텍스트(mpnet)와 **역할을 섞지 않는다**.

### 3.3 융합 (RQ2 측정 도구)

```
Text-only  : sim = cos(mpnet(q), ret_txt_d)
Visual-only: sim = cos(clip_mtxt(q), v_img_d)          # 텍스트 쿼리 ↔ 썸네일 교차모달
Late Fusion: score = α·minmax(sim_text) + (1-α)·minmax(sim_visual),  α ∈ {0.0, 0.1, …, 1.0}
             # 두 채널 스케일이 달라 쿼리별 min-max 정규화 후 가중합
```

**α 처리(사전 고정, 결과 보기 전)**: **primary operating point = α=0.5** — retrieval 결과를
참조하지 않고 사전에 고른 **대칭 equal-weight 지점**이다(*"selected a priori as the
symmetric equal-weight operating point, without reference to retrieval performance"*).
전체 α grid는 **sensitivity analysis**로 곡선만 보고하며, **최고점 α를 "optimal fusion"
으로 고르지 않는다**(test leakage 금지 — α가 바뀌면 융합 모델 자체가 바뀌므로 robustness가
아니라 sensitivity라 부른다).

융합은 성능 향상 자체가 목적이 아니라, **영상별 순위 개선폭(Δrank)을 만들어 gap과의
관계(RQ1)를 측정하기 위한 도구**다. retrieval 점수는 raw cosine을 쓴다(gap 전용 centering과
분리).

### 3.4 gap 가설 (RQ1)

```
qrels의 각 (쿼리 q, 관련 영상 v)에 대해:
  Δrank(v,q) = rank_text(v|q) - rank_fusion(v|q)     # 융합은 α=0.5. 양수 = 순위 개선
가설: gap이 큰 영상일수록 Δrank가 크다 (Spearman ρ > 0)
```

gap은 **영상 수준(video-level)** 지표(쿼리 무관, 영상당 1개)이고 Δrank는 (쿼리, 영상)
쌍마다 생기므로, **primary 분석은 영상당 Δrank를 median 집계**해 `Spearman(gap_v,
median Δrank_v)`로 본다(§5.3). 카테고리마다 gap 분포가 달라 생길 수 있는 **허위 상관
(카테고리 교란)**과 **반복측정** 구조는 secondary 분석으로 통제한다(§5.3).

---

## 4. 실험 설계 (Experimental Setup)

> 표집·라벨링·규모의 근거는 [PREREGISTRATION.md](PREREGISTRATION.md)에 실험 전 고정.
> 핵심만 요약한다.

### 4.1 코퍼스와 평가 쿼리 (Sampling ≠ IR 평가)

**코퍼스와 평가 쿼리는 서로 다른 문제다**(전자=다양한 영상 풀 확보=Sampling, 후자=검색
성능 평가=IR). 상세 규격은 [PREREGISTRATION.md](PREREGISTRATION.md) §0에 재현 가능하게
고정(freeze). 핵심만 요약한다.

**코퍼스(§PREREG 0.1)**: `videoCategories.list(regionCode='KR')`의 `assignable=true`
카테고리 **14개**를 표집 틀로 쓴다. ⚠️ **categoryId는 Sampling Anchor이지 semantic ground
truth가 아니다** — 주제 다양성 확보용 층화 도구로만 쓰고 H1/H2 어디서도 레이블로 쓰지
않는다(제작자가 categoryId를 22/24/27로 다는 경향이 커 일부 카테고리는 categoryId 잔존율이
낮음을 Pilot로 관찰; 이를 Appendix dispersion으로 보고). 절차: `videoCategoryId`가 search
필터로 부적합함을 실측했으므로 **search로 수집 → `videos.list`의 `categoryId`로 사후
필터링**한다. **카테고리당 복수 seed(Appendix 수록)**로 커버리지를 확보하고 **정렬 3혼합
(relevance+viewCount+date)**, **채널당 최대 5개**, **seed 간 round-robin**(단일 seed 독식
방지)으로 채운다. **Shorts 제외**: `duration` 실측 **60초 초과만** 남긴다(`videoDuration=
'long'`은 20분 초과라 일반 영상을 배제해 미채택). **카테고리당 60편 × 14 = 840편**(사전
고정, best-effort 층화; 확률표본 아님). 수집 단계별 감소는 funnel 표로 투명 보고한다.

**평가 쿼리(§PREREG 0.2)**: 코퍼스 Sampling과 개념이 다르며 실제 사용자 검색어를 반영한다.
연구자 임의 창작이 아니라 **YouTube의 공개 관찰 가능한 검색 제안(Suggest)** 에서 생성한다
(Google Trends=재현 불가, Naver DataLab=도메인 불일치로 미채택). **코퍼스 seed와 독립적인
고정 trigger**(카테고리 수준, seed 구 재사용 금지)로 Suggest를 촉발해 후보를 모은다. 촉발은
**초성(jamo) sweep** — category term에 초성 ㄱ/ㄴ/ㄷ…을 이어 붙여 해당 초성으로 시작하는
넓은 완성어를 수집한다(음절 sweep 가/나/다…는 사실상 ㅏ모음만 탐색해 거/게/고/기 등을
구조적으로 누락하는 coverage 결함이 확인됨; §PREREG 2026-08-14b). 이어 **사전 등록된 curation
규칙으로 navigational(채널/프로그램)·category mismatch·상품·서비스 쿼리를 제외**한다(후보마다
decision+reason 전량 기록 → Appendix exclusion funnel). 영상 텍스트에서 파생하지 않는다
(KeyBERT 금지 — circularity). eligible pool에서 **카테고리별로 MD5 해시 순 + content-filter
(META/NAV/product/near-duplicate skip) 결정적 표집**으로 카테고리당 동일 N을 뽑는다(3-way audit
[MD5/farthest/medoid]에서 MD5가 META/NAV 최소·재현성 최고로 선택; §PREREG 2026-08-14b).
**쿼리는 retrieval 실험 전에 확정(freeze)**하고 성능을 보고 바꾸지 않는다. 14개 카테고리
동일 N, 최종 **N=70(14×5)**(§PREREG 0.6·2026-08-14c).

| 항목 | 값 |
|------|-----|
| 영상 수 | **840** (14 × 60, 균형; 최종 다중모달 평가 코퍼스) |
| 표집 틀 | YouTube KR assignable 카테고리 14개, categoryId=Sampling Anchor (§PREREG 0.1) |
| 길이 | **Long-form 아님 — Shorts(≤60초)만 제외**(실측: ≤60초 0 / 1–4분 168 / 4–20분 346 / >20분 326) |
| 평가 쿼리 | YouTube Suggest(**초성 sweep**) + seed-독립 trigger + curation → 카테고리별 **MD5+content-filter 표집**, **N=70 (14×5)** |
| qrels | Text∪Visual∪Fusion 각 Top10 pooling → **3인 blind·독립** 라벨링, **median-of-3** 집계; Cohen κ(A-B)·완전3인시 Fleiss κ 보고 (기존 |차이|1=평균·0↔2=합의는 C 미커버 백스톱) |
| 쿼리 제거 | **최종 qrels에서 관련(등급≥1) 0개** 쿼리 제외(결과 무관, 제거 수 투명 보고) |
| gap 계산 | 전체 자동(라벨링 없음), centered |

### 4.2 절차 (§PREREG 0 순서)

1. 코퍼스 수집(§0.1) — 840편.
2. 임베딩(이미지/gap텍스트/검색텍스트) → **centered gap** 자동 계산(+인코더 sanity check §0.4).
3. **trigger freeze → Suggest 생성 → curation(navigational/mismatch/service 제외, audit log)
   → Query Pilot로 pool 크기 실측 → 쿼리 수·쿼리셋 Freeze**(§0.2·0.6).
4. 본 쿼리 pooling → **3인 blind·독립** 라벨링 → **median-of-3** qrels·κ(Cohen/Fleiss)·정답0 제거(§0.3).
5. retrieval: Text/Visual/Late Fusion(**α=0.5 primary + α grid sensitivity**, best-α 선택 없음).
6. (쿼리, 관련영상) Δrank 산출.
7. H1(Fusion α=0.5 vs Text: MRR@10 차>0.05 & paired Wilcoxon) / H2(영상당 median Δrank vs
   gap Spearman; secondary=카테고리 stratified + query-video cluster-robust; sensitivity=raw
   vs centered).

---

## 5. 평가 (Evaluation)

### 5.1 후보 풀 구성 (Pooling)

한 시스템의 상위 결과만 라벨링하면 편향된다(Text-only만→Fusion이 끌어올린 영상을 qrels가
모름 / Fusion만→Fusion에 유리한 후보만 라벨링). 표준 pooling을 따라 **Text-only ∪
Visual-only ∪ Late Fusion 각 Top10의 합집합**(중복 제거)을 후보 풀로 삼는다(§PREREG 0.3;
Top-K·pooling 대상 시스템은 결과 보기 전 고정, 사후 변경 금지). 라벨링 시트는 **어느
시스템이 뽑았는지 표시하지 않고(blind) 쿼리별로 셔플**하며, **세 라벨러가 상호 라벨을 볼
수 없는 독립 파일**로 작업하고 **median-of-3**으로 집계한다(§PREREG 0.3). Fusion이 찾은
영상이 pooling으로 qrels에 포함되는 것은 IR 표준이다.

### 5.2 지표

| 지표 | 대상 |
|------|------|
| MRR@10, NDCG@10, Recall@10 | 검색 성능(RQ2) |
| Spearman ρ(gap, Δrank) | gap의 순위개선 예측력(RQ1) |
| Cohen's d | gap 수준별 효과 크기 |

### 5.3 통계·강건성 (§PREREG 0.5·6)

**H1(RQ2)**: Fusion(α=0.5) vs Text-only — 쿼리별 reciprocal rank@10에 **paired Wilcoxon
signed-rank**(p<0.05) **그리고** aggregate MRR@10 차 > +0.05(두 조건 모두).

**H2(RQ1)** — 카테고리 교란·반복측정을 선제 차단하는 다층 구조(§PREREG 0.5):
- **primary**: 영상당 **median Δrank** → `Spearman(centered gap, median Δrank)` (gap이
  video-level이라 이 단위가 자연스러움; median으로 극단값 방어).
- **secondary**: (1) query-video 원자료 `Δrank ~ gap + category`에 **video 클러스터-robust
  SE**(반복측정 보존), (2) **카테고리 내(stratified) Spearman**.
- **descriptive**: 14개 중 양(+) 상관 카테고리 비율(검정 승격 아님).
- **sensitivity**: **raw gap vs centered gap**으로 primary 재실행(centering은 construct
  validity로 사전 선택했고 raw는 측정 선택의 영향을 보는 것이지 성능으로 고른 게 아님).
- **부트스트랩 95% CI**(1,000회) + subsampling 수렴 곡선 + **MDES**(탐지 가능한 최소 ρ_min).

### 5.4 성공 기준 (실험 전 고정)

- RQ2(H1): Fusion(α=0.5) MRR@10 > Text-only + 0.05 **그리고** paired Wilcoxon p<0.05
- RQ1(H2): primary Spearman ρ(centered gap, median Δrank) > 0, p<0.05
- 결과가 위에 못 미쳐도 §PREREG 3(결과 분기 매트릭스)에 따라 조건부/부정 결과로 서술.

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

> 구성 원칙: **§6.1(전체 성능)은 맥락, §6.2~6.4(조건 분석)가 본 논문의 중심.**

### 6.1 전체 성능 (RQ2, 맥락)

| 방법 | MRR@10 | NDCG@10 | Recall@10 |
|------|--------|---------|-----------|
| Text-only | `[DATA]` | `[DATA]` | `[DATA]` |
| Visual-only | `[DATA]` | `[DATA]` | `[DATA]` |
| **Late Fusion (α=0.5, primary)** | **`[DATA]`** | **`[DATA]`** | **`[DATA]`** |

Wilcoxon (Fusion α=0.5 vs Text-only, 쿼리별 RR@10): `[DATA: stat, p]` (부트스트랩 95% CI:
`[DATA]`). **α sensitivity 곡선**(α∈{0.0..1.0}별 MRR/NDCG/Recall@10): `[DATA: 곡선]`
(최고점 α를 "최적"으로 주장하지 않음 — sensitivity로만 보고).

### 6.2 gap과 순위 개선 (RQ1, 핵심)

| 통계량 | 값 |
|--------|-----|
| **primary** Spearman ρ(centered gap, 영상당 median Δrank) | `[DATA]` (95% CI `[DATA]`) |
| p-value / 표본(영상 수) / MDES ρ_min | `[DATA]` / `[DATA]` / `[DATA]` |
| **sensitivity** ρ(raw gap, median Δrank) | `[DATA]` |
| **secondary** 카테고리 stratified: 양(+) 상관 카테고리 비율 | `[DATA]` (예 12/14) |
| **secondary** 회귀 `Δrank~gap+category`(video 클러스터-robust) gap 계수/p | `[DATA]` |

`[DATA: centered gap(x) vs median Δrank(y) 산점도 + 회귀선]`

**gap 수준별 효과 크기 (Cohen's d):** gap을 3등분해 상·하위군의 평균 순위 개선과 두 군
간 효과 크기(Cohen's d)를 함께 보고한다. 아래는 형식 예시이며 실수치로 교체한다.

| gap 수준 | n | 평균 Δrank | 두 군 간 Cohen's d |
|---|---|---|---|
| High gap (상위 33%) | `[DATA]` | `[DATA: 예 +7.6]` | — |
| Mid gap (중위 33%) | `[DATA]` | `[DATA]` | — |
| Low gap (하위 33%) | `[DATA]` | `[DATA: 예 +1.2]` | High vs Low: `[DATA: 예 d=0.81]` |

→ 통계적 유의성(p)뿐 아니라 **효과 크기(d)**까지 보고해, gap 상위군의 순위 개선이
하위군 대비 실질적으로 큰지를 정량화한다.

### 6.3 쿼리 유형별 효과 (조건 분석)

쿼리 `[DATA: 50]`개를 유형으로 분류(기술 / 라이프스타일 / 뉴스 / 엔터테인먼트 등)하고
유형별 융합 개선폭을 본다.

| 쿼리 유형 | n | ΔMRR@10 |
|---|---|---|
| 기술(Technical) | `[DATA]` | `[DATA]` |
| 라이프스타일 | `[DATA]` | `[DATA]` |
| 뉴스 | `[DATA]` | `[DATA]` |
| 엔터테인먼트 | `[DATA]` | `[DATA]` |

### 6.4 쿼리 길이별 효과 (조건 분석)

쿼리 토큰 수(2/3+/…)별 융합 개선폭 — 완전 자동 분석(추가 라벨링 없음).

| 쿼리 길이(단어) | n | ΔMRR@10 |
|---|---|---|
| 짧음(≤2) | `[DATA]` | `[DATA]` |
| 중간(3–4) | `[DATA]` | `[DATA]` |
| 김(≥5) | `[DATA]` | `[DATA]` |

### 6.5 정성 사례 (illustration, 분석 근거 아님)

가설을 지지하는 사례(gap 높음 → 개선)와 **반례**(gap 높은데도 개선 실패)를 함께 표로
제시한다. 반례를 숨기지 않는 것은 §7·§9에서 gap을 "결정적 규칙"이 아니라 "예측 변수"로
서술하는 것과 일관된다. 아래는 형식 예시이며 실제 사례로 교체한다.

| 쿼리 | gap | Δrank | 결과 | 비고(썸네일, 정성) |
|---|---|---|---|---|
| `[예: HBM]` | `[0.63]` | `[+11]` | 도움 | 제품 근접샷, 제목에 없는 시각 단서 |
| `[예: 이어폰]` | `[0.58]` | `[+9]` | 도움 | 제품형 |
| `[예: AI반도체]` | `[0.67]` | `[-2]` | **실패(반례)** | gap 높으나 썸네일·제목 둘 다 질의와 약하게만 관련 |

이들의 썸네일 유형(인물/제품/그래프 등)은 **정성적으로만** 부기한다 — 주관적 유형
분류를 분석의 근거로 삼지 않으며(그래서 gap 지표를 도입했으므로), 어디까지나 예시다.

### 6.6 연산 비용

`[DATA: CLIP 이미지 인코더 + gap용 텍스트 인코더 추론 시간]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- **주장 수위(중요)**: gap을 "**높을수록 반드시 도움이 된다**"는 결정적 규칙이 아니라,
  "이미지 정보의 잠재적 기여도를 설명하는 **유용한 예측 변수**"로 서술한다. 전자는
  반례(§6.5) 하나로 무너지지만, 후자는 확률적 주장이라 반례가 있어도 성립한다. §6.2의
  상관·효과 크기는 이 예측력의 **강도**를 보고하는 것이지 결정적 법칙을 주장하지 않는다.
- **실무적 함의(적응형 검색)**: gap은 시각 임베딩이 유용할 영상을 **사전에 선별**하는
  기준으로 쓸 수 있다 — gap이 낮은 영상엔 시각 임베딩 계산·저장을 생략하고 높은 영상에만
  적용하는 **적응형 검색(adaptive retrieval)** 전략으로 비용을 줄일 수 있다. 이것이
  "예측 변수"라는 약한 주장에 구체적 쓸모를 부여한다.
- gap이 높은데도 개선이 없는 예외(§6.5 반례)의 원인: 썸네일·텍스트 둘 다 질의와 무관 →
  gap은 높으나 어느 쪽도 검색에 유용치 않음. gap은 "정합성 어긋남"을 재지 "유용성"을
  보장하지 않는다는 한계를 드러낸다.
- **RQ1이 약하게 나온 경우의 서술**(§PREREG 3 우측 열): 전체 융합은 유효하나 gap 예측이
  약함 → 다른 예측 요인(쿼리 유형·길이) 탐색 필요라는 방향 제시. §6.3~6.4가 대안적 조건
  설명을 제공하므로 논문이 "설명 실패"로 끝나지 않는다.

## 8. 한계 (Limitations)

- 테스트 쿼리 `[DATA: N_q]`(=70)·평가자 3인(median-of-3) — 검정력 한계(MDES로 정량 보고).
- **시각 인코더 OCR 미수행**: CLIP-ViT-B-32는 썸네일 내 **한국어 자막 텍스트를 판독하지
  못한다**(전용 OCR 없음, 한국어 이미지-텍스트는 특히 약함). 따라서 본 연구의 시각 신호(및
  gap)는 **썸네일의 시각적 장면 및 비문자적 시각 정보**에 국한되며, 자막에 담긴 정보는 반영하지 못한다. OCR-증강
  썸네일로의 확장은 후속 연구로 남긴다(§9).
- gap은 정렬된 다국어 CLIP 텍스트 인코더의 한국어 품질에 의존하며, **mean-centering
  전처리**(이방성 제거)를 쓴다 — centered는 raw CLIPScore와 다르므로 raw 결과를 sensitivity로
  병기했으나, 전처리 선택이 완전히 자유롭지 않음은 한계다.
- gap은 제목-썸네일 정합성만 측정(설명·영상 내용과의 정합성 미반영).
- 상관은 인과가 아님(채널 인기도 등 교란 가능성; 카테고리 교란은 §5.3 secondary로 통제).
- **평가 코퍼스는 확률표본이 아니라 gap 분산 확보용 카테고리 층화표본**(14×60): 대표성
  주장은 **"2025-01-01 이후 게시된 한국어 non-Shorts YouTube 영상의 카테고리 층화표본"**
  으로 좁게 규정한다(YouTube 전체 대표 주장 아님). categoryId 관행상 일부 카테고리는
  categoryId 잔존율이 낮으나 복수 seed·깊은 표집으로 60편을 충원함.
- 평가 쿼리는 YouTube Suggest에서 수집·curation한 것으로, Suggest가 실제 사용자 의도를
  그대로 반영한다고까지 주장하지 않는다(내부 메커니즘 미공개).

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

핵심 메시지(주장 수위를 약하게 유지):
1. CLIP 썸네일 임베딩과 텍스트 임베딩의 late fusion은 한국어 YouTube 검색에서 text-only
   대비 성능을 향상시킨다(`[DATA]`).
2. 그러나 그 기여는 균일하지 않으며, **시각-텍스트 의미 격차(gap)는 그 기여를 설명하는
   유의한 예측 변수**다(`[DATA]`; 결정적 규칙이 아니라 확률적 예측).
3. 따라서 시각 임베딩은 모든 영상에 필요하지 않으며, **gap 기반 선별 적용(적응형 검색)**
   으로 비용을 줄일 수 있다.

본 연구의 기여는 새로운 융합 기법이 아니라, **멀티모달 검색에서 시각 정보의 기여 조건을
라벨링 없이 정량적으로 설명하는 gap 지표를 제안하고 실증**한 데 있다.

향후: gap 기반 적응형 검색(gap 높은 영상에만 시각 임베딩 적재)의 실제 비용-성능 트레이드
오프 측정, **OCR-증강 썸네일**(한국어 자막 판독)로 시각 채널·gap 확장, 대표 프레임 다중
샘플링, 한국어 도메인 CLIP fine-tuning, 썸네일 A/B 교체 탐지.

---

## 참고문헌 (References)

전체 서지정보·확인 경로는 [references.md](references.md) 유지. 본문 인용:
Radford+2021(CLIP), Hessel+2021(CLIPScore), Fang+2021(CLIP2Video), Reimers&Gurevych2019
(SBERT), Li+2022(BLIP), Gao+2022(M2HF), ThumbnailTruth 2025(arXiv:2509.04714, 서지 미완),
**Mu&Viswanath 2018(All-but-the-Top, gap centering 근거)**, Ethayarajh 2019(임베딩 이방성).

---

## 데이터 삽입 체크리스트 (작업용)

- [x] 4.1 코퍼스 규모 N=**840**(14×60) 확보 · 임베딩 · centered gap 산출 완료
- [x] 4.1 쿼리 수 확정 **N=70(14×5)** — 초성 sweep + MD5+content-filter 표집, 3인 라벨링 시트 생성
- [ ] 4.1/5 라벨링 완료(3인 median-of-3) → qrels·κ·정답0 제거 후 최종 N 확정·보고
- [ ] 6.1 전체 성능표(Text/Visual/Fusion α=0.5) + Wilcoxon + 부트스트랩 CI + **α sensitivity 곡선**
- [ ] 6.2 primary Spearman ρ(centered gap, median Δrank) + 산점도 + Cohen's d + MDES
      + **raw sensitivity** + **카테고리 stratified·회귀**
- [ ] 6.3 쿼리 유형별 표 · 6.4 쿼리 길이별 표
- [ ] 6.5 정성 사례 1~3 · 6.6 연산 비용
- [ ] 7~9장 작성, Abstract [DATA] 전부 실수치 교체
- [ ] 참고문헌 7번 서지 완성, novelty 재검색(§2.1)
- [ ] Appendix: **seed 목록 · trigger 목록 · 쿼리 curation exclusion funnel · categoryId dispersion · 수집 funnel** 표
- [ ] Appendix: **쿼리 생성 방법 비교(음절/초성/bare sweep)** + **표집 3-way audit(MD5/farthest/medoid)** 근거표
- [ ] **5페이지 분량 확인** (초과 시 §2 관련연구·§6.6·부록 우선 축약)
