# 메타데이터 플랫폼 관련 논문 주제 리스트

> 작성일: 2026-07-07
> 대상 플랫폼: 이종 데이터 소스(YouTube, Naver 뉴스·쇼핑·페르소나) 통합 메타데이터 수집·관리 시스템

---

## 플랫폼 구성 요약 (논문 배경 맥락)

| 구성 요소 | 내용 |
|----------|------|
| 데이터 소스 | YouTube API, Naver 뉴스 API, Naver 쇼핑인사이트 API |
| 메타데이터 표준 | DCAT 2.0 (dcat_dataset, dcat_provenance) |
| 시계열 추적 | active_meta 패턴 (조회수·댓글·검색량 지수 변화 이력) |
| 벡터 검색 | pgvector 768차원 임베딩 (데이터셋·영상·기사 레벨) |
| AI 메타데이터 | LLM 기반 요약·키워드·개체명 추출 (Groq API, 예정) |
| 인프라 | PostgreSQL 17 + Kubernetes + SeaweedFS (S3 호환) |

---

## 논문 주제 후보

---

### 1. 상대적 검색량 지수의 장기 연속 시계열 복원: pseudo_volume 보정 방법론

**분류:** 데이터 전처리 / 측정 방법론

**연구 목적:**
네이버 쇼핑인사이트 API는 호출마다 최댓값을 100으로 정규화한 상대값을 반환한다.
배치가 달라지거나 수집 시점이 달라지면 기준(M)이 바뀌어 직접 비교가 불가능하다.
이 문제를 anchor 카테고리와 두 단계 scale 보정(intra_scale × inter_scale)으로 해결하는 방법을 형식화한다.

**핵심 기여:**
- 상대 지수의 비교 불가 문제를 수학적으로 정의
- intra_scale (동일 수집 내 배치 간 보정) / inter_scale (수집 구간 간 보정) 2단계 방법 제안
- 중앙값 기반 robust 추정으로 이상치 영향 최소화
- pseudo_volume의 신뢰 구간 추정 방법

**활용 데이터:** active_meta_naver_shopping (raw_ratio, anchor_raw_ratio, scale_factor, pseudo_volume)

---

### 2. 이종 웹 데이터 소스 통합을 위한 DCAT 2.0 기반 메타데이터 플랫폼 설계

**분류:** 시스템/아키텍처

**연구 목적:**
YouTube 영상, 뉴스 기사, 쇼핑 트렌드처럼 구조·갱신 주기·API 방식이 전혀 다른 소스를
단일 메타데이터 체계로 통합 관리하는 방법을 제안한다.

**핵심 기여:**
- DCAT 2.0을 한국어 웹 데이터 도메인에 적용하는 구체적 확장 방법
- `source_type` 경계 설계 원칙 (1 dataset = 1 source_type 불변 규칙)
- `dataset_origin` (admin/user) 이분법으로 관리자 자동 수집과 사용자 정의 컬렉션을 단일 스키마로 통합
- active_meta 패턴: 정적 메타데이터와 시계열 통계를 분리해 이력을 보존하는 설계

**활용 데이터:** dcat_dataset, dcat_provenance, data_registry, 전체 meta_*/active_meta_* 테이블

---

### 3. LLM 기반 비정형 미디어 메타데이터 자동 생성: 유튜브 트랜스크립트 활용

**분류:** NLP / AI 메타데이터 생성

**연구 목적:**
YouTube 자동 생성 자막(STT 기반)에서 Groq API(LLM)를 통해 요약·키워드·개체명을 추출하고,
API 메타데이터만으로는 얻을 수 없는 콘텐츠 이해 정보를 자동으로 보강하는 파이프라인을 구축·평가한다.

**핵심 기여:**
- STT 노이즈가 포함된 한국어 트랜스크립트에서의 LLM 메타데이터 추출 품질 평가
- 무료 LLM(llama-3.1-8b, gemma2-9b)의 메타데이터 생성 실용성 검증 (14,400 req/day 제약 내)
- API 메타데이터(제목·설명·태그)만 사용 시 vs. 트랜스크립트 포함 시 검색 정확도 비교

**활용 데이터:** meta_youtube_video_ai (예정), meta_youtube_video_vec

---

### 4. 쇼핑 Persona Index 독립 가정의 카테고리별 위반 정도 분석

**분류:** 데이터 분석 / 방법론 검증

**연구 목적:**
`persona_index = gender_pv × age_pv` 는 성별과 연령이 독립이라는 가정 하의 추정치다.
이 가정이 실제 쇼핑 검색 행동에서 얼마나 성립하는지, 어떤 카테고리에서 독립 가정이 깨지는지 분석한다.

**핵심 기여:**
- 독립 가정 위반 정도를 카테고리별로 정량화하는 지표 제안
- Persona index와 실제 인구통계 분포의 괴리를 추정하는 상한 오차 분석
- 독립 가정이 비교적 성립하는 카테고리 유형과 위반이 심한 카테고리 유형 분류

**활용 데이터:** active_meta_naver_persona (gender_ratio, age_ratio, gender_pv, age_pv, persona_index)

---

### 5. 뉴스 기사 댓글 시계열 분석을 통한 사회적 임팩트 측정

**분류:** 소셜 미디어 분석

**연구 목적:**
뉴스 기사 댓글 수의 시간별 누적 패턴을 분석해 기사의 사회적 임팩트를 유형화한다.
"언제까지 반응이 오는가(Duration)", "얼마나 빠르게 모이는가(Velocity)", "총 규모는
얼마인가(Volume)" 세 차원으로 분해해 기사 유형별 임팩트 궤적을 군집화한다.

**핵심 기여:**
- 댓글 누적 곡선의 수학적 모델 제안 및 파라미터 해석 (지수 감쇠 + 장기 꼬리)
- Velocity·Duration·Volume 3차원 임팩트 지표 정의
- 기사 임팩트 패턴 유형 분류 (단발 화제형 vs. 지속 확산형 등)
- 초기 N시간 댓글 수로 최종 임팩트 조기 예측 가능성 검증

**활용 데이터:** active_meta_naver_news (comment_count 시계열), meta_naver_news

---

### 6. 쇼핑 검색 트렌드와 YouTube 콘텐츠 인기도의 상관관계 분석

**분류:** 크로스소스 데이터 분석 / 트렌드 예측

**연구 목적:**
동일 주제(예: 특정 패션 카테고리)에 대한 YouTube 영상 조회수 변화와
네이버 쇼핑 검색량(pseudo_volume) 간의 선행·후행 관계를 분석한다.
"영상이 트렌드를 이끄는가, 트렌드가 영상 수요를 이끄는가"를 검증한다.

**핵심 기여:**
- 이종 소스 시계열(active_meta_youtube, active_meta_naver_shopping)의 정렬 및 그랜저 인과 검정
- 카테고리별 lead/lag 관계 패턴 분류
- 트렌드 예측에서 YouTube 조회수의 선행 지표로서의 유용성 검증

**활용 데이터:** active_meta_youtube (delta_views), active_meta_naver_shopping (pseudo_volume)

---

### 7. RAG 기반 한국어 도메인 Q&A: 뉴스 기사 지식베이스 활용

**분류:** NLP / 정보 검색 (IR)

**연구 목적:**
한국어 AI·반도체 뉴스 기사를 지식베이스로 사용한 RAG 시스템을 구축하고,
청킹 전략(고정 길이·문단·문장·슬라이딩 윈도우)과 검색 방법(Dense·Sparse·Hybrid)
조합이 성능에 미치는 영향을 한국어 교착어·전문 용어 특성과 연결해 분석한다.

**핵심 기여:**
- 한국어 뉴스 기사 특화 청킹 전략 4종 체계적 비교
- Dense(DPR)·Sparse(BM25)·Hybrid 검색 방법 한국어 도메인 성능 비교
- RAGAS 프레임워크 기반 자동 평가 파이프라인 구축 (Faithfulness, Answer Relevancy 등)
- 12조합(4 청킹 × 3 검색) 전수 실험으로 최적 조합 도출

**활용 데이터:** meta_naver_news_vec, meta_naver_news (article_content, title)

---

### 8. 계층적 벡터 검색을 활용한 이종 미디어 데이터셋 탐색 시스템

**분류:** 정보 검색 / IR

**연구 목적:**
데이터셋 레벨(dcat_dataset_vec)과 콘텐츠 레벨(meta_youtube_video_vec, meta_naver_news_vec)
두 단계 벡터 검색을 결합해 "어떤 데이터셋에 무엇이 들어 있는가"를 의미 기반으로 탐색하는 방법을 제안한다.

**핵심 기여:**
- 2레벨 계층적 벡터 검색 아키텍처 (데이터셋 → 아이템 drill-down)
- 다국어 임베딩(paraphrase-multilingual-mpnet-base-v2)의 이종 미디어 적용 성능 평가
- YouTube 영상 vs. 뉴스 기사 간 cross-modal 유사도 탐색 가능성 검토

**활용 데이터:** dcat_dataset_vec, meta_youtube_video_vec, meta_naver_news_vec

---

### 9. YouTube 썸네일+텍스트 멀티모달 임베딩을 이용한 영상 검색 성능 향상

**분류:** 멀티모달 / 정보 검색 (IR)

**연구 목적:**
CLIP ViT-B/32로 추출한 썸네일 시각 임베딩과 다국어 텍스트 임베딩을 late fusion 방식으로
결합해 텍스트 단독 검색 대비 정확도를 향상시키는 방법을 제안한다.
콘텐츠 카테고리(기술 설명형·인물형·제품형)별로 최적 융합 가중치가 다를 것이라는 가설을 검증한다.

**핵심 기여:**
- CLIP 썸네일 임베딩 + 텍스트 임베딩 late fusion 파이프라인 구축
- 텍스트 단독 vs. 시각 단독 vs. late fusion 성능 비교 실험 (MRR@10, NDCG@10)
- 카테고리 유형별 최적 융합 가중치(α) 분석

**활용 데이터:** meta_youtube_video (thumbnail_url, title, description), meta_youtube_video_vec

---

### 10. 비전-언어 모델을 이용한 YouTube 썸네일 메타데이터 자동 생성

**분류:** 멀티모달 / NLP·AI 메타데이터 생성

**연구 목적:**
비전-언어 모델(LLaVA 계열, Groq Vision API)을 통해 썸네일에서 시각적 메타데이터 4종
(visual_summary·dominant_objects·visual_emotion·layout_type)을 자동 추출하고,
트랜스크립트 기반 LLM 메타데이터가 포착하지 못하는 신규 정보를 정량화한다.

**핵심 기여:**
- VLM 썸네일 구조화 메타데이터 추출 파이프라인 구축 (Groq Vision API)
- 트랜스크립트 LLM 메타 vs. VLM 썸네일 메타의 정보 보완성 분석 (신규 정보 비율 > 30% 가설)
- 트랜스크립트 없는 영상(has_content=FALSE)에서 VLM 대체 활용 가능성 실증
- 4조건 Ablation으로 VLM 메타의 검색 기여도 측정

**활용 데이터:** meta_youtube_video (thumbnail_url), meta_youtube_video_ai (예정)

---

### 11. 썸네일-제목 의미 정합성을 활용한 한국어 YouTube 클릭베이트 탐지

**분류:** 멀티모달 / 콘텐츠 품질·신뢰

**연구 목적:**
CLIP 모델로 계산한 썸네일-제목 의미 정합성 점수(alignment score)를 클릭베이트 탐지
신호로 활용하는 zero-shot 방법을 제안한다. 텍스트 패턴 분석이 포착하지 못하는
"시각적 낚시형"(썸네일만 이상) 클릭베이트 탐지 효과를 검증한다.

**핵심 기여:**
- CLIP 썸네일-제목 코사인 유사도 기반 zero-shot 클릭베이트 탐지 방법
- 한국어 YouTube 클릭베이트 레이블 데이터셋 300건 구축 (Cohen's Kappa 검증)
- 텍스트 단독 vs. 시각 단독 vs. 멀티모달 결합 탐지 성능 비교 (F1, ROC-AUC)
- 클릭베이트 유형 분류: 시각적 낚시형 / 텍스트 낚시형 / 혼합형

**활용 데이터:** meta_youtube_video (thumbnail_url, title), 수동 레이블 300건

---

## 우선순위 제안

| 순위 | 주제 | 이유 |
|------|------|------|
| ★★★ | 1번 / P01 (pseudo_volume 보정) | 독창적 방법론, 수식 형식화 가능, 데이터 이미 존재 |
| ★★★ | 2번 / P02 (DCAT 플랫폼 설계) | 시스템 논문으로 전체 플랫폼 기여를 포괄 |
| ★★★ | 9번 / P09 (멀티모달 검색) | CLIP CPU 동작, 썸네일 즉시 수집 가능, 실험 설계 명확 |
| ★★☆ | 3번 / P03 (LLM 메타데이터 생성) | NLP 분야 어필, meta_youtube_video_ai 구현 필요 |
| ★★☆ | 6번 / P06 (쇼핑-YouTube Granger) | 크로스소스 분석, 인과 검정 포함 시 임팩트 높음 |
| ★★☆ | 7번 / P07 (한국어 RAG Q&A) | NLP·IR 분야 어필, 평가 데이터셋(QA 100건) 구축 필요 |
| ★★☆ | 11번 / P11 (클릭베이트 탐지) | 독창적 멀티모달 응용, 300건 레이블링이 주요 비용 |
| ★★☆ | 10번 / P10 (VLM 썸네일 메타) | P03 자연스러운 확장, Groq Vision API 가용 여부 사전 확인 필요 |
| ★☆☆ | 5번 / P05 (뉴스 댓글 임팩트) | 소셜 분석, 시계열 댓글 수집 기간 확보 필요 |
| ★☆☆ | 4번 / P04 (Persona 독립 가정) | 방법론 검증 논문, 비교 대상 실데이터 필요 |
| ★☆☆ | 8번 / P08 (계층적 벡터 검색) | IR 분야, 검색 평가 데이터셋 구축 필요 |
