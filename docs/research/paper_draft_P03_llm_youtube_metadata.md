# 논문 초안: LLM 기반 한국어 YouTube 콘텐츠 메타데이터 자동 생성

> 기반 기획서: [research_proposals.md](./research_proposals.md) P03
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)

---

## 제목 (Title)

**영문:** *Automated Korean Metadata Enrichment for YouTube Videos via LLM-Based Transcript Analysis*

**국문:** LLM 기반 트랜스크립트 분석을 통한 한국어 YouTube 영상 메타데이터 자동 보강

---

## Abstract

YouTube video metadata (title, description, tags) is uploader-supplied and frequently suffers from
keyword stuffing or mismatch with actual content. Automatic speech recognition (ASR/STT)
transcripts are available but Korean STT output is heavily degraded by domain-specific
terminology misrecognition. We present a pipeline that extracts structured metadata — a
summary, keywords, named entities, and a content-type label — from noisy Korean STT
transcripts using open-weight large language models (LLMs), and evaluate the pipeline on a
corpus of `[DATA: N videos]` videos spanning technology, medical, and news domains, together
with `[DATA: 50]` retrieval query-relevance pairs. We compare two free-tier Groq-hosted models
(llama-3.1-8b, gemma2-9b) against a paid quality ceiling (GPT-4o-mini) on metadata quality
(ROUGE-L, Keyword F1, NER F1, human rating) and, more importantly, on whether the generated
metadata measurably improves downstream retrieval quality (NDCG@5, MRR, Recall@10) when added
to a vector search index. Adding LLM-generated metadata improves NDCG@5 by
`[DATA: Δ]` over API-metadata-only retrieval (`[DATA: p-value]`, paired t-test), and we report
per-model human-rated usability together with processing cost and latency under Groq's free-tier
rate limits (14,400 requests/day).

**국문 초록 (draft):** YouTube 영상의 API 메타데이터(제목·설명·태그)는 업로더 입력값으로
키워드 스터핑이나 콘텐츠 내용과의 불일치가 빈번하다. 자동 자막(STT) 트랜스크립트가
있지만 한국어 STT는 전문 용어 오인식이 심해 그대로 쓰기 어렵다. 본 연구는 STT 노이즈가
심한 한국어 트랜스크립트에서 공개 LLM으로 요약·키워드·개체명·콘텐츠 유형 4종의 구조화
메타데이터를 자동 추출하는 파이프라인을 제안한다. 기술 `[DATA]`편, 의료 `[DATA]`편,
뉴스 `[DATA]`편으로 구성된 영상 `[DATA: N]`편과 검색 평가용 Query-Relevance 쌍
`[DATA: 50]`개로 평가한다. 무료 Groq API 모델(llama-3.1-8b, gemma2-9b)을 유료 품질
상한 기준(GPT-4o-mini)과 비교해 메타데이터 자체 품질(ROUGE-L, Keyword F1, NER F1,
인간 평가)을 측정하고, 무엇보다 이 메타데이터를 벡터 검색 인덱스에 추가했을 때 검색
정확도(NDCG@5, MRR, Recall@10)가 실제로 향상되는지를 검증한다. LLM 메타데이터 추가
시 NDCG@5가 API 메타데이터 단독 대비 `[DATA: Δ]` 향상되었으며(`[DATA: p-value]`,
paired t-test), Groq 무료 티어(일 14,400회) 제약 하에서의 처리 비용·응답 시간도 함께
보고한다.

**Keywords:** large language models, information extraction, Korean NLP, ASR noise, structured
metadata generation, retrieval augmentation, few-shot prompting, YouTube

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

YouTube API 메타데이터(제목·설명·태그)는 업로더 입력값이라는 태생적 한계를 갖는다.
검색 노출을 위한 키워드 스터핑이 흔하고, 실제 콘텐츠 내용과의 불일치도 빈번하다.
자동 자막(STT) 기반 트랜스크립트는 콘텐츠 내용을 더 충실히 반영할 잠재력이 있지만,
한국어 STT는 전문 용어 오인식이 심해 그대로 활용하기 어렵다. 최근 공개된 소규모
오픈소스 LLM(7B~9B급)은 few-shot·zero-shot 정보 추출에서 상당한 성능을 보이지만,
GPU 자원 없이 무료 API만으로 한국어 STT 노이즈 텍스트에서 고품질 구조화 메타데이터를
뽑아낼 수 있는지에 대한 실증 평가는 부족하다.

### 1.2 연구 질문

> LLM이 생성한 메타데이터를 추가했을 때, 트랜스크립트가 없는 API 메타데이터만
> 사용한 경우 대비 검색 정확도가 통계적으로 유의하게 향상되는가?

이 질문은 메타데이터 생성 자체의 품질(요약이 잘 되었는가, 키워드가 정확한가)과는
별개로, **그 메타데이터가 실제로 사용될 때 검색에 도움이 되는가**를 직접 겨냥한다.
생성 품질이 높아도 검색에 기여하지 못한다면 파이프라인 도입의 실익이 없기 때문이다.

### 1.3 기여점 (Contributions)

1. STT 노이즈 유형 분류 및 전처리 파이프라인 (타임스탬프 제거, 반복 구문 병합,
   토큰 수 기반 청킹)
2. 요약·키워드·개체명·콘텐츠 유형 4종을 동시에 추출하는 구조화 출력 프롬프트 설계
3. 무료 LLM(Groq: llama-3.1-8b, gemma2-9b)의 한국어 실용 성능 측정 — 유료 품질
   상한(GPT-4o-mini) 대비 상대 평가
4. LLM 메타데이터 추가 시 벡터 검색 품질 향상의 정량화 — 메타데이터 자체 품질과
   검색 기여도를 분리해서 평가

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 한계 |
|------|------|------|
| Brown et al. (2020). "Language Models are Few-Shot Learners (GPT-3)." *NeurIPS*, 33, 1877–1901. | 175B 파라미터 LLM의 few-shot 능력을 실증. 정보 추출·요약 등 다양한 NLP 태스크에서 인간 수준에 근접. | 한국어 전문 도메인·STT 노이즈 환경에서의 소규모 오픈소스 모델 적용 미검증 |
| Touvron et al. (2023). "Llama 2: Open Foundation and Fine-Tuned Chat Models." arXiv:2307.09288. | 7B–70B 오픈소스 LLM 공개. 상용 수준의 한국어 이해 가능성을 시사하나 성능 평가는 영어 벤치마크 중심. | 한국어 구조화 메타데이터 추출(요약+키워드+개체명 동시)의 실용성 평가 없음 |
| Wei et al. (2022). "Emergent Abilities of Large Language Models." *TMLR*. | 모델 규모가 일정 임계를 넘으면 복잡한 추론·추출 능력이 창발함을 분석. 소규모(8B 이하) 모델의 창발 한계 지점 미제시. | 8B 급 오픈소스 모델의 구조화 추출 안정성 평가 없음 |
| Raffel et al. (2020). "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer (T5)." *JMLR*, 21(140), 1–67. | 정보 추출을 text-to-text 프레임워크로 통일. 한국어 전문 용어 STT 오류 패턴에 대한 로버스트성 평가 없음. | 교착어 한국어 STT 노이즈 대응 전략 없음 |

### 2.1 선행 연구 대비 위치 (Positioning)

- GPT-3(Brown et al., 2020)와 Emergent Abilities(Wei et al., 2022)는 모델 규모가
  정보 추출 능력에 미치는 영향을 실증했지만, 평가는 대체로 영어 벤치마크에 국한된다.
  본 연구는 이 창발 능력이 **한국어·8~9B급 오픈소스 모델·STT 노이즈**라는 훨씬 어려운
  조건에서도 실용 수준으로 나타나는지를 직접 측정한다.
- Llama 2(Touvron et al., 2023)는 오픈소스 LLM의 한국어 이해 가능성을 시사하지만
  요약·키워드·개체명을 동시에 요구하는 구조화 추출 과제에서의 실용성은 검증되지 않았다.
- T5(Raffel et al., 2020)의 text-to-text 통일 프레임워크는 정보 추출 과제 일반에
  적용 가능하지만, 교착어인 한국어의 STT 오류 패턴(조사 누락, 전문 용어 음차 오인식
  등)에 대한 로버스트성은 검토된 바 없다.
- 무엇보다, 이들 선행 연구는 모두 **생성된 메타데이터 자체의 품질**을 평가 대상으로
  삼을 뿐, 그 메타데이터가 실제 하위 응용(검색)에서 성능 향상으로 이어지는지는
  다루지 않는다. 기존 연구들은 대용량 영어 중심 벤치마크에서의 성능 평가에 집중하며,
  GPU 자원이 없는 환경에서 소규모 오픈소스 LLM으로 한국어 STT 노이즈 텍스트로부터
  구조화 메타데이터를 추출하고 이를 검색 품질 향상으로 연결하는 실용적 파이프라인을
  평가한 연구는 확인되지 않는다.

---

## 3. 제안 방법 (Methodology)

### 3.1 파이프라인 구성

```
[youtube-transcript-api] → 원시 트랜스크립트
        ↓ 전처리
  - 타임스탬프 제거
  - 반복 구문 병합 (STT 버벅임 제거)
  - 토큰 수 계산 → 16K 초과 시 청킹
        ↓ LLM 호출 (Groq API)
  프롬프트: "아래 YouTube 트랜스크립트를 분석하여 JSON으로 반환하라.
             {summary, keywords, entities, content_type}"
        ↓ 파싱 및 검증
  - JSON schema validation
  - 빈 필드 fallback 처리 (title+description으로 재시도)
        ↓
  meta_youtube_video_ai 테이블 저장
```

전처리 단계는 한국어 STT 특유의 노이즈(전문 용어 오인식, 동일 구문 반복, 외래어
표기 흔들림)를 LLM 호출 이전에 최대한 걷어내, 제한된 컨텍스트 윈도우와 무료 API
호출 횟수를 효율적으로 쓰기 위한 장치다. 파싱 및 검증 단계는 LLM 출력이 JSON
스키마를 벗어나거나 특정 필드가 비는 경우를 대비한 안전장치로, 실패 시
title+description만으로 재시도하는 fallback을 둔다.

### 3.2 Long Context 처리 전략

한국어 강의·인터뷰형 콘텐츠는 트랜스크립트 길이가 수만 토큰에 달할 수 있어, 단일
LLM 호출의 컨텍스트 한계와 무료 API의 요청당 토큰 제한을 함께 고려한 길이별 전략이
필요하다.

| 트랜스크립트 길이 | 전략 |
|----------------|------|
| ≤ 8K 토큰 | 전체 입력 |
| 8K ~ 32K 토큰 | Map-Reduce: 청크별 요약 → 최종 통합 |
| > 32K 토큰 | 앞·중간·뒤 3구간 샘플링 후 통합 |

### 3.3 구조화 출력 프롬프트

프롬프트는 요약(3문장 내외)·키워드(5~10개)·개체명(인물/기관/제품/기술 용어)·콘텐츠
유형(예: 강의, 리뷰, 뉴스, 인터뷰 등) 4개 필드를 하나의 JSON 객체로 동시에 요구한다.
4종을 한 번의 호출로 묶어 요청하는 이유는 무료 API의 일일 요청 한도(Groq 14,400
req/day) 안에서 영상당 호출 횟수를 최소화하기 위함이며, Map-Reduce 청킹이 필요한
경우에도 청크별로는 동일한 스키마를 유지하고 최종 통합 단계에서만 필드별로 병합한다.

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| 영상 수 | `[DATA: N]` (제안서 목표: 200편 이상 — 기술 100편 + 의료 50편 + 뉴스 50편) |
| 인간 레퍼런스 | 영상별 3문장 요약, 5~10개 키워드, 개체명 목록 (평가자 2인, 불일치 시 제3자 조정) |
| 검색 평가용 Query-Relevance 쌍 | `[DATA: 50]`개 (예: "HBM 제조 공정을 설명하는 영상") |
| 데이터 소스 | `meta_youtube_video`, `youtube-transcript-api` 원시 트랜스크립트 |

### 4.2 조건 비교

```
조건 A: 제목 + 설명 + 태그 (API 메타데이터만)
조건 B: 조건 A + LLM 요약 + 키워드
조건 C: 조건 B + 개체명 + 콘텐츠 유형
```

### 4.3 LLM 비교

```
llama-3.1-8b   (Groq, 무료)
gemma2-9b      (Groq, 무료)
GPT-4o-mini    (유료, 품질 상한 기준)
```

### 4.4 실험 절차

1. **데이터 구축** — 영상 `[DATA: N]`편의 트랜스크립트 수집·전처리, 인간 레퍼런스
   (요약·키워드·개체명) 2인 독립 작성 후 불일치 조정.
2. **메타데이터 생성** — 3개 LLM 각각으로 전체 영상에 대해 요약·키워드·개체명·콘텐츠
   유형을 생성, JSON schema validation 및 fallback 적용.
3. **메타데이터 품질 평가** — LLM별 출력을 인간 레퍼런스와 비교(ROUGE-L, Keyword F1,
   NER F1) 및 5점 척도 인간 평가.
4. **검색 인덱싱 및 평가** — 조건 A/B/C 각각으로 영상 `[DATA: N]`편을 임베딩·인덱싱하고
   Query-Relevance 쌍 `[DATA: 50]`개로 NDCG@5/MRR/Recall@10 측정.
5. **처리 효율 측정** — LLM별 영상 1편당 평균 API 호출 횟수, 응답 시간 기록.

---

## 5. 평가 방법 (Evaluation)

### 5.1 평가 1: 메타데이터 품질 (생성 자체의 품질)

이 평가는 "LLM이 올바른 메타데이터를 생성하는가"를 측정한다.

| 지표 | 측정 대상 | 계산 방법 |
|------|----------|---------|
| ROUGE-L | 요약 품질 | LLM 요약 vs. 인간 레퍼런스 요약의 최장 공통 부분 수열 |
| Keyword F1 | 키워드 적중률 | LLM 키워드 ∩ 인간 키워드 / Union |
| NER F1 | 개체명 인식 정확도 | LLM 개체명 vs. 인간 레이블 |
| 인간 평가 (5점) | 전반적 유용성 | 관련성·정확성·완결성 항목 |

### 5.2 평가 2: 검색 품질 향상 (메타데이터가 검색에 도움이 되는가)

이 평가가 핵심이다. 메타데이터 자체의 품질보다 **실제로 사용할 때 더 잘 찾아지는가**가
중요하다.

```
실험 절차:
1. 조건 A/B/C 각각으로 영상 [DATA: N]편을 임베딩·인덱싱
2. [DATA: 50]개 검색 쿼리를 각 조건에서 실행
3. 결과 상위 10개와 정답셋(관련 영상 목록) 비교
```

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| NDCG@5 | 상위 5개 결과의 순위 품질 | 사용자는 보통 상위 몇 개만 확인 |
| MRR | 첫 번째 관련 결과의 순위 역수 평균 | 정확한 답을 얼마나 빨리 찾는지 |
| Recall@10 | 정답 중 상위 10개 안에 있는 비율 | 놓치는 관련 결과가 없는지 |

### 5.3 주요 개념 설명

**ROUGE-L**
자동 텍스트 요약 평가 지표. 생성된 요약과 인간이 작성한 레퍼런스 요약 사이의 최장
공통 부분 수열(LCS, Longest Common Subsequence)을 기준으로 F1을 계산한다. 값이
높을수록 두 요약이 비슷한 흐름과 단어를 사용한다는 뜻. 단, 표현이 달라도 의미가
같은 경우(paraphrase)는 낮게 평가될 수 있다는 한계가 있다.

**F1 (Keyword F1, NER F1)**
Precision(정밀도)과 Recall(재현율)의 조화 평균.
- Precision: 모델이 예측한 키워드 중 인간 레이블과 일치하는 비율 (틀린 것을 얼마나
  줄였는가)
- Recall: 인간 레이블 키워드 중 모델이 맞춘 비율 (맞아야 할 것을 얼마나 맞췄는가)

F1 = 2 × (Precision × Recall) / (Precision + Recall). 둘 다 높아야 F1이 높다.

**NDCG@5 (Normalized Discounted Cumulative Gain at 5)**
검색 결과 상위 5개의 순위 품질을 측정. 관련도가 높은 결과가 순위가 높을수록 점수가
높다. "할인(discounting)": 1위 결과는 5위보다 더 크게 기여한다 (log 함수 기반
감쇄). 이상적 순위와의 비율로 정규화해 0~1 범위로 표현. NDCG@5 = 1.0이면 관련도
높은 결과가 완벽하게 상위에 정렬된 상태.

**MRR (Mean Reciprocal Rank)**
첫 번째 관련 결과가 몇 위에 나타나는지의 역수 평균. 1위 = 1.0 / 2위 = 0.5 / 3위 =
0.33 / 10위 = 0.1 / 없으면 0. 사용자가 얼마나 빨리 첫 번째 정답을 만나는지 측정.
NDCG와의 차이: NDCG는 전체 목록 품질을 보지만, MRR은 "처음 정답을 만나는 속도"에만
집중한다.

### 5.4 해석 기준 (성공 조건)

- NDCG@5: 조건 C > 조건 A에서 Δ ≥ 0.05 (paired t-test p < 0.05)
- LLM 인간 평가: llama-3.1-8b 평균 3.5/5.0 이상 (실용 수준)
- 처리 효율: 영상 1편당 Groq 호출 ≤ 3회, 응답 시간 ≤ 10초

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 메타데이터 품질 (LLM별)

| 모델 | ROUGE-L | Keyword F1 | NER F1 | 인간 평가 (5점) |
|------|---------|-----------|--------|----------------|
| llama-3.1-8b (무료) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| gemma2-9b (무료) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| GPT-4o-mini (유료, 상한) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |

해석 기준(llama-3.1-8b 인간 평가 ≥ 3.5) 충족 여부: `[DATA]`

### 6.2 도메인별 메타데이터 품질 세부 (선택 모델 기준)

| 도메인 | ROUGE-L | Keyword F1 | NER F1 |
|--------|---------|-----------|--------|
| 기술 | `[DATA]` | `[DATA]` | `[DATA]` |
| 의료 | `[DATA]` | `[DATA]` | `[DATA]` |
| 뉴스 | `[DATA]` | `[DATA]` | `[DATA]` |

### 6.3 검색 품질 향상 (조건별)

| 조건 | NDCG@5 | MRR | Recall@10 |
|------|--------|-----|-----------|
| A (API 메타데이터만) | `[DATA]` | `[DATA]` | `[DATA]` |
| B (A + 요약 + 키워드) | `[DATA]` | `[DATA]` | `[DATA]` |
| C (B + 개체명 + 콘텐츠 유형) | `[DATA]` | `[DATA]` | `[DATA]` |

Δ(NDCG@5, C − A) = `[DATA]` / paired t-test: `[DATA: t-statistic, p-value]`

해석 기준(Δ NDCG@5 ≥ 0.05, p < 0.05) 충족 여부: `[DATA]`

### 6.4 처리 효율

| 모델 | 영상당 평균 API 호출 횟수 | 평균 응답 시간 | 일일 처리 가능 영상 수 (14,400 req/day 기준) |
|------|--------------------------|---------------|----------------------------------------|
| llama-3.1-8b | `[DATA]` | `[DATA]` | `[DATA]` |
| gemma2-9b | `[DATA]` | `[DATA]` | `[DATA]` |
| GPT-4o-mini | `[DATA]` | `[DATA]` | `[DATA]` |

해석 기준(호출 ≤ 3회, 응답 시간 ≤ 10초) 충족 여부: `[DATA]`

### 6.5 정성적 사례 분석

`[DATA: 메타데이터 품질과 검색 기여도가 서로 다른 방향을 가리키는 사례 1~2건
(예: 특정 지표는 낮지만 검색에는 도움이 된 경우, 또는 그 반대), 트랜스크립트/
쿼리 예시 포함]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 조건 C의 검색 품질 향상이 개체명·콘텐츠 유형 추가분에서 기인하는지, 아니면 이미
  조건 B(요약+키워드)에서 대부분의 향상이 발생하는지
- 메타데이터 품질 지표(ROUGE-L, F1)와 검색 기여도(NDCG@5 Δ) 사이의 상관/괴리 여부 —
  품질이 낮은 필드가 검색에는 기여할 수 있는지, 혹은 그 반대
- llama-3.1-8b와 gemma2-9b 간 성능 차이가 해석 기준(인간 평가 3.5/5.0) 충족 여부에
  실질적으로 영향을 미치는지
- 도메인별(기술/의료/뉴스) 성능 편차의 원인 — 특히 의료 도메인 전문 용어 STT
  오인식이 개체명 인식에 미치는 영향
- Groq 무료 티어 제약 하에서 실제 운영 규모로 확장했을 때의 병목

## 8. 한계 (Limitations)

- 인간 레퍼런스 및 Query-Relevance 쌍 구축이 가장 큰 병목이며, 평가자 2인 규모로는
  통계적 검정력에 한계가 있다
- Groq API rate limit(14,400 req/day) 하에서의 측정으로, 상용 유료 티어나 온프레미스
  배포 환경의 처리량과는 다를 수 있다
- 개체명 인식 레이블은 인간 평가자의 주관적 판단에 의존하며, 전문 용어(의료·기술)
  경계 판단에 평가자 간 불일치가 존재할 수 있다
- STT 노이즈 유형 분류는 사전에 관찰된 패턴(전문 용어 오인식, 반복 구문 등)에
  기반하며, 데이터셋에 없는 새로운 노이즈 유형에는 일반화되지 않을 수 있다
- Query-Relevance 쌍 `[DATA: 50]`개는 특정 도메인(기술 중심)에 편중되었을 가능성이
  있다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- 영상 썸네일 비전 결합 멀티모달 메타데이터
- 트랜스크립트 변경 감지 시 자동 재생성 파이프라인

---

## 참고문헌 (References)

1. Brown, T. B., et al. (2020). Language Models are Few-Shot Learners. *NeurIPS*, 33, 1877–1901.
2. Touvron, H., et al. (2023). Llama 2: Open Foundation and Fine-Tuned Chat Models. arXiv:2307.09288.
3. Wei, J., et al. (2022). Emergent Abilities of Large Language Models. *TMLR*.
4. Raffel, C., et al. (2020). Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer. *JMLR*, 21(140), 1–67.

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 데이터셋 규모 (N, 도메인별 분포, Query-Relevance 쌍 수) 확정
- [ ] 6.1 LLM별 메타데이터 품질(ROUGE-L, Keyword F1, NER F1, 인간 평가) 수치 삽입
- [ ] 6.1 llama-3.1-8b 인간 평가 해석 기준 충족 여부 판정
- [ ] 6.2 도메인별 세부 품질 수치 삽입
- [ ] 6.3 조건 A/B/C 검색 품질(NDCG@5, MRR, Recall@10) 수치 삽입
- [ ] 6.3 paired t-test 통계량/p-value 삽입 및 해석 기준 충족 여부 판정
- [ ] 6.4 처리 효율(호출 횟수, 응답 시간, 일일 처리량) 실측치 삽입 및 해석 기준 판정
- [ ] 6.5 정성적 사례 작성
- [ ] 7장 논의 작성 (품질-검색기여도 괴리, 모델 간 차이, 도메인별 편차 포함)
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 제출 전 novelty 재검색 (2.1절 참고)
