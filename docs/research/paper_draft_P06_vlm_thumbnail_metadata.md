# 논문 초안: 비전-언어 모델을 이용한 YouTube 썸네일 메타데이터 자동 생성

> 기반 기획서: [research_proposals.md](./research_proposals.md) P06
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)

---

## 제목 (Title)

**영문:** *Vision-Language Models for Automated Thumbnail Metadata Generation in Korean YouTube Content*

**국문:** 비전-언어 모델을 이용한 한국어 YouTube 썸네일 메타데이터 자동 생성

---

## Abstract

YouTube video thumbnails often encode visual information — products, people, emotional
tone — that is never mentioned in the video's transcript, yet existing automated metadata
generation research is concentrated almost entirely on transcript text. We propose a
pipeline that uses a vision-language model (VLM; LLaVA-family, served via the Groq Vision
API) to automatically extract four types of structured metadata from Korean YouTube
thumbnails — visual summary, dominant objects, visual emotion, and layout type — and we
empirically evaluate the complementarity between this VLM-derived metadata and
transcript-based LLM metadata (produced by the pipeline proposed in a companion study,
P03). On a corpus of `[DATA: N]` videos, `[DATA: 100]` of which are rated by three human
judges on a 1–5 scale (accuracy / specificity / usefulness), mean VLM metadata quality is
`[DATA]` (GPT-4V used as an upper-bound reference, rated in parallel at `[DATA]`). We
measure the **novel information ratio** — the fraction of VLM-extracted keywords absent
from the transcript-derived keyword set — separately for videos with (`has_content=TRUE`)
and without (`has_content=FALSE`) a transcript, finding `[DATA]`% and `[DATA]`%,
respectively. In a four-condition (A/B/C/D) retrieval ablation over `[DATA: 50]` test
queries, adding VLM thumbnail metadata (condition C) changes MRR@10 relative to the
API-metadata-only baseline (condition A) by `[DATA: Δ]` (Friedman test across all four
conditions, `[DATA: p-value]`). We discuss whether the novel information captured by the
VLM channel translates into measurable retrieval gains, and whether this relationship
differs between videos with and without transcripts.

**국문 초록 (draft):** P03(트랜스크립트 기반 LLM 메타데이터 생성)은 텍스트 채널만
활용하며, 썸네일에 담긴 제품·인물·감성 톤 같은 시각 정보는 트랜스크립트에 전혀
언급되지 않는 경우가 많다. 본 연구는 비전-언어 모델(VLM; LLaVA 계열, Groq Vision
API)을 이용해 한국어 YouTube 썸네일에서 시각적 메타데이터 4종(시각 요약·주요
객체·감성·레이아웃 유형)을 자동 추출하는 파이프라인을 구축하고, 트랜스크립트 기반
LLM 메타데이터(P03)와의 정보 보완성을 실증한다. 영상 `[DATA: N]`편 중 `[DATA:
100]`편의 visual_summary를 3인이 1–5점으로 평가한 결과 평균 `[DATA]`점을 얻었다
(GPT-4V를 upper bound baseline으로 병행 평가한 결과는 `[DATA]`점). 트랜스크립트
유무(`has_content`)별로 신규 정보 비율을 각각 측정한 결과 has_content=TRUE 그룹에서
`[DATA]`%, has_content=FALSE 그룹에서 `[DATA]`%로 나타났다. 50개 테스트 쿼리에 대한
4조건(A/B/C/D) Ablation 검색 실험에서 VLM 메타를 추가한 조건 C는 API 메타만 사용한
조건 A 대비 MRR@10을 `[DATA: Δ]` 변화시켰다(Friedman 검정, `[DATA: p-value]`). VLM
채널이 포착한 신규 정보가 실제 검색 성능 향상으로 얼마나 이어지는지, 그리고 이
관계가 트랜스크립트 유무에 따라 달라지는지를 논의한다.

**Keywords:** vision-language model, VLM, thumbnail metadata generation, multimodal
complementarity, Jaccard similarity, novel information ratio, Korean YouTube, information
retrieval, Groq Vision API

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

YouTube 메타데이터 자동 생성 연구는 주로 트랜스크립트 텍스트를 LLM에 입력해 요약·
키워드·카테고리 등을 생성하는 방식(P03)에 집중되어 왔다. 그러나 트랜스크립트는
음성으로 언급된 정보만 담을 뿐, 썸네일에 등장하는 **제품·인물·감성 톤·레이아웃
구성처럼 화자가 말로 설명하지 않는 시각 정보**는 포착하지 못한다. 예를 들어
발표자의 표정, 제품 클로즈업 사진, 비교 다이어그램 같은 요소는 트랜스크립트
텍스트만으로는 재구성할 수 없다.

비전-언어 모델(VLM)은 이미지에서 자유형식 텍스트를 생성할 수 있어 이 공백을 메울
후보로 자연스럽다. 그러나 VLM을 이용해 썸네일에서 **구조화된** 메타데이터를
추출하고, 이를 트랜스크립트 기반 메타데이터와의 **보완 관계**로 정량화하며, 최종적
으로 검색 성능 향상까지 이어지는지를 end-to-end로 검증한 연구는 확인되지 않는다.
또한 GPU 없는 환경에서 무료 Vision API(Groq)만으로 이 파이프라인이 실용적으로
구현 가능한지에 대한 실증도 그 자체로 연구 가치가 있다 — 특히 한국어 YouTube
콘텐츠에 대한 JSON 구조화 출력의 안정성은 사전에 보장되지 않는다.

### 1.2 연구 질문

> "VLM이 썸네일에서 추출한 시각 메타데이터는 트랜스크립트가 포착하지 못하는 신규
> 정보를 충분히 포함하며, 이를 추가했을 때 검색 성능이 유의미하게 향상되는가?"

이 질문은 두 하위 질문으로 나뉜다. (1) VLM 메타데이터 자체의 생성 품질이 실용
수준인가? (2) 신규 정보의 "양"(신규 정보 비율)이 실제 검색 성능 향상이라는 "효과"
로 전환되는가? 특히 트랜스크립트가 아예 없는 영상(`has_content=FALSE`)에서 VLM이
대체 정보원으로 기능할 수 있는지를 별도로 검증한다.

### 1.3 기여점 (Contributions)

1. VLM 썸네일 메타데이터 4종 추출 파이프라인 구축 (visual_summary · dominant_objects
   · visual_emotion · layout_type), Groq Vision API(`llava-v1.5-7b`) 기반
2. 트랜스크립트 LLM 메타(P03) vs. VLM 썸네일 메타의 정보 보완성을 Jaccard 기반
   신규 정보 비율로 정량화
3. 트랜스크립트 없는 영상(`has_content=FALSE`)에서 VLM의 대체 정보원 가능성을
   `has_content` 그룹별 비교 실험으로 실증
4. 4조건(A/B/C/D) Ablation 검색 실험을 통해 VLM 메타 추가가 실제 검색 정확도
   (MRR@10 · NDCG@10)에 기여하는지를 통계적으로 검증
5. Groq Vision API 무료 tier로의 실용적 파이프라인 구현과 `meta_youtube_video_ai`
   테이블로의 스키마 확장 설계를 통해 운영 환경 적용 가능성을 평가

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Liu et al. (2023). "Visual Instruction Tuning (LLaVA)." *NeurIPS*, 36. | 시각 인스트럭션 튜닝으로 이미지에 대한 자유형식 질문 응답이 가능한 VLM 공개. 한국어 입력·출력 지원 가능. | 한국어 YouTube 도메인 구조화 메타데이터 추출 평가 없음 |
| Zhu et al. (2023). "MiniGPT-4: Enhancing Vision-Language Understanding with Advanced Large Language Models." arXiv:2304.10592. | 소형(7B) VLM으로 고품질 이미지 설명·추론 가능함을 보임. | 제목·썸네일 간 보완 관계 분석 없음 |
| Radford et al. (2021). "Learning Transferable Visual Models From Natural Language Supervision (CLIP)." *ICML*. | 이미지-텍스트 정렬 모델로 이미지 분류·검색에 광범위하게 활용. | 구조화 메타데이터(자유 형식 텍스트) 생성 불가 — 유사도 계산만 가능 |
| Zhang et al. (2023). "Video-LLaMA: An Instruction-tuned Audio-Visual Language Model for Video Understanding." *EMNLP (Demo)*. | 비디오 프레임+오디오를 LLM에 결합해 영상 내용을 이해. | 썸네일 단일 이미지 기반 구조화 메타 추출의 실용성 평가 없음; 프레임+오디오 처리 비용이 큼 |

### 2.1 선행 연구 대비 위치 (Positioning)

- 기존 VLM 연구(LLaVA, MiniGPT-4)는 일반 이미지 이해 능력 향상 자체에 집중하며,
  한국어 YouTube 썸네일이라는 특정 도메인에서 **구조화된 4종 메타데이터**를
  추출하는 프롬프트 설계와 그 실용성을 검증하지 않는다.
- CLIP류 이미지-텍스트 정렬 모델은 유사도 계산에는 강하지만 `visual_summary` 같은
  자유형식 서술이나 `layout_type` 같은 범주형 라벨을 직접 생성하지 못한다 —
  본 연구는 구조화 텍스트 생성이 가능한 instruction-tuned VLM을 사용한다는 점에서
  다르다.
- Video-LLaMA 등 비디오 전체를 다루는 멀티모달 모델은 프레임 시퀀스+오디오
  처리가 필요해 연산 비용이 크다. 본 연구는 **썸네일 단일 이미지**만으로 파이프
  라인을 구성해 GPU 없는 환경(Groq 무료 tier)에서도 실용적으로 구현 가능한지를
  검증한다는 점에서 실무 지향적이다.
- 트랜스크립트 기반 메타(P03)와 VLM 썸네일 메타 사이의 정보 보완성을 Jaccard
  기반 지표로 정량화하고, 이것이 실제 검색 성능 향상(MRR@10 · NDCG@10)으로
  이어지는지를 end-to-end로 검증한 선행 연구는 확인되지 않는다.

---

## 3. 제안 방법 (Methodology)

### 3.1 VLM 추론 파이프라인

```
썸네일 URL 다운로드
    ↓
Groq Vision API (llava-v1.5-7b) 호출
    ↓ 프롬프트:
    "다음 YouTube 썸네일을 분석하여 JSON 형식으로 출력하라:
     visual_summary (1문장), dominant_objects (최대 3개 배열),
     visual_emotion (positive/neutral/dramatic/humorous 중 1개),
     layout_type (face-centered/diagram/product/collage 중 1개)"
    ↓
JSON 파싱 → meta_youtube_video_ai 확장 컬럼에 저장
```

4종 메타데이터는 각각 다른 역할을 한다. `visual_summary`는 자유형식 서술로 신규
정보 비율 계산의 원천 키워드를 제공하고, `dominant_objects`는 검색 인덱싱에 직접
활용 가능한 명사구를 제공하며, `visual_emotion`·`layout_type`은 범주형 라벨로
콘텐츠 톤 분석에 활용된다.

### 3.2 정보 보완성 분석

```
LLM 트랜스크립트 키워드 집합: K_transcript  (P03 파이프라인 산출물)
VLM 썸네일 키워드 집합:       K_visual      (visual_summary + dominant_objects에서 추출)

Jaccard 유사도  = |K_transcript ∩ K_visual| / |K_transcript ∪ K_visual|
신규 정보 비율  = |K_visual \ K_transcript| / |K_visual|
```

신규 정보 비율이 높을수록 두 채널이 상호 보완적임을 의미한다. 이 지표는
`has_content=TRUE`(트랜스크립트 존재) 그룹과 `has_content=FALSE`(트랜스크립트
부재) 그룹 각각에 대해 별도로 계산한다 — 후자는 `K_transcript`가 공집합에
가까우므로 신규 정보 비율이 구조적으로 높게 나올 것으로 예상되며, 이는 VLM이
대체 정보원으로 기능할 수 있는지를 보여주는 핵심 근거가 된다.

### 3.3 Ablation 검색 실험 설계

```
조건 A: API 메타만 (제목 + 설명 + 태그)
조건 B: A + 트랜스크립트 LLM 메타 (P03 방법)
조건 C: A + VLM 썸네일 메타 (제안 방법)
조건 D: A + B + C (전체 결합)
```

조건 C와 조건 A의 비교가 "VLM 메타 자체의 검색 기여도"를, 조건 D와 조건 B의
비교가 "이미 트랜스크립트 메타가 있는 상태에서 VLM 메타를 추가로 넣는 한계
기여도(marginal contribution)"를 보여준다. 4조건 모두 동일한 임베딩 모델·검색
파이프라인을 사용하며 메타데이터 구성만 다르게 한다.

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| VLM 파이프라인 적용 영상 수 | `[DATA: N]` |
| `has_content=TRUE` 영상 수 | `[DATA]` |
| `has_content=FALSE` 영상 수 | `[DATA]` |
| 인간 품질 평가 대상 영상 수 | `[DATA: 100]` (전체 중 무작위 표집) |
| GPT-4V 병행 평가 대상 | 위 100편과 동일 |
| 평가자 수 | 3인 (독립 평가 후 평균) |
| 테스트 쿼리 수 (Ablation) | `[DATA: 50]` |
| qrels 레이블링 방식 | 상위 후보 × 2인 독립 평가 |
| 데이터 소스 | `meta_youtube_video`, `meta_youtube_video_ai` |

### 4.2 실험 절차

1. **VLM 메타데이터 생성** — 전체 `[DATA: N]`편에 대해 Groq Vision API로 4종
   메타데이터를 생성하고 `meta_youtube_video_ai` 확장 컬럼에 적재. JSON 파싱
   실패율을 함께 기록.
2. **인간 품질 평가 (실험 1)** — 100편의 `visual_summary`를 3인이 정확성·구체성·
   유용성 기준 1–5점으로 평가. GPT-4V 생성 결과를 동일 기준으로 병행 평가해
   upper bound baseline으로 삼는다.
3. **정보 보완성 분석 (실험 2)** — `has_content=TRUE`/`FALSE` 그룹 각각에서
   신규 정보 비율을 계산해 비교.
4. **4조건 Ablation 검색 실험 (실험 3)** — 50개 테스트 쿼리로 A·B·C·D 조건의
   MRR@10·NDCG@10을 측정하고 Friedman 검정으로 조건 간 유의 차이를 확인.

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상

| 방법 | 설명 |
|------|------|
| 조건 A (Baseline) | API 메타데이터 텍스트 임베딩만 |
| 조건 B | A + 트랜스크립트 LLM 메타 (P03 방법) |
| 조건 C | A + VLM 썸네일 메타 (제안 방법) |
| 조건 D | A + B + C (최대 결합) |

### 5.2 측정 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| Human Rating (1–5) | VLM 메타데이터 품질 | 자동 지표가 없는 생성 품질의 직접 측정 |
| GPT-4V Rating (1–5) | Upper bound 대비 상대 품질 | 무료 tier VLM의 품질 손실 정도 파악 |
| 신규 정보 비율 (%) | VLM 전용 키워드 비율 | 보완성의 정도를 정량화 |
| MRR@10 | 검색 정확도 | 생성 메타가 실제 검색에 기여하는지 |
| NDCG@10 | 검색 순위 품질 | 전반적 결과 목록 품질 향상 측정 |
| Friedman p-value | 4조건 간 차이 유의성 | 조건별 성능 차이가 우연이 아님을 확인 |
| JSON 파싱 성공률 · API 오류율 | 파이프라인 실용성 | 무료 tier에서의 운영 가능성 판단 |

### 5.3 주요 개념 설명

**Jaccard 유사도**
두 집합의 겹침 정도를 측정하는 지표. `|교집합| / |합집합|`. 0이면 완전히 다르고,
1이면 완전히 같다. 여기서는 LLM 트랜스크립트 키워드 집합과 VLM 썸네일 키워드
집합이 얼마나 겹치는지를 측정한다. Jaccard가 낮을수록 두 채널이 서로 다른 정보를
담고 있어 보완 관계가 강하다는 의미다.

**신규 정보 비율**
`|K_visual \ K_transcript| / |K_visual|` — VLM이 찾아낸 키워드 중 LLM에는 없는
것의 비율. 신규 정보 비율 = 40%이면 VLM 키워드의 40%가 트랜스크립트에 없는
시각 전용 정보라는 뜻이다. 이 값이 30% 이상이어야 VLM을 추가하는 가치가 있다고
판단한다.

**Friedman 검정**
세 그룹 이상의 반복 측정 비교를 위한 비모수 검정. ANOVA의 비모수 버전(paired
데이터용). 여기서는 A/B/C/D 4조건에 대해 동일한 50개 쿼리를 적용한 MRR@10 값이
조건 간에 통계적으로 다른지를 검정한다. 정규 분포 가정 없이 순위 기반으로
검정하므로 소규모 실험에 적합하다. p < 0.05이면 4조건 중 적어도 하나가 다른
조건과 유의미하게 다른 검색 성능을 보인다. 단, 이는 "어딘가 차이가 있다"는
것만 알려줄 뿐 어느 조건 쌍이 다른지는 별도의 사후 검정(post-hoc, 예: Wilcoxon
signed-rank + Bonferroni 보정)이 필요하다.

### 5.4 해석 기준 (성공 조건)

- Human Rating 평균 ≥ 3.5 → 실용 수준의 VLM 메타데이터 품질
- 신규 정보 비율 > 30% → 트랜스크립트와 충분히 독립적인 정보 제공
- 조건 C가 조건 A 대비 MRR@10 > +0.03 → VLM 메타의 검색 기여 입증

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 VLM 메타데이터 품질 인간 평가

| 평가 기준 | VLM (Groq llava-v1.5-7b) | GPT-4V (upper bound) |
|-----------|---------------------------|------------------------|
| 정확성 | `[DATA]` | `[DATA]` |
| 구체성 | `[DATA]` | `[DATA]` |
| 유용성 | `[DATA]` | `[DATA]` |
| **평균** | **`[DATA]`** | **`[DATA]`** |

평가자 간 일치도: `[DATA: Krippendorff's alpha 또는 ICC]`

### 6.2 정보 보완성 분석 (신규 정보 비율)

| 그룹 | 신규 정보 비율 | Jaccard 유사도 | 표본 수 |
|------|---------------|----------------|---------|
| `has_content=TRUE` | `[DATA]`% | `[DATA]` | `[DATA]` |
| `has_content=FALSE` | `[DATA]`% | `[DATA]` | `[DATA]` |
| 전체 | `[DATA]`% | `[DATA]` | `[DATA: N]` |

`[DATA: 두 그룹 간 차이의 통계적 유의성 검정(예: Mann-Whitney U) 결과 삽입]`

### 6.3 4조건 Ablation 검색 실험

| 조건 | 설명 | MRR@10 | NDCG@10 |
|------|------|--------|---------|
| A | API 메타만 | `[DATA]` | `[DATA]` |
| B | A + 트랜스크립트 LLM 메타 | `[DATA]` | `[DATA]` |
| C | A + VLM 썸네일 메타 | `[DATA]` | `[DATA]` |
| D | A + B + C | `[DATA]` | `[DATA]` |

Friedman 검정 (4조건, MRR@10): `[DATA: 통계량, p-value]`

조건 C − 조건 A (MRR@10 차이): `[DATA: Δ]` (해석 기준: > +0.03)

### 6.4 `has_content` 그룹별 VLM 기여도 세부 분석

트랜스크립트 유무에 따라 VLM 메타(조건 C)의 조건 A 대비 기여도가 다른지를
별도로 확인한다.

| 그룹 | 조건 A MRR@10 | 조건 C MRR@10 | Δ(C−A) |
|------|---------------|---------------|--------|
| `has_content=TRUE` | `[DATA]` | `[DATA]` | `[DATA]` |
| `has_content=FALSE` | `[DATA]` | `[DATA]` | `[DATA]` |

### 6.5 정성적 사례 분석

`[DATA: VLM 메타가 검색에 크게 기여한 사례 1~2건, VLM 메타의 신규 정보 비율은
높았지만 검색 기여가 미미했던(가설과 어긋나는) 사례 1건, 썸네일 이미지 설명
포함]`

### 6.6 파이프라인 실용성 (Groq Vision API)

| 항목 | 값 |
|------|-----|
| JSON 파싱 성공률 | `[DATA]`% |
| API 오류율(rate limit/timeout 등) | `[DATA]`% |
| 영상당 평균 추론 시간 | `[DATA]` |
| 무료 tier 처리 가능 영상 수/일 | `[DATA]` |
| 총 소요 시간 (`[DATA: N]`편 기준) | `[DATA]` |

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 인간 평가 품질이 해석 기준(≥3.5)을 충족했는지, GPT-4V 대비 격차의 크기와 실무적
  의미
- 신규 정보 비율이 해석 기준(>30%)을 충족했는지, `has_content` 그룹 간 차이가
  기대(트랜스크립트 부재 그룹에서 더 높음)와 일치하는지
- 신규 정보 비율(정보의 "양")과 조건 C의 MRR@10 향상폭(정보의 "효과")이 서로
  얼마나 일치하는지 — 만약 신규 정보 비율은 높은데 검색 성능 향상이 기준(+0.03)에
  못 미친다면, 그 이유(예: 신규 키워드가 쿼리 분포와 무관, 임베딩 표현력 한계 등)
- `has_content=FALSE` 그룹에서의 VLM 기여도가 전체 평균과 다른 양상을 보이는지,
  이것이 "트랜스크립트 부재 시 VLM 대체 활용"이라는 기여점을 얼마나 뒷받침하는지
- 조건 D(전체 결합)가 조건 B 대비 얼마나 추가 개선을 보이는지 — VLM의 한계
  기여도(marginal contribution) 평가
- Groq Vision API 무료 tier의 운영 실용성(오류율·처리량)이 실제 파이프라인
  적용에 걸림돌이 되는지

## 8. 한계 (Limitations)

- 인간 품질 평가 대상이 100편, 평가자 3인으로 제한적 — 통계적 검정력의 한계
- GPT-4V를 upper bound로 사용했으나 이 역시 완벽한 gold standard는 아님 —
  GPT-4V 자체의 한국어 이미지 이해 오류 가능성을 배제하지 못함
- Jaccard 기반 신규 정보 비율은 표층 키워드 일치만 측정하며, 의미적으로 동일하나
  표현이 다른 키워드(동의어·형태 변이)를 신규 정보로 잘못 카운트할 가능성이 있다
- Groq `llava-v1.5-7b`는 소형 VLM으로, 프롬프트에 명시한 4종 항목 외의 세부
  시각 정보(텍스트 오버레이, 작은 배경 요소 등)를 놓칠 수 있다
- 4조건 Ablation은 50개 쿼리에 한정되어 조건 간 미세한 차이를 검출할 통계적
  검정력이 부족할 수 있다
- 한국어 YouTube 콘텐츠 중에서도 특정 채널·주제에 편중된 표본일 경우 일반화에
  한계가 있다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 (VLM 메타 품질, 신규 정보 비율, 검색 기여도) + 향후
확장 방향]`

향후 확장성:
- 뉴스 기사 대표 이미지로 확장 (`meta_naver_news` 이미지 URL 수집)
- 썸네일 A/B 변경 탐지: VLM 설명이 달라지면 썸네일 교체를 자동 감지
- 제품 인식 결과를 Naver 쇼핑 카테고리에 자동 매핑

---

## 참고문헌 (References)

1. Liu, H., Li, C., Wu, Q., & Lee, Y. J. (2023). Visual Instruction Tuning (LLaVA). *NeurIPS*, 36.
2. Zhu, D., Chen, J., Shen, X., Li, X., & Elhoseiny, M. (2023). MiniGPT-4: Enhancing Vision-Language Understanding with Advanced Large Language Models. arXiv:2304.10592.
3. Radford, A., et al. (2021). Learning Transferable Visual Models From Natural Language Supervision (CLIP). *ICML*.
4. Zhang, H., Li, X., & Bing, L. (2023). Video-LLaMA: An Instruction-tuned Audio-Visual Language Model for Video Understanding. *EMNLP (Demo)*.

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 데이터셋 규모 (N, has_content TRUE/FALSE 분할, 쿼리 수) 확정
- [ ] 6.1 VLM/GPT-4V 인간 평가 점수표 삽입, 평가자 간 일치도 삽입
- [ ] 6.2 신규 정보 비율(그룹별) 및 유의성 검정 삽입
- [ ] 6.3 4조건 Ablation MRR@10/NDCG@10 삽입, Friedman 검정 통계량/p-value 삽입
- [ ] 6.4 `has_content` 그룹별 VLM 기여도(Δ) 삽입
- [ ] 6.5 정성적 사례 작성 (기여 큰 사례 + 반례)
- [ ] 6.6 Groq Vision API 실용성 지표(파싱 성공률·오류율·처리 시간) 삽입
- [ ] 7장 논의 작성 — 특히 "신규 정보 비율(양) vs. 검색 기여(효과)" 불일치 여부 검토
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 제출 전 novelty 재검색 (P05와 마찬가지로 최근 VLM 썸네일 메타 관련 연구 확인)
