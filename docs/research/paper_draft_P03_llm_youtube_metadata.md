# 논문 초안: LLM 기반 한국어 YouTube 콘텐츠 메타데이터 자동 생성

> 기반 기획서: [research_proposals.md](./research_proposals.md) P03
> 작성일: 2026-07-08 (v2: 인간 레퍼런스 기반 품질평가 제거 → 검색품질 평가로 단일화)
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)
>
> **v1 → v2 변경 요약**: 기존 설계는 영상 200편마다 사람이 3문장 요약·키워드
> 5~10개·개체명 목록을 직접 작성(2인 + 제3자 조정)해 ROUGE-L/Keyword F1/NER F1/
> 5점 인간평가로 "메타데이터 생성 자체의 품질"을 별도로 측정했다. 이 절차는
> (1) 200편×2인 규모의 큰 공수가 들고, (2) "정답 요약"이 본질적으로 주관적이라
> 다른 연구자가 재현하면 다른 레퍼런스·다른 수치가 나온다는 문제가 있었다. 게다가
> 기획서 스스로 "이 평가(검색 품질)가 핵심이다. 메타데이터 자체의 품질보다 실제로
> 사용할 때 더 잘 찾아지는가가 중요하다"라고 명시하고 있었다. v2는 인간 레퍼런스
> 작성 단계를 완전히 제거하고, 검색 품질 향상(Query-Relevance 레이블 기반) 평가
> 하나로 가설을 검증한다.

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
with `[DATA: 50]` retrieval query-relevance pairs. Rather than scoring generated metadata
against manually written reference summaries/keywords/entities — an approach that is costly
(roughly `[DATA: N]` videos × 2 annotators) and inherently subjective, since there is no single
"correct" summary — we evaluate purely by whether the generated metadata measurably improves
downstream retrieval quality (NDCG@5, MRR, Recall@10) when added to a vector search index.
Adding LLM-generated metadata improves NDCG@5 by `[DATA: Δ]` over API-metadata-only retrieval
(`[DATA: p-value]`, paired t-test), and we report per-model processing cost and latency under
Groq's free-tier rate limits (14,400 requests/day) for two open models (llama-3.1-8b, gemma2-9b)
against a paid quality ceiling (GPT-4o-mini).

**국문 초록 (draft):** YouTube 영상의 API 메타데이터(제목·설명·태그)는 업로더 입력값으로
키워드 스터핑이나 콘텐츠 내용과의 불일치가 빈번하다. 자동 자막(STT) 트랜스크립트가
있지만 한국어 STT는 전문 용어 오인식이 심해 그대로 쓰기 어렵다. 본 연구는 STT 노이즈가
심한 한국어 트랜스크립트에서 공개 LLM으로 요약·키워드·개체명·콘텐츠 유형 4종의 구조화
메타데이터를 자동 추출하는 파이프라인을 제안한다. 기술 `[DATA]`편, 의료 `[DATA]`편,
뉴스 `[DATA]`편으로 구성된 영상 `[DATA: N]`편과 검색 평가용 Query-Relevance 쌍
`[DATA: 50]`개로 평가한다. 사람이 직접 요약·키워드·개체명을 작성해 생성물과 비교하는
절차(비용이 크고 "정답"이 주관적이라 재현성이 떨어짐) 대신, 이 메타데이터를 벡터 검색
인덱스에 추가했을 때 검색 정확도(NDCG@5, MRR, Recall@10)가 실제로 향상되는지만으로
가설을 검증한다. LLM 메타데이터 추가 시 NDCG@5가 API 메타데이터 단독 대비
`[DATA: Δ]` 향상되었으며(`[DATA: p-value]`, paired t-test), 무료 Groq API 모델
(llama-3.1-8b, gemma2-9b)을 유료 품질 상한 기준(GPT-4o-mini)과 비교해 Groq 무료
티어(일 14,400회) 제약 하에서의 처리 비용·응답 시간도 함께 보고한다.

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

이 파이프라인을 평가하는 방법에는 두 갈래가 있다: (1) 생성된 요약·키워드·개체명이
"사람이 썼을 법한 것"과 얼마나 비슷한지 채점하는 방법(ROUGE-L, F1류), (2) 그
메타데이터를 실제로 검색에 붙였을 때 사용자가 원하는 영상을 더 잘 찾는지 측정하는
방법. 전자는 영상마다 사람이 요약·키워드·개체명을 직접 작성해야 하는 큰 공수가
들고, "정답 요약"이 본질적으로 주관적이라 다른 연구자가 같은 데이터로 다시 레퍼런스를
만들면 다른 점수가 나온다. 본 연구는 이 연구 질문에 직접 답하는 데 꼭 필요한 후자만
사용한다 — 메타데이터의 최종 목적이 검색 품질 향상이라면, 그 목적을 직접 측정하는
것이 인간이 썼을 요약과의 유사도를 재는 것보다 타당하고, 비용도 훨씬 적게 든다.

### 1.2 연구 질문

> LLM이 생성한 메타데이터를 추가했을 때, 트랜스크립트가 없는 API 메타데이터만
> 사용한 경우 대비 검색 정확도가 통계적으로 유의하게 향상되는가?

### 1.3 기여점 (Contributions)

1. STT 노이즈 유형 분류 및 전처리 파이프라인 (타임스탬프 제거, 반복 구문 병합,
   토큰 수 기반 청킹)
2. 요약·키워드·개체명·콘텐츠 유형 4종을 동시에 추출하는 구조화 출력 프롬프트 설계
3. 무료 LLM(Groq: llama-3.1-8b, gemma2-9b)의 한국어 실용 성능을 **검색 품질
   향상 기여도**로 측정 — 인간 레퍼런스 작성 없이 Query-Relevance 레이블만으로
   검증 가능한 가볍고 재현 가능한 평가 설계
4. LLM 메타데이터 추가 시 벡터 검색 품질 향상의 정량화

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
- 무엇보다, 이들 선행 연구는 대체로 **생성된 메타데이터 자체의 품질**(인간 레퍼런스와의
  유사도)을 평가 대상으로 삼는다. 본 연구는 이 방식이 요구하는 대규모 인간 레퍼런스
  작성 없이, 생성 품질을 "검색에 실제로 기여하는가"라는 하위 응용 성능으로 직접
  치환해 평가한다 — 평가 비용과 재현성 양쪽에서 이점이 있다.

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
| 검색 평가용 Query-Relevance 쌍 | `[DATA: 50]`개 (예: "HBM 제조 공정을 설명하는 영상", 2인 독립 관련성 판정 + 불일치 시 제3자 조정) |
| 데이터 소스 | `meta_youtube_video`, `youtube-transcript-api` 원시 트랜스크립트 |

인간이 직접 요약·키워드·개체명을 작성하는 레퍼런스 구축 단계는 두지 않는다.
Query-Relevance 판정(관련/부분관련/무관)은 요약 작성보다 훨씬 가볍고, 검색 품질이라는
최종 목적에 직접 연결된 신호이므로 이것만으로 가설을 검증한다 (§1.1 참고).

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

1. **데이터 구축** — 영상 `[DATA: N]`편의 트랜스크립트 수집·전처리, Query-Relevance
   쌍 `[DATA: 50]`개를 2인 독립 판정.
2. **메타데이터 생성** — 3개 LLM 각각으로 전체 영상에 대해 요약·키워드·개체명·콘텐츠
   유형을 생성, JSON schema validation 및 fallback 적용.
3. **검색 인덱싱 및 평가** — 조건 A/B/C 각각으로 영상 `[DATA: N]`편을 임베딩·인덱싱하고
   Query-Relevance 쌍 `[DATA: 50]`개로 NDCG@5/MRR/Recall@10 측정.
4. **처리 효율 측정** — LLM별 영상 1편당 평균 API 호출 횟수, 응답 시간 기록.

---

## 5. 평가 방법 (Evaluation)

### 5.1 검색 품질 향상 (메타데이터가 검색에 도움이 되는가)

메타데이터 자체가 인간이 쓸 법한 요약과 얼마나 닮았는지가 아니라, **실제로 사용할 때
더 잘 찾아지는가**로 가설을 검증한다.

```
실험 절차:
1. 조건 A/B/C 각각으로 영상 [DATA: N]편을 임베딩·인덱싱
2. [DATA: 50]개 검색 쿼리를 각 조건에서 실행
3. 결과 상위 10개와 정답셋(Query-Relevance 레이블) 비교
```

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| NDCG@5 | 상위 5개 결과의 순위 품질 | 사용자는 보통 상위 몇 개만 확인 |
| MRR | 첫 번째 관련 결과의 순위 역수 평균 | 정확한 답을 얼마나 빨리 찾는지 |
| Recall@10 | 정답 중 상위 10개 안에 있는 비율 | 놓치는 관련 결과가 없는지 |

### 5.2 주요 개념 설명

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

**paired t-test**
동일한 쿼리 집합에 조건 A와 조건 C를 각각 적용한 결과를 비교하는 검정. 쿼리 간
자연적 난이도 차이를 제거하고 조건 간 차이만 검정하므로 검정력이 높다.

### 5.3 해석 기준 (성공 조건)

- NDCG@5: 조건 C > 조건 A에서 Δ ≥ 0.05 (paired t-test p < 0.05)
- 처리 효율: 영상 1편당 Groq 호출 ≤ 3회, 응답 시간 ≤ 10초

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 검색 품질 향상 (조건별)

| 조건 | NDCG@5 | MRR | Recall@10 |
|------|--------|-----|-----------|
| A (API 메타데이터만) | `[DATA]` | `[DATA]` | `[DATA]` |
| B (A + 요약 + 키워드) | `[DATA]` | `[DATA]` | `[DATA]` |
| C (B + 개체명 + 콘텐츠 유형) | `[DATA]` | `[DATA]` | `[DATA]` |

Δ(NDCG@5, C − A) = `[DATA]` / paired t-test: `[DATA: t-statistic, p-value]`

해석 기준(Δ NDCG@5 ≥ 0.05, p < 0.05) 충족 여부: `[DATA]`

### 6.2 LLM 모델 간 비교 (조건 C 기준)

| 모델 | NDCG@5 | MRR | Recall@10 |
|------|--------|-----|-----------|
| llama-3.1-8b (무료) | `[DATA]` | `[DATA]` | `[DATA]` |
| gemma2-9b (무료) | `[DATA]` | `[DATA]` | `[DATA]` |
| GPT-4o-mini (유료, 상한) | `[DATA]` | `[DATA]` | `[DATA]` |

### 6.3 도메인별 검색 품질 향상 세부

| 도메인 | Δ NDCG@5 (C − A) | 비고 |
|--------|-------------------|------|
| 기술 | `[DATA]` | `[DATA]` |
| 의료 | `[DATA]` | `[DATA]` |
| 뉴스 | `[DATA]` | `[DATA]` |

### 6.4 조건 B vs. 조건 C 증분 분해

조건 B(요약+키워드)에서 이미 발생한 향상과, 조건 C에서 개체명·콘텐츠 유형을 추가로
더했을 때의 증분 향상을 분리한다.

| 비교 | Δ NDCG@5 |
|------|----------|
| B − A (요약+키워드의 순수 기여) | `[DATA]` |
| C − B (개체명+콘텐츠유형의 순수 기여) | `[DATA]` |

### 6.5 처리 효율

| 모델 | 영상당 평균 API 호출 횟수 | 평균 응답 시간 | 일일 처리 가능 영상 수 (14,400 req/day 기준) |
|------|--------------------------|---------------|----------------------------------------|
| llama-3.1-8b | `[DATA]` | `[DATA]` | `[DATA]` |
| gemma2-9b | `[DATA]` | `[DATA]` | `[DATA]` |
| GPT-4o-mini | `[DATA]` | `[DATA]` | `[DATA]` |

해석 기준(호출 ≤ 3회, 응답 시간 ≤ 10초) 충족 여부: `[DATA]`

### 6.6 정성적 사례 분석

`[DATA: 조건 A에서는 못 찾았지만 조건 C에서 찾은 사례 1~2건, 트랜스크립트/쿼리 예시 포함]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 조건 C의 검색 품질 향상이 개체명·콘텐츠 유형 추가분(C−B)에서 기인하는지, 아니면
  이미 조건 B(요약+키워드)에서 대부분의 향상(B−A)이 발생하는지 (§6.4)
- llama-3.1-8b와 gemma2-9b, GPT-4o-mini 간 검색 기여도 차이가 모델 규모·품질과
  비례하는지, 혹은 무료 모델이 유료 모델과 실용적으로 큰 차이가 없는지
- 도메인별(기술/의료/뉴스) 향상 폭 편차의 원인 — 특히 의료 도메인처럼 전문 용어
  STT 오인식이 심한 영역에서 LLM 메타데이터가 얼마나 이를 보정하는지
- Groq 무료 티어 제약 하에서 실제 운영 규모로 확장했을 때의 병목

## 8. 한계 (Limitations)

- Query-Relevance 쌍 `[DATA: 50]`개, 평가자 2인 규모로는 통계적 검정력에 한계가 있다
- 인간 레퍼런스 기반 품질 평가(ROUGE-L, F1 등)를 생략했으므로, 생성된 메타데이터가
  "얼마나 사실에 부합하는가(factuality)"는 본 연구의 검색 품질 지표만으로는 직접
  드러나지 않는다 — 검색에 도움이 되었다고 해서 메타데이터 내용이 항상 정확하다는
  보장은 아니다
- Groq API rate limit(14,400 req/day) 하에서의 측정으로, 상용 유료 티어나 온프레미스
  배포 환경의 처리량과는 다를 수 있다
- STT 노이즈 유형 분류는 사전에 관찰된 패턴(전문 용어 오인식, 반복 구문 등)에
  기반하며, 데이터셋에 없는 새로운 노이즈 유형에는 일반화되지 않을 수 있다
- Query-Relevance 쌍 `[DATA: 50]`개는 특정 도메인(기술 중심)에 편중되었을 가능성이
  있다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- 영상 썸네일 비전 결합 멀티모달 메타데이터
- 트랜스크립트 변경 감지 시 자동 재생성 파이프라인
- 검색 기여도가 낮게 나온 필드(예: 개체명)에 대해서만 선별적으로 소규모 인간 검증을
  추가하는 저비용 품질 점검 절차

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
- [ ] 6.1 조건 A/B/C 검색 품질(NDCG@5, MRR, Recall@10) 수치 삽입
- [ ] 6.1 paired t-test 통계량/p-value 삽입 및 해석 기준 충족 여부 판정
- [ ] 6.2 LLM 모델 간 비교 수치 삽입
- [ ] 6.3 도메인별 세부 수치 삽입
- [ ] 6.4 B−A / C−B 증분 분해 수치 삽입
- [ ] 6.5 처리 효율(호출 횟수, 응답 시간, 일일 처리량) 실측치 삽입 및 해석 기준 판정
- [ ] 6.6 정성적 사례 작성
- [ ] 7장 논의 작성 (증분 분해, 모델 간 차이, 도메인별 편차 포함)
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 제출 전 novelty 재검색 (2.1절 참고)
