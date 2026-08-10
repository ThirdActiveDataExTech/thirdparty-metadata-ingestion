# P05 사전등록 (Pre-registration) + 예상 반박 대응

> **작성일: 2026-08-04 / 🔒 방법론 FREEZE: 2026-08-05.**
> 이 문서의 목적은 가설·표집·평가 기준·분석 방법을 **실험 결과를 보기 전에 고정**해,
> "결과를 보고 표본/기준을 맞췄다"는 사후 합리화(HARKing) 의심을 원천 차단하는 것이다.
> 실험 후 이 문서는 논문 4·5·7·8장(실험설계·평가·논의·한계)의 뼈대가 된다.
>
> **🔒 FREEZE 선언 (2026-08-05):** 여러 라운드의 검토(사용자·동료·AI)를 거쳐 방법론이
> 수렴했다. 이 시점 이후로는 **아이디어를 더 바꾸지 않고 구현·실험·해석에 집중**한다.
> 이후 방법론 변경은 (1) 반드시 하단 "변경 이력"에 근거와 함께 기록하고, (2) **실험
> 결과를 보고 나서 유리하게 바꾸는 것은 금지**한다(성능 기반 사후 조정 불가). 단,
> "정답 0개 쿼리 제거"처럼 사전 정의된 규칙에 따른 조정은 예외가 아니다(§0.3).

관련: 논문 초안(영문 v2) [../paper_draft_P05_thumbnail_fusion.md](../paper_draft_P05_thumbnail_fusion.md),
논문 초안(한국어 v3, Analysis 중심) [paper_draft_ko.md](paper_draft_ko.md),
재현 가이드 [README.md](README.md), 레퍼런스 [references.md](references.md)

---

## 0. 데이터·평가 프로토콜 (FREEZE, 재현 가능 규격)

> 아래 6절이 실험의 **정본(authoritative) 규격**이다. 누구나 그대로 재현할 수 있는
> 수준으로 고정한다. §1~§7은 이 프로토콜의 배경·근거·방어 논리다.

### 0.1 코퍼스 수집 규칙 (Corpus)

- **표집 틀**: `videoCategories.list(regionCode='KR')`의 `assignable=true` 카테고리
  **14개**(§4.1). 이는 코퍼스 **Sampling 틀**이지 평가 쿼리가 아니다(둘은 다른 개념).
- **🔑 categoryId = Sampling Anchor, NOT Ground Truth (핵심 선언)**: categoryId는
  **주제 다양성 확보를 위한 표집 앵커로만** 쓴다. H1/H2 어디서도 semantic label로 쓰지
  않는다. Seed Pilot 결과 일부 카테고리(동물·스포츠·코미디·과학기술)는 제작자가 categoryId를
  22/24/27로 다는 경향이 커서 자기잔존율이 낮음을 **관찰**했다(§Appendix dispersion).
  이는 categoryId가 완벽한 GT가 아님을 보여주지만, **노이즈가 있어도 주제와 상관이 있는 한
  층화 표집으로서 다양성 확보 목적은 달성**되므로 앵커로서 유효하다. 논문 문구: *"We use
  YouTube categoryId only as a sampling anchor to improve topical diversity; it is never
  used as a semantic ground truth."* (리뷰어의 "categoryId를 GT로 신뢰하나?" → "We do not.")
  ⚠️ **용어**: funnel의 categoryId 통과율(예: 게임 93% vs 동물 28%)은 **category retention
  = sampling efficiency**(seed 검색결과와 categoryId 일치율)일 뿐, **영상 "품질"이나
  "카테고리 정확도"가 아니다**. "게임=좋은 카테고리, 동물=나쁜 카테고리" 식 해석 금지.
- **구현 절차 (실측 기반, §변경이력 2026-08-04/05/05b)**: `videoCategoryId`는 search에서
  카테고리 필터로 못 쓴다(실측). 따라서 **search.list로 수집 → videos.list로
  `snippet.categoryId` 획득 → 원하는 14개 카테고리로 사후 필터링 → 카테고리별 목표
  개수까지 반복**한다.
- **검색어(seed) — 카테고리당 복수, 고정·문서화**: 단일 seed(공식 카테고리명)만으로는
  일부 카테고리 잔존율이 목표에 미달함을 실측(2026-08-05, 자동차 260→59 등). 따라서
  **카테고리당 복수 고정 seed**로 커버리지를 확보한다. seed는 **사람이 작성하되 후보 풀은
  `data/seeds.json`, 확정본은 `data/seeds_frozen.json`에 박제하고 논문 Appendix에 전문
  수록**한다 — 자동 생성(mostPopular 제목 마이닝·Autosuggest 등)은 **재현 불가·비공식
  API·인기 편향** 때문에 채택하지 않는다(§변경이력 2026-08-05b).
- **seed 확정 규칙(Seed Pilot 후, 2026-08-05d)**: 잔존율을 **통과/탈락 이분이 아니라
  우선순위(precision)**로 쓴다. 카테고리별 **잔존율 ≥ 0.20인 seed를 최대 5개까지**(내림차순,
  2개 미만이면 상위 2). **0.20 미만(예: 반도체 0.00·축제 0.00·카레이싱 0.04)만 제거** —
  0.2~0.5 seed(예: 고양이 0.46·물고기 0.28)는 "쓰레기"가 아니라 categoryId 유입률이 낮을
  뿐이라 **다양성 확보를 위해 함께 사용**한다(동물=강아지+고양이+앵무새+물고기+반려동물).
- **수집 시 round-robin(단일 seed 독식 방지)**: 본 수집은 seed를 **교대로 한 편씩** 채택해
  카테고리당 목표를 채운다 → 잔존율 최고 seed(예: 강아지)가 카테고리를 독식하는 것을 방지.
  채널당 최대 5개(채널 편향)와 함께 **"동물=강아지"류 편중을 구조적으로 차단**한다.
- **coverage는 본 수집이 실측**한다(Pilot은 1페이지 50건 상한이라 coverage 신호 없음).
  **seed는 코퍼스 커버리지용 Sampling Device일 뿐 평가에 쓰이지 않으며 어떤 가설 변수
  (gap·Δrank)와도 무관**하다.
- **정렬 혼합**: 표집 편향(viewCount만=옛날 유명 영상, date만=조회수 0 신규)을 줄이기
  위해 `relevance` + `viewCount` + `date` **3정렬을 혼합**해 수집·중복 제거.
- **채널 편향 차단**: **채널당 최대 5개**. (한 채널이 특정 카테고리를 지배하면 논문이
  무너짐. 결과적으로 300~500개 이상 채널 확보 → 채널 다양성 정량 보고.)
- **기간**: `publishedAfter` 최근 1~1.5년(예: 2025-01-01~) — 오래된 영상의 알고리즘·
  썸네일 스타일 차이 배제, 삭제·비공개 비율↓.
- **언어·지역**: `relevanceLanguage='ko'`, `regionCode='KR'`.
- **Shorts 제외(실제 길이 기준, §변경이력 2026-08-07)**: search에 duration 제한을 두지 않고,
  videos.list의 `contentDetails.duration`으로 **60초 초과만** 남긴다(라이브/예정=길이 0도 제외).
  ⚠️ 이전 `videoDuration='long'`은 YouTube API에서 **"20분 초과"**를 의미해 4~20분 일반 영상까지
  배제됨을 dev 코퍼스에서 실측 → 제거. 근거: Shorts는 CTR·썸네일(자동생성 프레임)·소비·추천이
  달라 gap 교란이나, 4~20분 일반 영상은 배제할 이유 없음. (search가 Shorts를 다수 반환하므로
  후처리로 거른다 — 페이지당 유효 수율은 낮아지나 PAGES=2로 흡수.)
- **목표 규모·표집 방식 — best-effort 층화 표집 (2026-08-07 Freeze)**: 카테고리당 목표
  **N=60**까지 수집(14×60=**840편 사전 Freeze**). **희소 카테고리는 억지로 60편을 맞추지
  않는다**("balanced"가 아니라 **"best-effort category-stratified sampling"**). N=100→60
  으로 낮춘 근거는 quota가 아니라(우리 코드에선 목표가 search quota를 줄이지 않음) **균형
  개선**(100편에선 과기 97 미달 → 60이면 더 많은 카테고리가 깔끔히 충원) + 840은 retrieval
  pool로 충분. **수집 결과를 보고 N을 늘리지 않는다**(sample-size HARKing 금지). 카테고리별
  실제 표본 수는 Results에 투명 보고. 확률표본이 아니라 **gap 분포 확보용 층화표본**.
- **🔬 dev / evaluation 코퍼스 분리 (2026-08-07)**: duration 오류로 만든 기존 1,397편
  (>20분 편중)은 **버리지 않고 development/validation 코퍼스**로 보존한다 —
  Seed Pilot·categoryId anchor·category dispersion·gap 인코더 이방성·centered gap을 이미
  실증한 방법론 검증 데이터다(`*_dev.*`로 보존). **최종 evaluation 코퍼스는 duration>60
  으로 새로 수집한 840편**이며, embedding·gap·retrieval·H2는 전부 이 최종 코퍼스로 한다.
  이 dev/eval 분리는 "방법론을 별도 데이터로 사전 검증한 뒤 최종 코퍼스를 구축"한 2단계
  설계로 논문에 기술한다.
- **대표성 주장 범위(사전 고정)**: 코퍼스를 "YouTube 전체의 대표"로 주장하지 **않는다**.
  주장 범위는 **"2025-01-01 이후 게시된 한국어 장편 YouTube 영상의 카테고리 층화표본"**으로
  좁게 규정하고, 이를 §한계에 명시한다(과대 대표성 주장 회피 = 방어력↑).
- **저장 메타데이터**: video_id, title, description, tags, categoryId, publishedAt,
  viewCount, likeCount, commentCount, duration, thumbnail_url, channelId,
  channelTitle, defaultLanguage, defaultAudioLanguage, liveBroadcastContent,
  madeForKids, licensedContent, topicCategories(가능 시). (저장 비용 낮고 분석 여지 큼.)

**Seed Pilot (seed 확정 절차 — 본 수집 전, Query Pilot §0.6과 별개)**

후보 seed를 **잔존율(categoryId 사후필터 통과율)로 압축·확정**한 뒤에 본 수집을 시작한다:

```
후보 seed(카테고리당 5~6개, seeds.json 초안)
  → Seed Pilot: seed당 relevance 1정렬 × 1페이지(50건)만 얕게 수집 (≈100 units/seed)
  → 각 seed의 categoryId 잔존율 측정
  → 카테고리당 잔존율 상위 3~4개만 남겨 seeds.json 확정 → 🔒 Freeze
  → 그 다음에 본 수집(3정렬 × 2페이지, videoDuration=long)
```

- **Freeze 무결성**: 잔존율은 **커버리지 지표이며 gap·Δrank 어떤 가설 변수와도 직교**
  하므로, 잔존율 기준 seed 압축은 "성능 유리하게 튜닝"이 아니다("규칙을 데이터로 최적화"
  원칙, §0.1 검색어). **seed는 gap을 보기 전에 잠긴다** → HARKing 불가.
- **쿼터 계획**: Seed Pilot ≈ 후보 84개 × 100 = ~8,400 units(하루 가능). 본 수집은
  살아남은 seed(카테고리당 3~4) × 3정렬 × 2페이지 = seed당 ~600 units라 **하루 1만 한도를
  넘을 수 있음 → 2~4일 분산 수집** 또는 페이지 축소로 관리(429 방지).

### 0.2 평가 쿼리 생성 + Freeze 규칙 (Evaluation Query)

- **성격**: 코퍼스 Sampling 키워드와 **완전히 다른 개념** — 실제 검색 시스템을 평가하는
  test query. Novelty는 gap 분석에서 나오므로 **쿼리는 화려할 필요 없이 평범·균형·
  재현 가능**하면 된다(쿼리는 평가 대상이지 실험 대상이 아님).
- **출처 확정(2026-08-07) — YouTube Suggest + seed-독립 trigger + freeze**: 사람이 임의
  창작하지 않고 **YouTube의 공개적으로 관찰 가능한 검색 제안(search-suggestion) 메커니즘**
  에서 생성한다(⚠️ "전역 검색 로그"라 단정 금지 — 내부 메커니즘 미공개. "실제 제공되는
  검색 제안어를 사용"이 정확). 절차: **카테고리 + seed와 독립적인 고정 trigger**(예:
  "음악 "+초성 ㄱ/ㄴ/ㄷ… 스윕; frozen seed 구 전체는 trigger로 쓰지 않음 → 코퍼스 sampling과
  평가의 coupling 최소화) → Suggest 수집 → 중복/유사어 제거 → 14 카테고리 층화 배분 →
  Query Pilot → **최종 쿼리셋 freeze·커밋**. **trigger 목록은 쿼리를 보기 전에 고정하고
  Appendix에 전부 공개**(쿼리 본 뒤 trigger 추가 금지). 🚫 **KeyBERT 등으로 우리 코퍼스
  영상 제목·설명에서 파생 금지**(circularity — 쿼리가 코퍼스 텍스트와 정합해 텍스트 채널이
  구조적으로 유리). Naver DataLab=도메인 불일치, Google Trends=재현 불가로 미채택.
- **trigger 성격·검수(2026-08-07c)**: trigger는 **"category-level, seed-independent query
  trigger"**로 정의하며 **정확한 카테고리 GT를 주장하지 않는다**(categoryId=Sampling Anchor
  철학과 일치). 각 trigger 검수 3원칙: ① frozen seed 구와 직접 겹치지 않음, ② 특정 seed의
  검색 의도를 재현하지 않음(예: '강의','꿀팁'은 seed 의도 재현 → 제외), ③ 카테고리 검색
  공간을 과도하게 좁히는 형식어 회피(예: '게임 방송'→'게임'). **Suggest 결과 수·품질을 보고
  trigger를 사후 수정하지 않는다**(기록).
- **유사변형 제거 규칙(2026-08-07c)**: lexical 유사도(substring/토큰 자카드)로 제거하지
  **않는다** — '축구' vs '축구 하이라이트'처럼 **검색 의도가 다른 변형을 보존**해야 한다.
  자동 제거는 **완전일치 + 매체 일반접미어('영상','동영상','유튜브','채널','쇼츠','모음')만
  다른 경우**로 한정('강아지 영상'≡'강아지'). 더 미세한 의도 중복은 **query freeze 시 사람이
  수동 검토로 제거하고 그 판단을 공개**한다.
- **trigger 중복 → 카테고리 귀속 규칙(2026-08-07c)**: trigger들이 겹쳐 한 쿼리가 여러
  카테고리에서 나올 수 있다. 파이프라인은 **전역 수집 → 정규화 dedup → 카테고리 귀속**:
  쿼리가 **단일 카테고리 trigger에서만** 나오면 그 카테고리에 귀속, **복수 카테고리에서
  나오면 억지로 분류하지 않고 drop(ambiguous, 수·목록 기록)**. 이후 균형 sampling + 사람
  최종 freeze. 각 쿼리는 `query/category/source_trigger/generation_timestamp/
  dedup_rule_version`를 저장해 Appendix에서 출처를 추적한다.
- **분포(대표성)**: 14개 카테고리에 **균등 배분**(카테고리당 동일 개수). 특정 도메인
  (예: 기술) 쏠림 방지 → "General Korean YouTube Retrieval" 주장 유지.
- **품질 규칙**: 쿼리 간 **주제 중복/유사 변형 금지**(예: "HBM"/"HBM 메모리"/"HBM4"를
  각각 세지 않음). 개수보다 **다양성**이 external validity에 중요.
- **개수 = 56부터 시작, Pilot으로 확정 (§0.6, 2026-08-07)**: **14×4=56을 1차 목표**로,
  Pilot의 실측 pool 크기·라벨링 부담을 보고 필요 시 70~84로 조정. **84로 무조건 늘리지
  않는다** — 코퍼스(1,397/최종 840)는 이미 충분하고 병목은 평가설계·qrels 품질이다. "라벨
  품질 떨어질 규모로 키우기보다 56을 제대로." "쿼리 수는 Pilot이 정한다"는 절차를 freeze.
- **🔒 Freeze 순서(필수)**: **쿼리 생성 → Freeze → Retrieval → Evaluation.** 평가
  쿼리는 **retrieval 실험을 돌리기 전에 확정**한다. 실험 결과(성능)를 보고 쿼리를
  빼거나 바꾸지 않는다("Evaluation queries were finalized before retrieval experiments").

### 0.3 Pooling + qrels 생성 절차

- **🔒 Pooling 절차 사전 고정(2026-08-07)**: **Top-K와 pooling 대상 시스템을 결과 보기 전에
  고정**한다 — 나중에 "Fusion Top20 추가", "Visual Top15까지" 같은 사후 변경 금지. Fusion이
  찾은 영상도 pooling으로 qrels에 포함되는 것은 **IR 표준(정상)** 이며 논문에 명시한다.
- **Pooling(편향 차단)**: 한 시스템의 Top-K만 라벨링하면 편향(Text만→Fusion이 올린
  영상을 모름 / Fusion만→Fusion 유리 후보만). 표준대로 **Text-only ∪ Visual-only ∪
  Late Fusion 각 Top10을 합집합·중복 제거**해 후보 풀 생성(평균 ~20~25개/쿼리 예상,
  Pilot으로 실측).
- **라벨링**: 후보 풀을 **2인 독립** 라벨링(2=관련 / 1=부분관련 / 0=무관). 제목·썸네일
  뿐 아니라 **실제 영상 내용**을 확인(시각 채널 연구라 시각 정보 반영 필수).
- **일치도**: Cohen's κ 보고(목표 substantial ≥ 0.6). **불일치는 두 등급의 평균**(§5.3).
- **쿼리 제거 규칙(사전 고정, 결과 무관)**: 라벨링 결과 **관련 영상(등급≥1)이 0개인
  쿼리는 평가셋에서 제외** — IR 표준(qrels 없는 쿼리는 평가 대상 아님, MS MARCO/BEIR/
  TREC). 단 **retrieval 성능이 아니라 qrels 존재 여부로만** 판단하므로 §0.2 Freeze와
  모순 아님. **최종 평가 쿼리 수 + 제거된 쿼리 수를 함께 투명 보고**.

### 0.4 gap 계산 절차

- `gap_i = 1 - cos_sim(centered(v_img_i), centered(g_txt_i))` (§3.2). 라벨링 없이 전체
  코퍼스 자동 계산. **centered = 모달별 코퍼스 평균 차감 후 재정규화**(이미지·텍스트 각각의
  평균 벡터를 빼 이방성/modality-gap offset 제거). 근거는 아래 sanity check 실측(2026-08-06).
  - **gap 범위**: cos∈[−1,1]이므로 gap∈[0,2]. centering 후 일부 쌍의 cos가 음수가 될 수
    있어 **gap>1이 정상**(실측 최대 1.142). 버그 아님 — 논문에 범위·해석 명시.
  - **µ 고정**: µ_img·µ_gtxt는 **최종 다중모달 평가 코퍼스(1,396편)**로 1회 계산해
    `gap.npz`에 저장하고, 이후 retrieval·분석 전 단계에 **동일 µ를 재사용**한다(재계산 금지).
- **sanity check(구현 검증, freeze 대상 아님 — 2026-08-05 실측 반영)**: 두 단계로 본다.
  1. **텍스트 이해(완료·PASS)**: gap용 인코더(`clip-ViT-B-32-multilingual-v1`)의 한국어
     구분력 확인(`code/sanity_gap_encoder.py`). ⚠️ **주의: raw cosine은 이방성(anisotropy)
     으로 전부 0.9+에 뭉쳐 의미 분리가 안 보인다**(영어도 동일 → 인코더 결함 아님, CLIP
     텍스트 임베딩의 알려진 성질). **평균중심화(centering) 후 측정**하면 유사쌍(평균 +0.53)
     과 무관쌍(평균 −0.09)이 깔끔히 분리됨을 확인 → 인코더는 한국어 의미를 제대로 구분한다.
  2. **gap 타당성(교차모달, 완료·PASS)**: 최종 1,396편 실측 — CENTERED 정합-비정합 분리
     **+0.135**(raw +0.033), 자기매칭 **R@1 7.95%**(랜덤 0.07%의 ~114배, raw 5.1%).
     600편(분리 +0.147, R@1 9.8%)과 **같은 방향으로 재현** → centering 선택이 특정 pilot
     표본에 의존한 게 아님. (후보 수 2.3배 증가로 R@1이 소폭 낮아진 것은 정상.)
- **Corpus vs 다중모달 평가 코퍼스 (N 구분, 논문 필수)**: 수집 corpus **N=1,397**. 그중
  썸네일 다운로드 실패 **1편**(`8sTbIc4zDIU`, 코미디/개그 seed)을 제외한 **N=1,396**이
  이미지-텍스트 gap·다중모달 평가 대상이다. **retrieval 평가도 1,396편으로** 수행하고,
  썸네일 없는 1편은 **평가에서 제외**한다(Text-only로만 넣으면 fusion 비교가 불공정 →
  제외가 깔끔, feedback 채택). 논문 표기: *"1,397 videos were collected; 1,396 had
  downloadable thumbnails and constitute the multimodal evaluation corpus."*
- **이방성 대응 — centered 임베딩을 전처리로 채택(2026-08-06 실측, construct validity 근거)**:
  RAW 교차모달 cos가 좁게 뭉쳐(600편 정합 0.249 vs 비정합 0.211) 순위가 이방성 노이즈에
  지배됨. **모달별 mean-centering** 후 정합-비정합 분리가 +0.038→**+0.147**(≈4배), 자기매칭
  **R@1 5.2%→9.8%**(랜덤 0.17% 대비 유의)로 **construct validity 개선**. gap은 centered로
  계산한다. ⚠️ **표현 주의**: 이는 "정답 gap"이 아니라 **우리 코퍼스의 이방성을 제거하는
  전처리**다(CLIPScore가 raw인데 우리가 centered인 이유). 또한 **H2는 Spearman(순위 기반)
  이라 분산 자체가 검정력을 좌우하지 않는다** — centering의 이점은 '분산 증가'가 아니라
  '순위의 의미성(construct validity) 개선'이다. 표준 이방성 제거(All-but-the-Top, Mu &
  Viswanath 2018) 인용.
- **채택 무결성 + ablation 계획**: centered 채택은 retrieval 전에 **construct validity
  로만** 결정(Δrank 안 봄) → HARKing 아님. **H2를 raw·centered 양쪽으로 돌려 ablation으로
  투명 보고**하되, **centered=사전등록 primary, raw=비교용**(어느 H2가 크냐로 고르지 않음).
- **rank preservation(실측 600편)**: raw↔centered gap 순위 **Spearman ρ=0.63, Kendall
  τ=0.46**. ρ는 **안정성(stability) 지표**이지 좋고/나쁨이 아니다 — preprocessing이 순위를
  얼마나 바꿨는지만 나타낸다(≈1 거의 유지, ≈0 새 순위, <0 뒤집음). ρ=0.63 = **적절한
  재배열(유지도 반전도 아님)**.
  ⚠️ **정정(2026-08-06, AI 리뷰 반영)**: 이전 판의 "construct validity 4배 개선 ⟹ ρ가
  낮아야 함"은 **논리적 과잉**이라 철회. construct validity(평균 match vs mismatch)와
  ρ(600개 전체 순위)는 **일대일 관계가 없다** — 상위 일부만 재배열돼도 separation은 크게
  오르고 ρ는 높게 유지될 수 있다. 따라서 ρ를 좋다/나쁘다로 해석하지 않으며, **재배열의
  정당성은 ρ 크기가 아니라 self-matching 과제 하의 construct validity(match>mismatch,
  R@1 향상)로만** 주장한다("객관적 정답"이 아니라 "self-matching 과제 하 대응 반영").
- **논문 문구(채택)**: 두 문장을 함께 쓴다.
  (1) *"We adopted mean-centering not because it improved retrieval performance, but
  because it substantially improved the construct validity of the gap measure by
  increasing the separation between matched and mismatched image–text pairs. Raw CLIP
  results are additionally reported as an ablation for transparency."*
  (2) *"Mean-centering produced a moderate reordering of similarities (Spearman ρ=0.63),
  indicating that the preprocessing neither preserved the original ranking unchanged nor
  arbitrarily distorted it. This reordering consistently improved construct validity, as
  evidenced by higher self-matching accuracy and substantially greater separation between
  matched and mismatched image–text pairs. Therefore, the modified ranking is justified by
  an external validation criterion rather than by retrieval performance."*
- **강건성 실측(600편)**: (1) **µ 표본크기 안정성** — µ(300) vs µ(600)로 계산한 gap이
  Spearman ρ=0.997·평균차 0.0008 → **600→1400 확장 시 gap 안정**. (2) centered gap std
  0.107 [95% CI 0.101–0.113] vs raw 0.035 [0.032–0.037](descriptive; 검정력 근거 아님).
  (3) 교차모달 신호 존재(R@1 랜덤의 ~58배) → **"썸네일이 검색에 기여 가능"이라는 대전제
  성립**. 카테고리별 gap 차이(동물 0.79 ~ 음악 0.89) 존재. µ는 최종 코퍼스에서 재계산(03).

### 0.5 Retrieval + 통계 분석 절차

- **Retrieval 비교군**: Text-only / Visual-only / Concat / Learned / **Late Fusion(α\*)**.
  α\*는 validation 쿼리로 그리드 탐색(§4.2).
- **지표**: MRR@10, NDCG@10(graded relevance), Recall@10, 그리고 gap-Δrank용 Spearman ρ.
- **통계**: H1=Wilcoxon signed-rank(paired), H2=Spearman 순위상관. **부트스트랩 95% CI**
  (1,000회) + **subsampling 수렴 곡선** + **MDES**(§6). gap 수준별 **Cohen's d**.
- **🔒 Δrank 정의 고정(2026-08-07, 결과 보기 전)**: `Δrank = rank_text − rank_fusion`
  → **양수 = fusion이 순위 개선**, 음수 = 악화. H2 = "**centered gap이 클수록 Δrank가
  증가**(Spearman ρ>0)". 이 정의를 04/05 코드·문서에 박는다.
- **🔒 H2 분석 구조 확정(2026-08-07b, 카테고리+반복측정 교란 선제 차단)**: gap은 **video-level
  에서 정의**되므로 H2의 기본 연관성은 **video-level 분석에서 직접 검증**한다. 같은 영상이
  여러 쿼리에 반복 관측되므로 순진한 all-pairs Spearman은 유의성을 부풀린다. 구조:
  - **Primary — video-level Spearman**: 영상별 **aggregate Δrank(사전등록 = median,** 극단값
    방어) → **Spearman(centered gap, aggregate Δrank)**. ⚠️ 이는 **설계 선택**이다 — 각
    영상이 관측치 1개(관련 쿼리가 1개든 8개든 동일 가중). "video-level 예측변수라 median이
    유일 정답"이라 **주장하지 않으며**, 이 집계의 장단점(쿼리별 개선/악화 정보 손실)을 명시한다.
  - **Secondary 1 — query-video 반복측정 보존(robustness)**: 원자료 `(query, video, gap,
    Δrank)`로 gap 효과 추정. **video와 query가 모두 반복되는 crossed 구조**이므로, 이를
    반영한 **사전 지정 모델**(video·query 교차 랜덤효과 mixed model, 또는 double-clustered
    robust SE)을 쓴다. **정확한 모델식은 구현 전에 하나로 freeze**(결과 보고 모델 선택 금지).
  - **Secondary 2 — category robustness**: **카테고리별 Spearman(stratified)** 을 사전 지정
    secondary로 수행("필요시"가 아니라 항상). 카테고리 내부에서도 관계가 유지되는지 확인.
  - **Descriptive**: 14개 중 양(+) 상관 카테고리 비율(방향 일관성 시각화 — 검정 승격 금지,
    카테고리별 N 작으면 불안정).
  - **Sensitivity**: **raw gap vs centered gap**으로 primary 재실행(§0.4). centered는
    construct validity로 사전 선택, raw는 **측정 선택의 영향을 보는 sensitivity**이지 H2
    성능으로 고른 게 아님.
  집계(median)·모델식·Δrank 방향 전부 **분포 보기 전 확정**(HARKing 방지).

### 0.6 Query Pilot Phase (쿼리 수·라벨링 규모를 데이터로 결정)

> **주의**: 이 Query Pilot은 **평가 쿼리 수**를 정하는 절차다. 코퍼스 **seed**를 정하는
> **Seed Pilot(§0.1)**과는 목적·대상·산출이 모두 다르다(혼동 금지).

본 실험 전에 소규모 파일럿으로 **pool 크기를 실측**해 최종 규모를 정한다:

```
Query Pilot: 쿼리 10개(카테고리에 분산) → §0.3 pooling(Top10×3) → 라벨링
     → 평균 pool size 실측(예: 17? 28?) + κ 예비 확인
     → 라벨링 총량 역산 → 최종 쿼리 수 확정(56 vs 84) + 필요 시 depth(10→7) 조정
     → 본 실험
```

이로써 "84가 가능한지 56이 맞는지"를 추측이 아니라 **숫자로** 결정한다.

---

---

## 1. 가설 (실험 전 고정)

두 가설은 **독립**이다 — 하나가 기각돼도 다른 하나가 논문을 지탱하도록 의도적으로 분리했다.

- **H1 (융합 효과)**: 썸네일 시각 임베딩 + 텍스트 임베딩의 late fusion이 text-only 대비
  검색 성능(MRR@10, NDCG@10)을 유의하게 향상시킨다.
- **H2 (gap 예측력)**: 영상별 **텍스트-이미지 의미 격차(gap)** 가 클수록, 융합으로 얻는
  순위 개선폭(Δrank)이 크다 — Spearman ρ(gap, Δrank) > 0.

논문의 프레이밍은 "우리 방법이 이긴다"가 아니라 **"시각 채널은 언제 도움이 되는가"**
(characterization). 따라서 결과가 "항상 돕지는 않는다"로 나와도 그 자체가 답이다.

---

## 2. 평가 기준 (실험 전 고정, 성공/실패 선을 미리 그음)

| 항목 | 사전 정의된 기준 |
|---|---|
| **H1 성공** | Late Fusion MRR@10 > Text-only + 0.05 **그리고** Wilcoxon signed-rank test p < 0.05 |
| **H2 성공** | Spearman ρ(gap, Δrank) > 0 **그리고** p < 0.05 |
| **강건성 필수 보고** | 위 지표 전부에 부트스트랩 95% CI 동반 + subsampling 수렴 곡선 |
| **라벨 신뢰성 필수 보고** | 라벨러 2인 Cohen's κ (목표: substantial ≥ 0.6) |
| **유의수준·검정력** | α = 0.05, power = 0.80 (Cohen 1988 관습, 인용으로 고정) |

---

## 3. 결과 분기 매트릭스 — 네 경우 모두 발표 가능한 서술이 존재

실험 결과가 어떻게 나오든 "버릴 판"이 되지 않도록, 사전에 각 경우의 서술을 정해둔다.

| | H2 유의 (gap↔Δrank O) | H2 약함 (상관 X) |
|---|---|---|
| **H1 성공** | 최상 — 융합이 돕고 gap이 그것을 예측 (완전한 스토리) | 융합은 돕지만 gap으로는 예측 안 됨 → 다른 예측 요인 탐색 필요 (기여 + 향후과제) |
| **H1 실패** | 전체론 미미하나 gap 높은 영상에선 도움 → 선별 적용 가치 (조건부 발견) | 이 도메인/이 지표로는 시각 채널 기여 제한적 → 부정 결과 + gap 지표 한계 규명 (informative null, §6 MDES와 결합) |

우하단(둘 다 실패)조차 §6의 MDES 보고와 결합하면 "우리 표본으로는 ρ > ρ_min 을
배제 가능 = 효과가 있어도 그보다 작다"는 **한계가 명시된 부정 결과**이지 실패가 아니다.

---

## 4. 표집 설계 (실험 전 고정) — "왜 이 채널/이 규모?" 방어

### 4.1 표집 틀 — YouTube 공식 카테고리 (주관 배제)

임의로 채널을 선정하지 않는다. **YouTube Data API `videoCategories.list(regionCode='KR')`가
반환하는 `assignable=true` 카테고리**를 표집 틀로 삼는다. "왜 이 주제들?"의 답은 "우리가
고른 게 아니라 YouTube가 정의한 분류".

**실측 (2026-08-04, 이 프로젝트 API 키로 호출):** KR 응답은 총 31개 카테고리를
반환하며 그중 `assignable=true`는 **14개** — ID 1(Film & Animation), 2(Autos &
Vehicles), 10(Music), 15(Pets & Animals), 17(Sports), 19(Travel & Events),
20(Gaming), 22(People & Blogs), 23(Comedy), 24(Entertainment), 25(News &
Politics), 26(Howto & Style), 27(Education), 28(Science & Technology). 나머지
17개는 `assignable=false`(Movies/Drama/Horror 등 레거시, 검색해도 영상 없음).

> **근거 기록 — "왜 14개? Nonprofits는 왜 빠졌나?"**: ID 29(Nonprofits & Activism)는
> **KR 응답에 아예 없다**(직접 `id=29,regionCode=KR` 조회 시 API 에러). US 응답에는
> `assignable=true`로 존재하므로, 이는 우리가 제외한 게 아니라 **YouTube가 한국 지역에
> 제공하지 않는 것**이다. 카테고리 포함/제외에 연구자 주관이 0%임을 보여주는 사례.
> (일반적으로 알려진 "15개 카테고리" 목록은 US/글로벌 기준이며, 우리 실험의 근거는
> 수집 시점 KR API 실제 응답이다 — 이 목록도 매니페스트에 스냅샷 저장, §4.4.)

### 4.2 카테고리별 수집 규칙 (자의성 배제, 실험 전 고정)

> **정본은 §0.1**이다. 아래는 초기(2026-08-04) 설계 근거 기록으로, 일부 항목(단일 q,
> videoCategoryId 직접 사용, N=70)은 §0.1·변경이력(2026-08-05/05b)에서 갱신됐다.
> 현재 규칙: **복수 seed(seeds.json) + categoryId 사후필터 + 3정렬 혼합 + Long-form only
> + 카테고리당 ~100편 균형표집.**

각 카테고리에 대해 동일 규칙으로 `search.list`를 호출한다 — 파라미터 각각이 근거를 갖는다:
- `videoCategoryId=C`: 그 카테고리 영상으로 제한(실측 검증: 반환 영상의 실제 categoryId가
  전부 C였음)
- `q=<C의 공식 한국어 카테고리명>`: **search API가 videoCategoryId 단독 사용을 허용하지
  않고 q를 요구**(실측: q 없으면 0건). 이 q는 연구자가 고른 게 아니라 `videoCategories.
  list(hl='ko')`가 반환하는 **YouTube 공식 카테고리명 그대로**(예: 10→음악, 27→교육) —
  카테고리도 YouTube 정의, 그 이름도 YouTube 정의라 주관 0% 유지
- `order=viewCount` (인기순): 실제로 소비되는 영상 대상 → 검색 논문 목적 부합
- `relevanceLanguage='ko'`, `regionCode='KR'`: 한국어 도메인
- `publishedAfter=<고정일>` (기간 하한): 삭제·비공개 영상 비율↓ → 재현성
- 카테고리당 **동일 개수 N = 70**: 특정 카테고리 과대표집 방지 (stratified sampling).
  14개 카테고리 × 70 = **총 목표 980편**(초안 목표 ~1,000편에 부합)
- 제외 규칙: 중복 video_id, 썸네일 없음, **Shorts(≤60초)** — Shorts는 커스텀 썸네일이
  아니라 자동 생성 프레임을 쓰는 경우가 많아 "썸네일 정보" 연구엔 교란요인. 정규 영상만.
- **미달 시**: "카테고리당 최대 N개, 확보량 미달 시 그대로 기록"(사전 고정 규칙)

### 4.3 규모의 근거 (두 규모를 다른 원칙으로 결정)

| 규모 | 결정 방법 | 근거 |
|---|---|---|
| **코퍼스 영상 수 M** | (A) 사전 검정력 분석 | medium 효과(ρ=0.3, Cohen 1988)를 α=0.05, power=0.8로 탐지 가능한 규모. 다양한 gap 값이 분포하는 검색 풀 확보 목적. 실제 필요 수치는 `05_analyze.py`에서 `statsmodels`로 산출 |
| **라벨링 표본 (쿼리×관련영상 쌍)** | (B) 민감도 분석 (MDES) | 관련성 라벨링은 사람 손이라 자유 확장 불가 → "감당 가능한 규모에서 탐지 가능한 최소 효과크기 ρ_min"을 보고. 값은 라벨링 완료 후 실제 쌍 수로 산출 |

**핵심**: 코퍼스 규모는 (A), 라벨링 표본은 (B) — 각 규모의 성격(확장 가능 vs 제약)에 맞는
논리를 붙인다. 두 기준 모두 **결과를 보기 전에** 이 문서로 고정한다.

### 4.4 재현성

수집 시점의 **영상 ID 전체를 매니페스트(`data/corpus.jsonl`)로 커밋**한다. YouTube
인기순은 시간에 따라 변하므로 "수집 시점 스냅샷"으로 박제. 썸네일 원본은 SeaweedFS
`research/p05_thumbnails/`에 백업(영상 삭제·썸네일 교체 후에도 재현 가능하도록).

---

## 5. 관련성 라벨링 프로토콜 (실험 전 고정) — "주관적이다" 방어

### 5.1 무엇을 라벨링하나

검색 성능(MRR/NDCG/Recall) 계산에 필요한 **qrels(쿼리별 정답)**. 라벨러는 각 (쿼리,
후보 영상) 쌍에 대해 아래 성문 기준으로 관련성 등급을 매긴다 — **주관적 속성이 아니라
"이 영상이 이 쿼리에 답하는가"라는 사실 판단**.

### 5.2 관련성 등급 정의 (라벨러에게 사전 배포, 부록 공개)

- **2 (관련)**: 영상 주제가 쿼리의 핵심 정보 요구를 직접 다룸
- **1 (부분관련)**: 쿼리 주제를 언급하나 부수적이거나 일부만 다룸
- **0 (무관)**: 쿼리와 주제적 연결 없음

라벨러는 제목·썸네일뿐 아니라 **실제 영상 내용**을 확인해 판단한다(시각 채널 연구이므로
시각 정보를 반영한 판정이 필수 — 텍스트만 보는 자동화 대비 이 논문에 더 정당).

### 5.3 절차

- 테스트 쿼리 `[DATA: ~50]`개, 쿼리당 상위 후보 `[DATA: depth]`개(품 절감을 위해
  depth=10 검토 — MRR@10/NDCG@10은 상위 10만 보므로 지표 영향 거의 없음)
- **2인 독립 라벨링** → Cohen's κ로 일치도 보고
- **불일치 조정 규칙(사전 고정)**: 두 등급이 다르면 **두 등급의 평균을 최종 등급으로**
  한다(2026-08-04 확정). 제3자 중재 방식 대비 (1) 추가 인력 불필요, (2) 규칙이
  단순명료해 재현·방어가 쉬움. NDCG는 graded relevance를 지원하므로 평균으로 생긴
  0.5·1.5 같은 중간 등급도 그대로 사용 가능. 모든 불일치 쌍(0↔1, 1↔2, **0↔2**)에 동일
  적용(0↔2→1.0). **심각 불일치(0↔2) 비율은 별도 보고**(κ와 함께 라벨 신뢰성 지표) —
  값이 높으면 성문 기준(§5.2) 재점검(2026-08-07b 추가).

### 5.4 방어 근거 요약

| 예상 태클 | 반박 장치 |
|---|---|
| "왜 사람이 라벨링?" | TREC 평가 관행(Voorhees 2000) — IR 분야 30년 표준 |
| "판정이 주관적이잖아?" | Cohen's κ로 일치도 측정 → 높으면 재현성 정량 입증 |
| "느낌대로 한 거 아냐?" | 사전 문서화된 성문 기준(§5.2) + 부록 공개 |
| "의견 갈릴 때 유리하게 처리?" | 사전 고정된 조정 규칙(§5.3) |

> 주의: v2에서 제거한 것은 **카테고리 라벨링**(썸네일 유형 분류, 기준 모호)이고, 여기
> **관련성 라벨링**은 IR 논문인 이상 제거 불가하며 성격이 다르다(사실 판단 + 표준 검증 절차).

---

## 6. 분석 방법 (실험 전 고정) — "표본 수 달라지면 결과도 달라지지 않나?" 방어

전체 성능·상관을 점추정만 하지 않고, **표집 변동에 대한 강건성을 정량적으로 보고**한다.

- **부트스트랩 95% CI**: 라벨링 쌍을 1,000회 리샘플 → MRR/NDCG/ρ의 신뢰구간.
  "다른 표본이면 달라지지 않냐"에 "그 다른 표본을 1,000번 만들어봤고 결과는 이 구간
  내에서 안정적"이라고 답.
- **Subsampling 수렴 곡선**: 데이터 50%/75%/100%에서 지표 재계산 → 표본이 커질수록
  값이 수렴함을 그래프로 입증(N에 따라 출렁이지 않음).
- **하이퍼파라미터 강건성**: α 그리드(0.1~0.9) + concat + learned fusion 비교 →
  특정 설정에서만 나온 우연이 아님.
- **검정**: H1 = Wilcoxon signed-rank(비모수, paired), H2 = Spearman 순위상관.
- **MDES**: 확정된 라벨링 쌍 수로 탐지 가능한 최소 ρ_min 산출·보고(§4.3-B).

---

## 7. 예상 반박 종합 대응표 (제출 전 체크리스트)

| 반박 | 대응 | 근거 위치 |
|---|---|---|
| 왜 이 채널/주제? | YouTube 공식 카테고리 표집 틀 | §4.1 |
| 왜 이 영상들? | 카테고리별 사전 고정 규칙 | §4.2 |
| 왜 이 규모(N)? | 코퍼스=검정력분석(A), 라벨=MDES(B) | §4.3 |
| 표본 수 달라지면 결과도? | 부트스트랩 CI + subsampling 곡선 | §6 |
| 라벨링 주관적 아냐? | TREC 표준 + Cohen's κ + 성문 기준 | §5 |
| 결과 보고 기준 맞춘 거 아냐? | 이 문서(실험 전 고정) 자체가 반증 | 문서 전체 |
| novelty 있나? | 제출 전 재검색 로그 | references.md |

---

## 변경 이력 (사전 결정을 실험 도중 바꿨을 때만 기록)

- **2026-08-04 (데이터 수집 전, 코퍼스 스크립트 작성 중)**: §4.2 수집 규칙 구체화.
  당초 "videoCategoryId + order=viewCount"만 상정했으나, 실측 결과 **search API가
  videoCategoryId 단독을 허용하지 않고 q(검색어)를 필수로 요구**(q 없으면 0건)함을 발견.
  검색어 주관 개입을 피하기 위해 q를 **YouTube 공식 한국어 카테고리명**(API가 반환하는
  값 그대로)으로 고정하는 것으로 규칙 확정. videoCategoryId가 카테고리 소속을 보장함은
  실측 검증(반환 영상 categoryId 전부 일치). `chart=mostPopular` 대안도 검토했으나
  카테고리별 개수 편차 큼(Music 30개 등)·일부 미지원이라 기각. 아직 데이터 수집 전이므로
  가설·평가기준·분석방법에는 영향 없음.
- **2026-08-04**: §5.3 불일치 조정 규칙을 "평균"으로 확정, §4.2에 Shorts(≤60초) 제외
  규칙 추가(자동생성 썸네일 교란 배제).
- **🔒 2026-08-05 (방법론 FREEZE)**: 여러 라운드 검토가 수렴. §0(데이터·평가 프로토콜)
  신설로 정본화. 주요 변경(전부 데이터 수집 전, 결과 무관):
  1. **코퍼스 수집 방식 전환**: "q=공식카테고리명 + videoCategoryId"에서 **"search로
     수집 → videos.list의 categoryId로 사후 필터링"**으로. 실측상 videoCategoryId가
     카테고리 필터로 부적합하고, 복합 카테고리명(예: "인물/블로그")이 order=viewCount와
     만나면 결과가 붕괴(5개)함을 확인. 사후 필터링은 이 문제를 원천 회피.
  2. **정렬 3혼합**(relevance+viewCount+date) 도입 — 단일 정렬 편향 완화 + viewCount
     붕괴 카테고리를 relevance분이 보충.
  3. **Shorts 제외 → 포함(+duration 분석축)**으로 전환. Shorts 제외가 숏폼 우세
     카테고리(반려동물 등)를 굶기던 문제를, "제외" 대신 "duration을 분석 변수로"로 해결.
  4. **채널당 최대 5개**(채널 편향 차단), **추가 메타데이터** 저장.
  5. **Evaluation Query 프로토콜 신설**(§0.2): 코퍼스 Sampling과 개념 분리, 외부
     검색어휘 기반, KeyBERT 등 텍스트 파생 금지(circularity), 카테고리 균등, 유사변형
     금지, **생성→Freeze→실험 순서 고정**.
  6. **Pooling 확정**(§0.3): Text∪Visual∪Fusion 각 Top10 합집합 → 2인 라벨링.
     "정답 0개 쿼리 사전 제거(결과 무관, 투명 보고)" 규칙 명시.
  7. **Pilot Phase 신설**(§0.6): 쿼리 10개로 pool 크기 실측 → 최종 쿼리 수(56 vs 84)를
     추측이 아니라 숫자로 결정. → 쿼리 수는 "Pilot이 정한다"는 절차를 freeze.
  8. **gap 인코더 sanity check**(§0.4): freeze 대상 아닌 구현 체크리스트로 분류.
  이상은 search 쿼터 리셋 후 구현 착수. 이후로는 방법론을 더 바꾸지 않고 실험 품질에 집중.
- **🔒 2026-08-05b (코퍼스 구축 규칙 확정 — 여전히 데이터(gap/retrieval) 수집 전, 결과
  무관)**: 여러 라운드 검토가 seed 문제로 수렴. 전부 **표집 단계 조정**이라 가설 결과와
  직교하며 무결성 영향 없음.
  1. **단일 seed → 카테고리당 복수 seed(3~4, `seeds.json` 고정·Appendix 수록)**. 단일
     공식 카테고리명 seed는 일부 카테고리 잔존율 미달(실측). 커버리지 확보 목적.
  2. **자동 seed 생성(mostPopular 제목 마이닝·Autosuggest·Google Trends·PlayBoard 등)
     기각**. 이유: 인기 순위는 매일 변동해 **재현 불가**, 비공식/유료 API는 ToS·쿼터
     리스크, mostPopular는 **인기 편향**을 코퍼스에 주입. "자동인 척"보다 **사람이 작성한
     고정 리스트를 정직하게 Appendix 공개**하는 것이 재현성·방어력 모두 우월(IR 관례).
  3. **Shorts 포함(+duration 분석축) → Long-form only(`videoDuration='long'`) 재전환**.
     Shorts는 CTR·썸네일(자동생성 프레임)·소비·추천이 달라 gap 검증 교란. duration은
     기록용으로만 저장.
  4. **균형(층화) 표집 명시 + 대표성 주장 범위 축소**. "YouTube 전체 대표" 주장 금지 →
     "2025-01-01 이후 한국어 장편의 카테고리 층화표본"으로 좁게 규정(§한계).
  5. **Seed Pilot 신설**(§0.1): 후보 seed를 잔존율로 압축·Freeze한 뒤 본 수집. Query
     Pilot(§0.6)과 목적·대상 분리(§0.6 상단 주의 문구). 잔존율=가설 직교라 무결성 유지.
  구현 순서: seeds.json 초안 → Seed Pilot → seed Freeze → 본 수집(Long-form).
- **🔒 2026-08-05c (Seed Pilot 완료 후 확정 — gap/retrieval 결과 보기 전, 무결성 유지)**:
  Seed Pilot 90 seed 전수 측정 완료. 예비 API 키(별도 GCP 프로젝트) failover로 동일 회차
  완주. 결과에 근거한 확정:
  1. **categoryId = Sampling Anchor, NOT Ground Truth 선언**(§0.1). Pilot이 4개 카테고리
     (동물40%·스포츠30%·코미디29%·과기21% 자기잔존)의 categoryId 희소성을 관찰 → 이를
     한계로 숨기지 않고 **Appendix dispersion 표 + "categoryId 품질 Pilot Study"로 분석**.
  2. **seed 확정 규칙**: 잔존율 ≥ 0.30 상위 4개(2개 미만이면 상위 2). 확정본
     `seeds_frozen.json`(status=frozen, 총 50 seed). 다양성은 복수 seed 세트 + 채널 cap이
     담보(순도만 최대화하지 않음 — 균질화로 gap 분산이 좁아지는 것 방지).
  3. **best-effort 층화 표집**으로 기술, 희소 카테고리 100편 강제 안 함, 카테고리별 실제 N
     투명 보고. coverage는 본 수집이 실측(Pilot은 50건 상한이라 coverage 신호 없음).
  4. 본 수집(01_build_corpus.py)은 `seeds_frozen.json`을 읽음. **이 시점으로 seed 논의
     종료** — 이후 연구 역량은 gap metric·retrieval·상관분석에 집중.
- **🔒 2026-08-05d (seed 확정 규칙 미세조정 — 여전히 gap/retrieval 전, 무결성 유지)**:
  리뷰 피드백 반영. 05c의 "잔존율 ≥ 0.30 상위 4"가 희소 카테고리 다양성을 과하게 깎는다는
  지적을 수용.
  1. **컷 0.30 → 0.20, 상위 4 → 상위 5**. 잔존율을 "통과/탈락"이 아니라 **우선순위**로
     재해석 — 매우 낮은 seed만 제거하고 0.2~0.5 seed는 다양성용으로 함께 사용. 결과:
     동물 3→5(+물고기·반려동물), 코미디 2→4(+개그·몰카) 등. 확정본 총 50→**63 seed**.
  2. **round-robin 수집 도입**(01): seed를 교대로 채택해 단일 seed 독식 방지("동물=강아지"
     위험을 seed 선택이 아니라 **수집 단계**에서 차단). 합성 테스트로 분포 균형 확인.
  3. 볼륨 가중("많이/조금") 수동 배분 대신 round-robin으로 **재현 가능**하게 구현.
  이로써 seed 방법론 확정. 본 수집 예상 ~37,800 units(2키 20k/일 → ~2일).
- **🔒 2026-08-06 (gap 전처리로 centered 채택 — retrieval/Δrank 보기 전, construct
  validity 기준)**: 본 수집 1일차 600편(6개 카테고리) + 02 임베딩으로 gap 교차모달 검증.
  gap 공식을 `1 - cos(centered v_img, centered g_txt)`로 정하되 **"정답 gap 확정"이 아니라
  "이방성 제거 전처리 채택"으로 표현**(AI 리뷰 반영). 근거·수치:
  1. **construct validity 개선**: 정합-비정합 분리 +0.038→+0.147, 자기매칭 R@1 5.2%→9.8%
     (절대값 우선 표기; 랜덤 0.17% 대비 유의는 보조).
  2. **정정**: H2는 Spearman(순위 기반)이라 "분산 낮음→검정력 약화"는 부정확. centering의
     근거는 분산이 아니라 **순위의 의미성**(construct validity). std 증가(0.035→0.107,
     CI 비겹침)는 descriptive로만 보고.
  3. **ablation 계획**: RAW·CENTERED 순위상관 ρ=0.63(순위 상당히 다름) → H2를 양쪽으로
     돌려 투명 보고. centered=사전등록 primary, raw=비교용(성능으로 고르지 않음=HARKing 방지).
  4. **µ 안정성 확인**: µ(300) vs µ(600) gap Spearman ρ=0.997 → 600→1400 확장에 안정.
  판단은 Δrank(H2 DV) 없이 construct validity로만 → 무결성 유지. (본 수집은 6/14 완료 후
  양키 쿼터 소진, 나머지 8개 익일 재개.)
- **🔒 2026-08-07 (duration 수정 + 코퍼스 재수집 — retrieval/H2 전, dev/eval 분리)**:
  dev 코퍼스(1,397편) 검증 중 `videoDuration='long'`이 "20분 초과"라 4~20분 일반 영상까지
  배제됨을 실측(min 1200s, 중앙값 32분). 의도는 "Shorts 제외"였으므로 수정:
  1. `videoDuration` 제거 + **실제 duration>60초 후처리 필터**(라이브/예정=0도 제외).
     스모크 실측: 무제한 검색 시 Shorts가 다수 유입되나 필터가 정확히 제거(≤60초 0건 확인).
  2. **목표 100→60/카테고리(840 Freeze)** — 근거는 quota가 아니라 균형 개선(과기류 미달↓)
     + 840은 pool로 충분. 수집 후 N 상향 금지(HARKing).
  3. **PAGES_PER_ORDER=2 유지**(안전, ~2일). 목표는 search quota와 무관.
  4. **dev/eval 코퍼스 분리**: 기존 1,397편은 방법론 검증 데이터(`*_dev.*`)로 보존, 최종
     evaluation 코퍼스는 새 840편. embedding·gap·retrieval·H2는 최종 코퍼스로 재수행
     (gap 방법론=centered는 freeze 유지, µ만 새 코퍼스로 재계산).
  기타 검증(채널 cap≤5·날짜≥2025-01-01·videoId 중복0)은 dev에서 전부 통과 확인.
- **🔒 2026-08-07b (평가/분석 프로토콜 확정 — Δrank 보기 전, AI 리뷰 3차 반영)**:
  1. **쿼리 소스 = YouTube Suggest + seed-독립 trigger + freeze**(§0.2). "전역 로그" 단정
     철회 → "공개 관찰 가능한 검색 제안". trigger 목록 사전 고정·Appendix 공개.
  2. **쿼리 수 56부터**(§0.2), 84 무조건 확대 금지. Pilot이 확정.
  3. **Pooling 절차 사전 고정**(§0.3): Top-K·대상 시스템 결과 전 고정, 사후 변경 금지.
     Fusion 발견 영상의 qrels 포함은 IR 표준으로 명시.
  4. **Δrank = rank_text − rank_fusion(+ = 개선) 고정**(§0.5).
  5. **H2 구조 확정**(§0.5): primary=영상당 median Δrank Spearman, secondary=query-video
     클러스터-robust 회귀 + 카테고리 내 Spearman, descriptive=양상관 카테고리 비율.
     gap이 video-level이라 primary를 video-level로 잡음(반복측정·카테고리 교란 선제 차단).
  6. **라벨링 = 2인 독립 + κ + skim(제목+썸네일+짧은 재생)**(§0.3·§5).
- **🔒 2026-08-07c (H2 프레이밍 정밀화 — AI 리뷰 4차, 여전히 Δrank 전)**: (1) "gap이
  video-level이라 median이 필연"이라는 과한 논리 완화 → **video-level 집계는 설계 선택**
  (각 영상=관측치 1개, 관련 쿼리 수 무관)이며 장단점 명시. (2) Secondary는 video·query가
  모두 반복되는 **crossed 구조**를 반영한 **사전지정 모델**(교차 랜덤효과/double-clustered)
  — 구현 전 모델식 1개로 freeze. (3) 카테고리 stratified는 "필요시"가 아니라 **항상 secondary**.
  (4) 불일치 0↔2(심각) 비율 별도 보고(§5.3). 쿼리 trigger의 seed-coupling은 "제거"가 아니라
  "직접 coupling 방지"로 표현(§0.2).
