# 논문 초안: 계층적 벡터 검색을 이용한 이종 미디어 데이터셋 탐색

> 기반 기획서: [research_proposals.md](./research_proposals.md) P04
> 작성일: 2026-07-08
> 상태: **초안 (실험 데이터 미삽입)** — `[DATA: ...]` 표시된 부분은 실제 실험 후 수치로 교체
> 목표 분량: 5페이지 내외 단편 논문 (워크숍/국내 학회 단문 트랙)

---

## 제목 (Title)

**영문:** *Hierarchical Vector Search for Heterogeneous Media Dataset Discovery: Coarse Dataset Filtering with Fine-Grained Item Retrieval*

**국문:** 계층적 벡터 검색을 이용한 이종 미디어 데이터셋 탐색: 데이터셋 단위 Coarse 필터링과 아이템 단위 Fine 검색의 결합

---

## Abstract

Vector search research has largely focused on retrieving similar items within a single
collection. In environments where heterogeneous media — YouTube videos and news articles —
coexist across many datasets, however, users first need to know *which dataset* contains
relevant content before drilling down to individual items. We propose a two-stage hierarchical
vector search architecture that combines coarse dataset-level retrieval (over
`dcat_dataset_vec`) with fine-grained item-level retrieval (over `meta_*_vec`) restricted to the
top-K selected datasets. We evaluate the accuracy-speed trade-off as a function of K on a corpus
of `[DATA: N items]` items across `[DATA: M datasets]` datasets, measure scalability across
corpus sizes of 1K/5K/10K/50K items, and assess cross-modal discovery (querying with a video to
retrieve related news articles, and vice versa) on `[DATA: 30]` manually labeled pairs. We show
that hierarchical search at K=`[DATA]` reduces response time by `[DATA]`% relative to flat dense
search while keeping the MRR@10 gap within `[DATA]` (`[DATA: statistical test result]`), and
report the point at which the accuracy loss transitions sharply as K decreases.

**국문 초록 (draft):** 벡터 검색 연구는 대부분 단일 컬렉션 내 유사 아이템 탐색에 집중해
왔다. 그러나 YouTube 영상과 뉴스 기사 등 이종 미디어가 다수의 데이터셋에 흩어져 있는
환경에서는, 아이템을 바로 검색하기 전에 "어떤 데이터셋에 관련 콘텐츠가 있는가"를 먼저
판단하는 것이 자연스럽다. 본 연구는 데이터셋 description 임베딩(`dcat_dataset_vec`)으로
관련 데이터셋 상위 K개를 추리는 coarse 단계와, 선택된 K개 데이터셋의 아이템 임베딩
(`meta_*_vec`)에서만 세부 검색을 수행하는 fine 단계를 결합한 2단계 계층적 벡터 검색
아키텍처를 제안한다. 데이터셋 `[DATA: M]`개·아이템 `[DATA: N]`개 규모의 코퍼스에서 K값에
따른 정확도-속도 트레이드오프를 측정하고, 아이템 수 1K/5K/10K/50K 규모별 확장성을
비교하며, 동일 주제의 영상-기사 쌍 `[DATA: 30]`개로 cross-modal 탐색(영상 쿼리로 관련 기사
탐색, 그 역방향)의 재현율을 평가한다. K=`[DATA]`에서 계층 검색이 Flat 검색 대비 응답
시간을 `[DATA]`% 단축하면서도 MRR@10 손실이 `[DATA]` 수준에 그침을 보이고, K값이 작아질
때 정확도 손실이 급격히 커지는 임계 구간을 함께 보고한다.

**Keywords:** hierarchical vector search, ANN, HNSW, dataset discovery, heterogeneous media,
cross-modal retrieval, pgvector, coarse-to-fine retrieval

---

## 1. 서론 (Introduction)

### 1.1 연구 배경 및 문제 정의

벡터 검색 연구는 대부분 **단일 컬렉션 내 유사 아이템 탐색**에 초점을 맞춰 왔다.
HNSW(Malkov & Yashunin, 2018)는 계층적 그래프 구조로 대규모 단일 컬렉션 내 근사 최근접
이웃(ANN) 검색을 높은 정밀도와 속도로 수행하도록 했고, FAISS(Johnson, Douze & Jégou,
2019)는 GPU 기반 IVF·PQ 양자화 등으로 수십억 벡터 규모의 인덱싱·검색을 최적화했다. 그러나
이 연구들은 어디까지나 하나의 플랫(flat) 인덱스 내부의 최적화이며, "이 질의와 관련된
콘텐츠가 어느 데이터셋에 있는가"를 먼저 판단한 뒤 그 안에서 세부 아이템을 찾는 **계층적
데이터셋 탐색** 문제는 다루지 않는다.

YouTube 영상과 뉴스 기사가 혼재하는 환경에서는 이 계층 구조가 자연스럽게 존재한다.
데이터셋(예: `youtube_samsung_official`, `naver_news_ai`)마다 서로 다른 주제·소스·미디어
타입을 담고 있고, 사용자는 궁극적으로 개별 아이템을 원하지만 탐색의 첫 단계는 "관련 있는
데이터셋을 좁히는 것"이다. 데이터셋 레벨의 coarse 벡터 검색과 아이템 레벨의 fine 벡터
검색을 결합해 효율성과 정확도를 동시에 달성하는 아키텍처 연구는 아직 확인되지 않는다.

### 1.2 연구 질문

> 2단계 계층적 검색이 전체 Flat 검색 대비 응답 시간을 줄이면서도 검색 정확도 손실이
> 통계적으로 무시 가능한 수준인가?

정확도 손실 없이 속도가 빨라지면 계층 구조가 의미 있는 설계로 입증된다. 반대로 정확도가
크게 떨어진다면 상위 K값을 늘려야 하며, 이는 정확도-속도 트레이드오프 분석을 통해서만
답할 수 있다.

### 1.3 기여점 (Contributions)

1. 데이터셋 레벨(coarse) + 아이템 레벨(fine) 2단계 계층적 벡터 검색 아키텍처 제안 —
   `dcat_dataset_vec`으로 관련 데이터셋 top-K를 추리고 `meta_*_vec`에서 세부 검색
2. 검색 공간 축소 효과의 정량화 — 1단계 데이터셋 필터가 아이템 검색 대상을 얼마나
   줄이는지 `(N-n)/N` 형태로 측정
3. K값에 따른 정확도-속도 트레이드오프 곡선 분석 및 K값 선택 기준 제시
4. 이종 미디어(YouTube 영상 ↔ 뉴스 기사) 간 cross-modal 탐색 가능성의 정량 평가
   (양방향 recall)
5. pgvector HNSW 인덱스만으로 구현 가능한 실전 적용형 아키텍처 설계 제시 (추가
   라이브러리 불필요)

---

## 2. 관련 연구 (Related Work)

| 문헌 | 내용 | 본 연구와의 차이 |
|------|------|----------------|
| Malkov & Yashunin (2018). "Efficient and Robust ANN Search Using HNSW." *IEEE TPAMI*, 42(4), 824–836. | HNSW 알고리즘 제안. 계층적 그래프 구조로 대규모 단일 컬렉션 내 ANN 검색을 높은 정밀도·속도로 수행. | 이종 미디어 다중 컬렉션 계층 탐색 미지원; 데이터셋 레벨 필터링 개념 없음 |
| Johnson, Douze & Jégou (2019). "Billion-Scale Similarity Search with GPUs (FAISS)." *IEEE Trans. Big Data*, 7(3), 535–547. | FAISS 라이브러리로 GPU 기반 수십억 벡터 인덱싱·검색 최적화. IVF, PQ 양자화 등 다양한 인덱스 전략 제공. | 단일 플랫 인덱스 최적화; 데이터셋→아이템 drill-down 계층 구조 없음 |
| Reimers & Gurevych (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks." *EMNLP*, 3982–3992. | 다국어 임베딩 모델(paraphrase-multilingual-mpnet-base-v2). 텍스트 의미 유사도 기반 검색의 기반 모델 역할. | YouTube 영상 텍스트 메타데이터와 뉴스 기사의 cross-modal 혼합 검색 평가 없음 |
| Yao et al. (2021). "FILIP: Fine-grained Interactive Language-Image Pre-Training." arXiv:2111.07783. | 이종 미디어(텍스트-이미지) 간 fine-grained 상호작용으로 cross-modal 검색 성능 향상. | 영상 텍스트 메타 + 뉴스 기사 텍스트 혼합 검색을 계층 구조로 제공하는 방법 미제시 |

### 2.1 선행 연구 대비 위치 (Positioning)

기존 벡터 검색 연구들은 단일 대규모 컬렉션 내 ANN 최적화(HNSW, FAISS)에 집중하며,
데이터셋 레벨 coarse 검색과 아이템 레벨 fine 검색을 결합해 이종 미디어 데이터셋을
계층적으로 탐색하는 아키텍처를 제안한 연구는 확인되지 않는다. Sentence-BERT류 텍스트
임베딩 모델과 FILIP류 cross-modal 정렬 기법은 각각 검색 품질의 구성 요소를 제공하지만,
이들을 "데이터셋을 먼저 좁히고 아이템을 나중에 찾는" 2단계 구조 안에 배치하고 그 구조가
가져오는 효율성-정확도 트레이드오프를 정량화한 연구는 없다. 본 연구의 novelty는 개별
기법의 개선이 아니라, 이미 검증된 ANN·임베딩 기법들을 **데이터셋→아이템 계층**이라는
새로운 축으로 조합하고 그 효과를 실증한다는 데 있다.

> **⚠️ 검증 필요:** 위 novelty 주장은 기획 단계 문헌 조사 기준이며, 학회 제출 전 최신
> arXiv/ACL Anthology/DBLP 재검색으로 최근 유사 연구(예: "hierarchical dataset retrieval",
> "coarse-to-fine vector search multi-collection")가 없는지 재확인할 것.

---

## 3. 제안 방법 (Methodology)

### 3.1 2단계 검색 아키텍처

```
질의 입력: "HBM 반도체 공정 기술"
        ↓ 임베딩
[L1] dcat_dataset_vec에서 유사 데이터셋 top-K 검색
        → K=3이면: youtube_samsung_official, naver_news_ai, user_hbm_collection 선택
        ↓
[L2] 선택된 K개 데이터셋의 meta_*_vec에서만 유사 아이템 검색
        → meta_youtube_video_vec ∪ meta_naver_news_vec 대상으로 검색
        ↓
최종 결과 반환 (데이터셋 정보 + 아이템 정보 포함)
```

L1은 데이터셋 description 임베딩(`dcat_dataset_vec`) 상에서 pgvector HNSW 인덱스로
top-K 후보 데이터셋을 검색한다. L2는 L1에서 선택된 K개 데이터셋에 속한 아이템들의
`meta_*_vec`(YouTube 영상, 뉴스 기사 등 소스 타입별 임베딩 컬럼의 합집합)에서만 세부
검색을 수행한다. 이 구조는 아이템 검색을 매번 전체 컬렉션이 아니라 L1이 좁혀 놓은
부분집합 위에서 수행하므로, K가 작을수록 L2의 탐색 공간이 줄어들어 응답 시간이 짧아진다.

### 3.2 검색 공간 축소 효과

```
전체 아이템 수: N
K개 데이터셋 선택 후 검색 대상: n  (n << N)
공간 축소율: (N - n) / N × 100%
```

K가 작을수록 속도는 빠르지만 관련 아이템을 L1 단계에서 놓칠 위험이 커진다. 본 연구는
K값에 따른 정확도-속도 트레이드오프 곡선을 실측하여 이 위험과 이득의 균형점을 규명한다.

### 3.3 Cross-modal 탐색 시나리오

L1의 데이터셋 후보가 서로 다른 미디어 타입(영상/기사)에 걸쳐 선택될 수 있다는 점을
이용하면, 하나의 미디어로 질의해 다른 미디어의 콘텐츠를 탐색하는 cross-modal 시나리오가
자연스럽게 성립한다.

```
시나리오 1: 영상 쿼리 → 관련 뉴스 기사
  "삼성 HBM 영상을 보고 관련 최신 뉴스 기사를 찾아줘"

시나리오 2: 기사 쿼리 → 관련 영상
  "AI 데이터센터 전력 소비 기사와 관련된 YouTube 영상을 찾아줘"
```

두 시나리오 모두 L1에서 미디어 타입이 다른 데이터셋이 후보로 선택되어야 성립하므로,
계층 구조 자체가 cross-modal 탐색의 실현 가능성을 좌우하는 요인이 된다.

---

## 4. 실험 설계 (Experimental Setup)

### 4.1 데이터셋

| 항목 | 값 |
|------|-----|
| 평가용 데이터셋(컬렉션) 수 | `[DATA: M]` |
| 평가용 전체 아이템 수 | `[DATA: N]` |
| 실험1 K값 범위 | 1, 2, 3, 5, 10, 전체(Flat) — 고정 설계값 |
| 실험2 데이터 규모 | 1K, 5K, 10K, 50K (시뮬레이션 또는 실제 수집) — 고정 설계값 |
| Query-Relevance 쌍 | `[DATA: 50]` (수동 구축) |
| Cross-modal 레이블링 쌍 | `[DATA: 30]` (동일 주제 영상-기사 쌍, 수동 레이블링) |
| 데이터 소스 | `dcat_dataset_vec`, `meta_youtube_video_vec`, `meta_naver_news_vec` (pgvector HNSW 인덱스) |

### 4.2 실험 절차

1. **평가용 코퍼스 구축** — 운영 중인 `dcat_dataset_vec`, `meta_*_vec`를 활용해
   `[DATA: M]`개 데이터셋·`[DATA: N]`개 아이템 규모의 평가 코퍼스를 구성한다.
2. **Query-Relevance 쌍 구축** — 테스트 쿼리 `[DATA: 50]`개를 작성하고 각 쿼리의 정답
   아이템을 수동으로 레이블링한다.
3. **실험 1: 정확도-속도 트레이드오프** — K = 1, 2, 3, 5, 10, 전체(Flat) 각각에 대해
   응답 시간(ms), MRR@10, Recall@10을 측정하고 트레이드오프 곡선을 작성한다.
4. **실험 2: 데이터 규모별 확장성** — 아이템 수 1K/5K/10K/50K 규모에서 Flat 검색과
   계층 검색(K=3)의 응답 시간을 비교해, 규모가 클수록 계층 검색의 이점이 커지는지
   확인한다.
5. **실험 3: Cross-modal 탐색 평가** — 동일 주제 영상-기사 쌍 `[DATA: 30]`개를 수동
   레이블링하고, 두 방향(영상 쿼리 → 기사, 기사 쿼리 → 영상) 모두에서 recall을
   측정한다.

---

## 5. 평가 방법 (Evaluation)

### 5.1 비교 대상 (Baselines)

| 방법 | 설명 |
|------|------|
| Flat Dense | 전체 아이템 대상 단일 벡터 검색 |
| Source-type Filter | 소스 타입으로 먼저 필터링 후 검색 |
| 계층 검색 (K=3) | **제안 방법** |
| 계층 검색 (K=5) | 제안 방법 (K 변형) |

### 5.2 지표와 연결 이유

| 지표 | 측정 대상 | 연결 이유 |
|------|----------|----------|
| MRR@10 | 첫 번째 관련 결과의 순위 역수 평균 | 사용자가 처음 보는 결과의 품질 측정 |
| Recall@10 | 정답 중 상위 10개 안에 있는 비율 | 계층 검색이 관련 결과를 놓치는지 측정 |
| 응답 시간 (ms) | 쿼리당 처리 시간 | 속도 이점의 실질적 크기 측정 |
| Cross-modal Recall@5 | 영상-기사 쌍 정답 회수율 | 이종 미디어 탐색 가능성 입증 |
| NDCG@10 (보조) | 상위 10개 순위 가중 품질 | MRR/Recall을 보완하는 표준 IR 지표로 추가 참고용 |

### 5.3 주요 개념 설명

**MRR@10 (Mean Reciprocal Rank at 10)**
상위 10개 결과 중 첫 번째 정답의 순위 역수 평균. 1위 = 1.0 / 2위 = 0.5 / 3위 = 0.33 /
10위 = 0.1 / 없으면 0. 사용자가 처음 보는 결과에서 얼마나 빨리 정답을 만나는지를
측정한다. 검색 정확도 지표 중 가장 직관적이고 널리 사용된다.

**Recall@K (K개 결과 내 재현율)**
전체 정답 중 상위 K개 결과 안에 포함된 비율. Recall@10 = 0.8이면 정답의 80%를 상위
10개 안에 포함한다는 뜻이다. 계층 검색에서 "2단계로 나눠 탐색해도 관련 결과를 놓치지
않는가"를 확인하는 핵심 지표다. MRR과의 차이: MRR은 "첫 정답의 위치"에 집중하고,
Recall@K는 "전체 정답 중 얼마나 커버하는가"에 집중한다.

**ANN (Approximate Nearest Neighbor, 근사 최근접 이웃) / HNSW**
수십만 개 벡터 중 가장 유사한 것을 정확하게 찾으려면 모든 벡터와 비교(O(N))해야 해서
너무 느리다. ANN은 약간의 정확도를 포기하고 훨씬 빠른 근사 탐색을 한다. pgvector가
지원하는 HNSW(Hierarchical Navigable Small World)는 계층적 그래프 구조를 미리 구축해
검색 경로를 단축한다. 정확도 손실은 통상 1~2% 수준이다.

**Flat Dense 검색 (vs. 계층 검색)**
인덱스 없이 모든 벡터와 직접 비교하는 가장 단순한 방법. 결과는 정확하지만 아이템
수가 많으면 느리다. 계층 검색은 "데이터셋 레벨에서 먼저 상위 K개 데이터셋을 선택 →
그 안에서만 세부 검색"으로 탐색 공간을 줄인다. 이 연구의 핵심 질문: 탐색 공간을
줄이는 대가로 얼마만큼의 정확도를 잃는가? (MRR 차이 < 0.05이면 무시 가능한 수준으로
판단)

### 5.4 통계 검정

- **Wilcoxon signed-rank test**(비모수, paired) — 쿼리별 MRR@10 차이에 순위를 매겨
  계층 검색(K=3)과 Flat Dense 간 전체 성능 차이의 유의성을 검정한다 (p < 0.05 기준).
  통계적으로 유의한 차이가 있더라도 그 차이의 크기(효과 크기)가 해석 기준(< 0.05)
  이내라면 실용적으로는 무시 가능한 손실로 판단한다.
- **비율 비교 검정** — cross-modal 두 방향(영상→기사 vs. 기사→영상) recall의 비대칭
  여부를 확인하기 위해 두 비율 간 차이 검정(Fisher's exact test 등)을 보조적으로
  수행한다.

### 5.5 해석 기준 (성공 조건)

- MRR@10: 계층(K=3) vs. Flat 차이 < 0.05 → 정확도 손실 무시 가능
- 응답 시간: 10만 건 기준 계층 검색이 Flat 대비 50% 이상 단축
- Cross-modal Recall@5: 60% 이상 → 이종 미디어 탐색 실용 수준

---

## 6. 결과 (Results) — ⟪실험 후 작성⟫

### 6.1 정확도-속도 트레이드오프 (실험 1)

| K | MRR@10 | Recall@10 | NDCG@10 | 응답 시간 (ms) |
|---|--------|-----------|---------|---------------|
| 1 | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| 2 | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| 3 | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| 5 | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| 10 | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |
| 전체 (Flat) | `[DATA]` | `[DATA]` | `[DATA]` | `[DATA]` |

`[DATA: K(x축) vs. MRR@10/응답시간(y축) 트레이드오프 곡선 삽입]`

Wilcoxon signed-rank test (계층 K=3 vs. Flat, 쿼리별 MRR@10): `[DATA: statistic, p-value]`

### 6.2 검색 공간 축소율

| K | 평균 선택 데이터셋 수 | 평균 검색 대상 아이템 수 (n) | 축소율 (N−n)/N |
|---|----------------------|------------------------------|-----------------|
| 3 | `[DATA]` | `[DATA]` | `[DATA]` |
| 5 | `[DATA]` | `[DATA]` | `[DATA]` |

### 6.3 데이터 규모별 확장성 (실험 2)

| 아이템 수 | Flat 응답 시간 (ms) | 계층 검색(K=3) 응답 시간 (ms) | 단축률 |
|-----------|---------------------|-------------------------------|--------|
| 1,000 | `[DATA]` | `[DATA]` | `[DATA]` |
| 5,000 | `[DATA]` | `[DATA]` | `[DATA]` |
| 10,000 | `[DATA]` | `[DATA]` | `[DATA]` |
| 50,000 | `[DATA]` | `[DATA]` | `[DATA]` |
| 100,000 (외삽) | `[DATA]` | `[DATA]` | `[DATA]` |

`[DATA: 아이템 수(x축) vs. 응답시간(y축) 그래프, Flat/계층 두 곡선 삽입]`

### 6.4 Cross-modal 탐색 평가 (실험 3)

| 방향 | Recall@5 | 표본 수 |
|------|----------|---------|
| 영상 쿼리 → 기사 | `[DATA]` | `[DATA: 30]` |
| 기사 쿼리 → 영상 | `[DATA]` | `[DATA: 30]` |
| 전체 평균 | `[DATA]` | `[DATA: 60]` |

`[DATA: 두 방향 recall 차이에 대한 비율 비교 검정 결과]`

### 6.5 정성적 사례 분석

`[DATA: 계층 검색이 정답을 놓친 사례(K값별) 1~2건, cross-modal 성공/실패 사례 각 1건,
데이터셋 후보 선택 과정 포함]`

---

## 7. 논의 (Discussion) — ⟪실험 후 작성⟫

- 정확도-속도 트레이드오프 곡선에서 K값에 따른 정확도 손실이 선형적인지, 특정 K
  이하에서 급격히 나빠지는 임계 구간이 있는지
- Wilcoxon 검정이 통계적으로 유의하더라도 효과 크기가 해석 기준(0.05) 이내라면 실용적
  의미를 어떻게 해석할지
- 데이터 규모가 커질수록 계층 검색의 이점이 실제로 확대되는지, 확대된다면 그 원인
  (검색 공간 축소율과 응답시간 단축률의 관계)
- Cross-modal 두 방향(영상→기사, 기사→영상) recall이 비대칭적이라면 그 원인 —
  임베딩 모델의 도메인 편향, 데이터셋 후보 선택 단계에서의 미디어 타입 쏠림 등
- Source-type Filter 대비 제안 방법의 상대적 이점 또는 한계

## 8. 한계 (Limitations)

- Query-Relevance 쌍 `[DATA: 50]`개, Cross-modal 레이블링 쌍 `[DATA: 30]`개로 표본
  규모가 작아 통계적 검정력에 한계가 있다
- 실험 2의 일부 규모(예: 50K, 100K 외삽)는 시뮬레이션 데이터에 의존할 수 있어 실제
  운영 데이터의 분포(데이터셋 간 아이템 수 불균형, 주제 쏠림)와 차이가 있을 수 있다
- HNSW는 근사 검색이므로 Flat Dense 대비 자체적인 정확도 손실(통상 1~2%)이 이미
  존재하며, 계층 구조로 인한 추가 손실과 완전히 분리해 측정하기 어렵다
- K값의 최적 지점은 데이터셋 수·아이템 분포에 의존적이므로, 본 실험에서 얻은 K값
  권장치가 다른 도메인·규모의 컬렉션에도 그대로 일반화된다고 보장할 수 없다
- Cross-modal 탐색 평가는 "동일 주제"를 사람이 판단해 레이블링한 것으로, 주제
  유사성 판단 기준이 주관적일 수 있다

## 9. 결론 (Conclusion) — ⟪실험 후 작성⟫

`[DATA: 핵심 결과 요약 3문장 + 향후 확장 방향]`

향후 확장성:
- 3레벨 계층 (소스 타입 → 데이터셋 → 아이템)
- 사용자 피드백 기반 데이터셋 레벨 임베딩 fine-tuning

---

## 참고문헌 (References)

1. Malkov, Y. A., & Yashunin, D. A. (2018). Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 42(4), 824–836.
2. Johnson, J., Douze, M., & Jégou, H. (2019). Billion-Scale Similarity Search with GPUs. *IEEE Transactions on Big Data*, 7(3), 535–547.
3. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP*, 3982–3992.
4. Yao, L., Huang, R., Hou, L., Lu, G., Niu, M., Xu, H., Liang, X., Li, Z., Jiang, X., & Xu, C. (2021). FILIP: Fine-grained Interactive Language-Image Pre-Training. arXiv:2111.07783.

---

## 데이터 삽입 체크리스트 (작업용)

실험 완료 후 이 파일에서 아래를 순서대로 채운다:

- [ ] 4.1 데이터셋 규모 (M, N, Query-Relevance 쌍 수, Cross-modal 쌍 수) 확정
- [ ] 6.1 K값별 MRR@10/Recall@10/NDCG@10/응답시간 표 삽입
- [ ] 6.1 트레이드오프 곡선 삽입
- [ ] 6.1 Wilcoxon signed-rank test 통계량/p-value 삽입
- [ ] 6.2 검색 공간 축소율 실측치 삽입
- [ ] 6.3 데이터 규모별 응답시간 비교표 및 100K 외삽 삽입
- [ ] 6.3 아이템수-응답시간 그래프 삽입
- [ ] 6.4 Cross-modal 방향별 recall 및 비율 비교 검정 결과 삽입
- [ ] 6.5 정성적 사례 작성 (K값별 실패 사례 + cross-modal 성공/실패 사례)
- [ ] 7장 논의 작성 (K값 임계 구간 여부, 통계적 유의성 vs. 효과 크기, cross-modal
      비대칭 원인 포함)
- [ ] 8장 한계 재검토
- [ ] 9장 결론 작성
- [ ] Abstract/초록의 `[DATA: ...]` 전부 실수치로 교체
- [ ] 제출 전 novelty 재검색 (2.1절 경고 참고)
