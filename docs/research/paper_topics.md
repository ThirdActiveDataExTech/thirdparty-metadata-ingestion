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

### 1. 이종 웹 데이터 소스 통합을 위한 DCAT 2.0 기반 메타데이터 플랫폼 설계

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

### 2. 상대적 검색량 지수의 장기 연속 시계열 복원: pseudo_volume 보정 방법론

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

### 3. 성별·연령 독립 가정 기반 Persona Index의 유효성 및 한계 분석

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

### 4. 다중 레벨 벡터 검색을 활용한 이종 미디어 데이터셋 탐색 시스템

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

### 5. LLM 기반 비정형 미디어 메타데이터 자동 생성: 유튜브 트랜스크립트 활용

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

### 7. Persona Index 기반 소비자 수요 세분화와 뉴스 기사 반응의 연계 분석

**분류:** 소비자 행동 분석 / 마케팅 인텔리전스

**연구 목적:**
네이버 쇼핑 Persona Index(성별·연령별 수요 지수)와 관련 뉴스 기사의 댓글 반응을 결합해
특정 상품 카테고리에 대한 소비자 세그먼트별 관심도 변화를 분석한다.

**핵심 기여:**
- persona_index 급등 시점과 관련 뉴스 기사 댓글 급증 시점의 시간적 연계 패턴
- 성별·연령 세그먼트별 뉴스 소비 패턴과 쇼핑 수요의 상관성
- 미디어 이벤트(기사 보도)가 특정 인구통계 세그먼트의 쇼핑 수요에 미치는 효과 추정

**활용 데이터:** active_meta_naver_persona, active_meta_naver_news

---

### 8. 데이터 수집 파이프라인 신뢰성을 위한 Provenance 기반 이상 탐지

**분류:** 데이터 엔지니어링 / MLOps

**연구 목적:**
dcat_provenance에 축적된 수집 이력(성공/실패, 소요 시간, 수집 행 수)을 분석해
API 한도 초과, 네트워크 이상, 데이터 드리프트를 자동으로 탐지하는 방법을 제안한다.

**핵심 기여:**
- Provenance 로그 기반 수집 파이프라인 이상 탐지 규칙 체계
- rows_affected 급감 / 수집 시간 급증을 이용한 조기 경고 지표
- DCAT Provenance를 데이터 품질 모니터링 도구로 확장하는 방법론

**활용 데이터:** dcat_provenance (activity_type, status, rows_affected, started_at, ended_at, error_message)

---

## 우선순위 제안

| 순위 | 주제 | 이유 |
|------|------|------|
| ★★★ | 2번 (pseudo_volume 보정) | 독창적 방법론, 수식 형식화 가능, 데이터 이미 존재 |
| ★★★ | 1번 (DCAT 플랫폼 설계) | 시스템 논문으로 전체 플랫폼 기여를 포괄 |
| ★★☆ | 5번 (LLM 메타데이터 생성) | NLP 분야 어필, 단 meta_youtube_video_ai 구현 필요 |
| ★★☆ | 6번 (쇼핑-YouTube 상관) | 크로스소스 분석, 인과 검정 포함 시 임팩트 높음 |
| ★☆☆ | 3번 (Persona 독립 가정) | 방법론 검증 논문, 비교 대상 실데이터 필요 |
| ★☆☆ | 4번 (다중레벨 벡터 검색) | IR 분야, 검색 평가 데이터셋 구축 필요 |

---

## 투고 대상 저널/학회 후보

| 주제 유형 | 국내 | 국제 |
|----------|------|------|
| 시스템/아키텍처 | 한국정보과학회논문지, KIISE | VLDB, SIGMOD, WWW |
| 데이터 분석/방법론 | 한국데이터정보과학회지 | Knowledge-Based Systems, TKDE |
| NLP/AI | 한국어정보처리학회(HCLT) | ACL, EMNLP, COLING |
| 마케팅/소비자 행동 | 마케팅연구, 소비자학연구 | Journal of Retailing, IJIM |
