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
- **trigger 성격·검수(2026-08-07c, freeze)**: trigger는 **"category-level, seed-independent
  query trigger"**로 정의하며 **정확한 카테고리 GT를 주장하지 않는다**(categoryId=Sampling
  Anchor 철학과 일치). trigger는 Suggest에 넣는 seed 문자열이고 최종 쿼리는 **관찰 가능한
  Suggest 결과에서 수집**한다(⚠️ "Suggest가 사용자 의도를 그대로 반영" 단정 금지 — 우리가
  쿼리를 창작 안 했다까지만 주장). 검수 3원칙: ① seed 구와 직접 겹치지 않음, ② 특정 seed
  검색의도 재현 안 함('강의'·'꿀팁' 제외), ③ 형식어로 검색공간 과협착 회피('게임 방송'→'게임').
  **Suggest 결과 보고 trigger 사후 수정 금지.** 음절 sweep은 **모든 카테고리 동일 고정 목록**
  (카테고리별 상이/사후변경 금지). **trigger 개수는 카테고리마다 2개로 강제하지 않음**(순수
  동의어 중복 회피 — 동물·게임은 1개). 한계: People&Blogs는 형식성이 남음(명시). 확정본
  `query_triggers.json` status=frozen.
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
- **🔒 쿼리 선별(curation) 규칙 (2026-08-08, retrieval 前 freeze)**: raw 560 후보에 아래
  분류를 적용하고 **후보마다 decision+reason을 전부 기록**(exclusion log → Appendix funnel).
  "정보성" 단일 기준의 주관성을 줄이기 위해 다축 분류:
  - **EXCLUDE:navigational** — 특정 채널/크리에이터/프로그램/브랜드를 찾는 쿼리(과학쿠키,
    뉴스타파, 자동차보험 차통령). ⚠️ **고유명사 유무가 아니라 의도로 판정**(손흥민 경기분석=keep).
  - **EXCLUDE:category_mismatch** — 실제 주제가 카테고리와 다름(동물의숲=게임, 자동차 게임/
    장난감/노래/다이캐스트).
  - **EXCLUDE:non_content_service** — 콘텐츠가 아니라 상품/서비스/도구 검색(자동차보험·담보대출,
    스포츠토토·가방, 음악 다운로드 앱, 헤드셋/스피커).
  - **FLAG:too_broad** — 사실상 카테고리/trigger 단어(자동차, 게임, 공부). **제외하지 않고
    flag** → Query Pilot에서 pool 크기·relevance 보고 사전 규칙으로 처리.
  - **KEEP:topical** — 해당 카테고리 콘텐츠를 찾는 구체적 정보요구 쿼리(자동차 배터리 교체,
    과학 감수분열, 게임 추천).
  - **REVIEW:ambiguous** — 경계 사례 → 사람이 재검토(14 카테고리 간 기준 일관성 확인).
  - **navigational 제외의 H2 근거**: 고유명사 exact-match 쿼리는 텍스트 매칭 우위를 재게 되어
    fusion의 semantic 효과 측정을 흐림 → 제외가 H2 construct와 정합(단순 '정리'가 아님).
  - 순서: 규칙 freeze → 560 전수 적용(사유 기록) → 사람이 REVIEW·경계 재검토 → Query Pilot →
    최종 수 freeze. **사람이 '좋아 보이는 것'을 고르는 게 아니라 명시 규칙의 경계만 처리.**
  - **broad 처리 규칙(Pilot 전 사전등록)**: FLAG:too_broad 쿼리는 KEEP:topical 후보로 카테고리
    목표 N을 못 채울 때만 fallback으로 쓰되, **Query Pilot에서 그 broad 쿼리의 pooled 후보 수가
    per-query 라벨링 상한(=Pilot 중앙값 pool의 1.5배로 사전 확정)을 넘으면 제외**한다. 성능이
    아니라 pool 크기로만 판단(HARKing 방지).
  - **경계 판정 원칙(자동차 worked example 확정)**: 시장·가격·소유/행정 정보는 topical KEEP
    (자동차 가격, 명의이전); 상품·서비스·거래·금융은 non_content_service EXCLUDE(보험·대출·
    가방·앱); 사운드/ASMR·'강의' 등 소비형식/broad는 REVIEW 유지.
  - **🔒 사람 검수 discipline(cherry-pick 방지, 2026-08-08)**: KEEP/EXCLUDE/REVIEW 재검수는
    **"좋다/별로다" 품질 판단 금지**. 오직 **frozen rule 위반 여부**만 보고, 변경 시 **기존
    reason_code**(NAVIGATIONAL / CATEGORY_MISMATCH / NON_CONTENT_SERVICE / TOO_BROAD /
    AMBIGUOUS)로 **사유를 기록**한다. 즉 사람은 규칙의 경계를 적용할 뿐 선호로 고르지 않는다.
    EXCLUDE도 audit(자동 substring 과잉 오탐 복원 — 예: '리스'가 '플레이리스트'를 오매치한
    4건). navigational은 고유명사 유무가 아니라 **의도**로 판정.
  - **🔒 최종 sampling 규칙(Pilot 전 freeze, 2026-08-08)**: clean eligible pool에서 **seed-
    독립 deterministic 표본추출**(고정 seed)로 **카테고리별 동일 N** 선정. **Pilot 결과(성능/
    relevance)를 보고 쿼리를 고르거나 빼지 않는다**(HARKing). Query Pilot은 **pool feasibility·
    라벨링 부담·broad 처리** 판단에만 쓴다. 최종 N은 Pilot의 pool 크기로 역산해 확정.
  - **분류기 v2(루프 검수 후 적용)**: SERVICE_TERMS substring 과잉 완화('리스' 등 짧은 term
    단어경계화/제거, 구매·가입·할인류는 auto-EXCLUDE 대신 REVIEW로 강등). 검수 중인 현재
    query_curation.json은 그대로 두고 검수 반영 시 함께 재생성.
  - **🔒 REVIEW 최종 판정 6원칙(2026-08-11, 마지막 curation 단계)**: REVIEW 100건을
    아래 규칙으로만 판정하고 종료(추가 대규모 필터링 금지 — curation drift 방지).
    ① 표기(띄어쓰기) 차이만으로 다른 판정 금지('음악감상'≡'음악 감상' → 동일 KEEP).
    ② 애매하면 SEMANTIC_MISMATCH 단정 대신 AMBIGUOUS_INTENT.
    ③ category **mismatch**(다른 도메인 그 자체: 자동차 게임)와 **target ambiguity**
    ('X 나오는 영화': 카테고리 콘텐츠일 수도)를 구분 — 후자는 REVIEW.
    ④ product(제품 탐색)와 how-to(방법/리뷰 콘텐츠) 구분 — how-to는 KEEP.
    ⑤ navigational은 고유명사 유무가 아니라 **intent**로(손흥민 경기분석=KEEP).
    ⑥ **KEEP을 '좋은 query' 기준으로 재선별 금지** — rule 위반만 본다.
  - **🔒 04e 최종 adjudication 규칙(2026-08-11, REVIEW 100 종결 · retrieval 前 freeze)**:
    REVIEW 100건**만** 대상(KEEP 341·EXCLUDE 106·FLAG 13 불변). intent를 **A(navigational)/
    B(topical-content)/C(ambiguous)** 로 기록하되 **최종 decision은 반드시 KEEP/EXCLUDE 이진**
    (C는 판정 과정의 중간 상태일 뿐 최종 pool에 남기지 않는다). 기준:
    - **KEEP**: query 자체에서 해당 카테고리의 YouTube **content 탐색의 합리적 dominant
      intent**를 식별할 수 있는 경우("100% 확실"이 아니라 "합리적 dominant intent"—
      음악감상·게임스토리·동물원은 KEEP).
    - **EXCLUDE**: navigational(특정 채널·프로그램·매체·인물·사업체 entity 지칭) / category
      mismatch / non-content·service / **content-search intent를 충분히 식별할 수 없는
      경우**(`INSUFFICIENT_CONTENT_INTENT` — 예: 자동차 낙엽, 음악 나무) / **query가 다른
      카테고리의 매체를 명시해 sampling stratum과 불일치**(`CROSS_DOMAIN` — 예: 동물 나오는
      영화, 자동차 만화; 매체 명시 기준. 단 '여행 남자코디'류 카테고리-프레임 라이프스타일은
      KEEP 유지 — '여행 다이소 꿀템'과 동일 구조라 일관).
    - **판정 사유는 "이상해 보여서"가 아니라 "content 탐색 intent 식별 불가"** 로 기록
      (reviewer 방어: "연구자 취향 제거"가 아님).
    - **웹 확인은 "이 문자열이 특정 entity를 지칭하는가"에만** 사용(품질·좋은쿼리 판단 금지).
      웹 확인 후에도 근거 불충분한 C는 EXCLUDE(`INSUFFICIENT_CONTENT_INTENT`).
    - 산출: `query_curation_adjudicated.json`(auto/reviewed/final/adjudicated 4+층 보존 +
      intent_class + evidence). exclusion funnel에 `INSUFFICIENT_CONTENT_INTENT` 추가.
    - **노하우* 대량 채널명 생성은 query-generation의 구조적 현상으로 audit 기록**(카테고리
      제거·sampling 페널티 금지). 최종 pool 확정 후 14 카테고리별 eligible 크기·제외율 비교.
- **개수 = 56부터 시작, Pilot으로 확정 (§0.6, 2026-08-07)**: **14×4=56을 1차 목표**로,
  Pilot의 실측 pool 크기·라벨링 부담을 보고 필요 시 70~84로 조정. **84로 무조건 늘리지
  않는다** — 코퍼스(1,397/최종 840)는 이미 충분하고 병목은 평가설계·qrels 품질이다. "라벨
  품질 떨어질 규모로 키우기보다 56을 제대로." "쿼리 수는 Pilot이 정한다"는 절차를 freeze.
  **→ [개정 2026-08-14c] Pilot·라벨링 여력 검토 후 최종 N=70(14×5)으로 확정**(56~84 범위 내).
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
- **라벨링(blind·독립, 3인 median-of-3, 2026-08-13 재-freeze)**: 후보 풀을 **3인 독립**
  라벨링(2=관련/1=부분관련/0=무관). **blind pooling** — 시트에 어느 시스템(Text/Visual/
  Fusion)이 뽑았는지 표시하지 않고 **쿼리별로 후보를 셔플**(위치 편향 차단). 세 라벨러는
  **상호 라벨을 볼 수 없는 독립 파일**(labeler_A/B/C)로 작업. 제목·썸네일 + **실제 영상
  내용(짧은 skim)** 확인(시각 채널 연구라 필수). 라벨링 가이드(1↔2 경계 예시 포함) 사전 배포.
- **집계 = median-of-3**: 최종 grade = 세 라벨의 **중앙값**. **A=B 쌍은 median{A,B,C}=A라
  C 없어도 값 불변** → C가 시간 부족 시 **불일치(A≠B) 쌍만** 판정해도 최종 라벨 동일(완전
  3인 vs 'C=불일치 심판'은 라벨 동일, **Fleiss κ 보고 가능 여부만 차이**). 완전/심판 선택은
  라벨 값이 아니라 **완료율** 기준으로 사후 결정(HARKing 아님). C 미커버 A≠B 잔여만 **백스톱**
  (|차이|1→평균 0.5/1.5, 0↔2→reconciliation.csv·없으면 1.0+플래그).
- **일치도·불일치**: **Cohen κ(A-B)** 항상 보고(원 라벨, 목표 ≥0.6). **완전 3인 달성 시
  Fleiss κ(3-way) + pairwise κ(A-C,B-C)** 추가 보고. **0↔2(A-B) 비율 보고**(신뢰성 지표).
- **쿼리 제거 규칙(사전 고정, 결과 무관)**: **최종 병합 qrels에서 grade ≥ 1인 문서가
  0개인 쿼리**를 평가셋에서 제외(IR 표준). "둘 다 전부 0"이 아니라 **최종 qrels 기준**으로
  판단. retrieval 성능이 아니라 qrels 존재 여부로만 판단하므로 §0.2 Freeze와 모순 없음.
  **최종 쿼리 수 + 제거 수 투명 보고**.

### 0.4 gap 계산 절차

- `gap_i = 1 - cos_sim(centered(v_img_i), centered(g_txt_i))` (§3.2). 라벨링 없이 전체
  코퍼스 자동 계산. **centered = 모달별 코퍼스 평균 차감 후 재정규화**(이미지·텍스트 각각의
  평균 벡터를 빼 이방성/modality-gap offset 제거). 근거는 아래 sanity check 실측(2026-08-06).
  - **gap 범위**: cos∈[−1,1]이므로 gap∈[0,2]. centering 후 일부 쌍의 cos가 음수가 될 수
    있어 **gap>1이 정상**(실측 최대 1.142). 버그 아님 — 논문에 범위·해석 명시.
  - **µ 고정**: µ_img·µ_gtxt는 **최종 evaluation 코퍼스(840편)**로 1회 계산해
    `gap.npz`에 저장하고, 이후 retrieval·분석 전 단계에 **동일 µ를 재사용**한다(재계산 금지).
- **sanity check(구현 검증, freeze 대상 아님 — 2026-08-05 실측 반영)**: 두 단계로 본다.
  1. **텍스트 이해(완료·PASS)**: gap용 인코더(`clip-ViT-B-32-multilingual-v1`)의 한국어
     구분력 확인(`code/sanity_gap_encoder.py`). ⚠️ **주의: raw cosine은 이방성(anisotropy)
     으로 전부 0.9+에 뭉쳐 의미 분리가 안 보인다**(영어도 동일 → 인코더 결함 아님, CLIP
     텍스트 임베딩의 알려진 성질). **평균중심화(centering) 후 측정**하면 유사쌍(평균 +0.53)
     과 무관쌍(평균 −0.09)이 깔끔히 분리됨을 확인 → 인코더는 한국어 의미를 제대로 구분한다.
  2. **gap 타당성(교차모달, 완료·PASS)**: **최종 EVAL 코퍼스(840편) 실측** — CENTERED
     정합-비정합 분리 **+0.129**(raw +0.031), 자기매칭 **R@1 8.2%**(랜덤 0.12%의 ~68배,
     raw 4.8%). **development 코퍼스**(dev 1,396편: +0.135/R@1 7.95%, 600편: +0.147/R@1 9.8%)
     와 **같은 방향으로 재현** → centering 선택이 특정 표본·코퍼스에 의존한 게 아님.
- **Corpus 구분 (dev vs 최종 eval)**: **최종 evaluation 코퍼스 = 840편**(duration>60,
  14×60 균형). **썸네일 다운로드 실패 0편 → 840 전부가 gap·다중모달 평가 대상**(dev와 달리
  N 손실 없음). *development/validation 코퍼스*(>20분, 1,397 수집→썸네일 1편 실패→1,396)는
  방법론 검증용으로 보존(`*_dev.*`)하되 최종 평가에는 쓰지 않는다. 논문 표기: *"The
  evaluation corpus comprises 840 videos (60 per category)."*
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

- **Retrieval 비교군**: Text-only / Visual-only / **Late Fusion**. Fusion score =
  α·minmax(text) + (1−α)·minmax(visual)(쿼리별 min-max 정규화).
- **🔒 α 처리 확정(2026-08-07c, 결과 보기 전)**: **primary operating point = α=0.5**
  — retrieval 결과를 참조하지 않고 사전에 고른 **대칭 equal-weight 지점**(*"α=0.5 was
  selected a priori as the symmetric equal-weight operating point, without reference to
  retrieval performance"*). 전체 **α grid = {0.0, 0.1, 0.2, …, 1.0}**(고정)에 대한 성능은
  **sensitivity analysis**로 보고(robustness라 부르지 않음 — α가 바뀌면 융합 모델 자체가
  바뀜). **최고점 α를 "optimal fusion"으로 선택·주장하지 않는다**(test leakage 금지).
- **지표**: MRR@10, NDCG@10(graded relevance), Recall@10, 그리고 gap-Δrank용 Spearman ρ.
- **통계**: H1=Wilcoxon signed-rank(paired), H2=Spearman 순위상관. **부트스트랩 95% CI**
  (1,000회) + **subsampling 수렴 곡선** + **MDES**(§6). gap 수준별 **Cohen's d**.
- **🔒 H1 계산 단위 확정(2026-08-07c)**: primary는 **Fusion(α=0.5) vs Text-only**.
  ① 쿼리별 **reciprocal rank@10**(Text RR, Fusion RR) 계산 → **paired Wilcoxon signed-rank**
  (p<0.05), ② **aggregate MRR@10 차이 = mean(Fusion RR) − mean(Text RR) > +0.05**.
  **두 조건 모두** 충족 시 H1 성공(§2). NDCG@10·Recall@10도 동일 쌍대 검정으로 보조 보고.
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
| **라벨 신뢰성 필수 보고** | 라벨러 **3인 median-of-3**; Cohen κ(A-B)·완전3인시 Fleiss κ (목표 ≥0.6) [개정 2026-08-13] |
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
- **3인 독립 라벨링(median-of-3)** → Cohen κ(A-B)·완전3인시 Fleiss κ로 일치도 보고 [개정 2026-08-13]
- **불일치 조정 규칙(사전 고정, 2026-08-07c 개정)**: (1) **경미한 불일치(|차이|=1: 0↔1,
  1↔2)** → **두 등급의 평균**(0.5·1.5; NDCG는 graded라 그대로 사용). (2) **심각한 불일치
  (0↔2)** → **두 라벨러가 해당 항목만 합의(consensus reconciliation)** 로 최종 등급 결정
  (TREC식 adjudication, 3인 불필요). 합의 실패 시 fallback=1(+플래그). (3) **κ는 원(독립)
  라벨로 계산**(신뢰도), **0↔2 비율 별도 보고**. 개정 이유: 0↔2를 단순 평균(→1.0)하면
  "한 명 완전관련·한 명 완전무관"이라는 강한 불일치를 은폐(2026-08-04 '전부 평균'에서 변경).

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
  **✅ eval 840편 무결성 검증(2026-08-07)**: 14×60 균형·videoId 840 고유·채널 cap 최대 5·
  Shorts 0·날짜 하한 준수. **duration 분포 = ≤60초 0 / 1~4분 168 / 4~20분 346 / >20분 326**
  (median 918s) → **4~20분 영상이 정상 유입**되어 duration 수정이 의도대로 작동함을 실증
  (dev는 전부 >20분이었음). seed allocation은 round-robin+availability 결과(예: 코미디
  개그=4는 개그 seed의 categoryId-23 통과분이 적어 소진된 것 — 규칙 위반 아님).
  **표현 원칙**: 채널 549개는 "cap으로 집중 완화 결과"로 기술(‘최고 다양성’ 과장 금지);
  3개 API 키는 **failover 구성**으로 기술(별도 프로젝트가 아니면 쿼터 3배 아님); 60편은
  "카테고리별 표본 수 동일 유지"로 기술(‘과학적 최적’ 주장 금지).
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
- **🔒 2026-08-08 (쿼리 curation 다축 규칙 — retrieval 前)**: raw 560 → 자동분류(04b)
  → reviewed(04c: navigational 공백형·product) → semantic override(04d: content-search
  기준, 71건). auto/reviewed/final 3층 audit 보존. ambiguous는 강제 EXCLUDE 대신 REVIEW.
- **🔒 2026-08-11 (REVIEW 6원칙 §0.2)**: REVIEW 100 판정을 6원칙으로만(표기차 무시,
  애매→AMBIGUOUS_INTENT, mismatch/target 구분, product/how-to 구분, intent 기반 nav,
  KEEP 재선별 금지). curation drift 방지.
- **🔒 2026-08-11b (04e 최종 adjudication 규칙 §0.2 — REVIEW 100 종결, retrieval 前)**:
  REVIEW 100만 대상(KEEP/EXCLUDE/FLAG 불변). intent A/B/C 기록하되 **최종은 KEEP/EXCLUDE
  이진**. KEEP=합리적 dominant content intent 식별 가능(과잉 엄격 금지: 음악감상·동물원 KEEP);
  EXCLUDE=nav/mismatch/service **또는 content intent 식별 불가**(`INSUFFICIENT_CONTENT_INTENT`).
  웹 확인은 entity 지칭 여부에만 국한. 근거 불충분 C는 EXCLUDE. `query_curation_adjudicated.json`
  산출 + funnel에 사유 추가. 노하우* 채널 대량생성은 audit 기록(카테고리 페널티 금지).
  선택지 비교(positive content-intent vs conservative-KEEP vs 잔여 REVIEW)에서 **positive
  content-intent + abstain(근거없음→EXCLUDE)** 채택 — construct validity(평가 가능한 명확한
  information need) 우선, pool 최대화보다 qrels 품질 우선.
- **🔒 2026-08-12 (04e cross-domain 종결 + Appendix QA — retrieval 前)**: 마지막 피드백
  (9.5/10, "더 필터링 아닌 재현성·편향 통제")의 category-consistency 지적 반영. 이진 종결
  freeze 유지를 위해 REVIEW 복귀 대신 **CROSS_DOMAIN EXCLUDE**로 처리. 범위는 **query가
  다른 카테고리 매체를 명시한 4건만**(동물 나오는 영화/애니/웹툰, 자동차 만화); 여행-프레임
  라이프스타일 3건(남자코디/다꾸/다이어리꾸미기)은 '여행 다이소 꿀템'과 동일 구조라 KEEP
  유지(일관성). 결과: **REVIEW 100 → KEEP 32/EXCLUDE 68, clean eligible pool 373**
  (최소 category 자동차 18 → N≤252 균형표집 가능). `query_curation_qa_table.csv`(category별
  raw→eligible funnel) 생성 = Appendix 재현성 증빙. **쿼리 curation 종료**, 다음은 05 retrieval.
- **🔒 2026-08-12b (쿼리 표집·Pilot·FREEZE 완료 — retrieval 前 마지막)**:
  1. **04f deterministic 표집**: eligible 373 → 순서 md5(SALT+query) 사전식(코퍼스 seed 독립,
     nested) → 카테고리별 4개 = **56**.
  2. **04g Query Pilot(§0.6)**: pool size만 실측(성능 미측정). Top-10 평균 pool **23.6**
     (17~32, PREREG 예상 ~20~25 부합), Top-7 17.2.
  3. **04h FREEZE 확정**: **N=56 / pool Top-10**(§0.6 '56을 제대로', §0.3 depth 10 유지).
     `queries_frozen.json`(q00~q55, 14×4) 동결 — **retrieval 이후 변경 금지**.
  이후 05 retrieval → 06 라벨링 → qrels → 07 분석은 이 frozen 쿼리로만 수행한다.
- **🔒 2026-08-13 (라벨링 2인→3인 median-of-3 — 라벨 생성 前 변경, HARKing 아님)**:
  라벨이 하나도 없는 시점에 변경(결과 무관 = preregistration 안전). 근거: median-of-3는
  0↔2 심각 불일치의 **주관적 합의 회의를 제거**(중앙값이 결정적 tie-break)하고, 라벨러 1인
  편향을 희석한다. **핵심 성질**: A=B 쌍은 median{A,B,C}=A라 C가 값에 영향 없음 → C가
  전량이든 불일치 쌍만이든 **최종 라벨 동일**(Fleiss κ 보고 가능 여부만 차이). 운영: 3인
  병렬 시작 → A·B 완료 시 06b_checkpoint로 C 불일치 잔여 시트 생성 → C 페이스 OK면 완주
  (완전 3인), 늦으면 불일치만(심판 모드). 완전/심판 결정은 **완료율 기준**(라벨 값 아님).
  scripts: 06_make_sheets(3시트), 06b_checkpoint(신규), 06_merge_qrels(median-of-3+Fleiss κ).
  기존 2인 규칙(|차이|1 평균·0↔2 합의)은 **C 미커버 잔여용 백스톱**으로만 잔존.
- **🔒 2026-08-14 (표집 방법 amendment: md5-hash → greedy k-medoid — 라벨 생성 前, HARKing 아님)**:
  초기 deterministic hash 표집(md5)은 재현성은 확보했으나 category 내 query diversity·pool
  coverage를 함께 고려하지 못했다(예: 자동차가 detailing에 쏠림, 대표 쿼리 밀림). sampling
  audit(04i/j/k 진단 + 04f2/f3 비교)에서 **MD5 / farthest-first / cluster-medoid**를 사전 정의
  **representative+diverse** 기준으로 비교한 결과, **greedy k-medoid**가 coverage 0.455(최고)·
  diversity −0.174(최고)·centrality −0.033(md5와 동률)로 최선 → 최종 채택(04f_final_medoid.py).
  **결정성**: clustering·threshold·RNG 없음, k=4 고정, 인코더 mpnet 고정, 동점 md5 tie-break,
  임베딩 npz 캐시(재현 보강). 2회 실행 동일 검증 통과. 이전 md5 표본은 queries_frozen_v1.json 보존.
  query 생성(sweep)은 불변 — **표집 단계만** 변경. 재retrieval(pool 23.9)·재시트(1,336쌍) 갱신.
  **한계 기록**: 자동차 등 일부 category의 detailing 편중은 **eligible pool(=generation 특성)**
  이며 어떤 표집으로도 제거 불가(sampling ≠ generation 문제). sweep 채택 근거는 04l(추천검색어는
  navigational/상품 오염 더 큼). **이로써 query generation·curation·sampling 재론 종료 → 라벨링.**
- **🔒 2026-08-14b (generation 결함 발견·수정 + 최종 표집 확정 — 라벨 생성 前, HARKing 아님)**:
  **근본 결함 발견**: 음절 sweep(가나다…)은 사실상 **ㅏ모음 음절만** 탐색해 거/게/고/구/기 등
  타모음 완성어를 구조적으로 누락(예: 뉴스 경제/기자/교통사고, 자동차 리뷰/배터리/경매 못 잡음).
  → **초성 sweep(ㄱㄴㄷ…)** 로 revised(04_gen_jamo): 동일 trigger에서 해당 초성 전체 모음 탐색.
  음절 baseline 보존. **동일 curation**(04_curate_jamo: 이전 EXCLUDE 재사용 + 렉시콘) 적용.
  **초성 pool에서 3-way 재비교**(04f4, 사전정의 지표): **META/NAV(/56) MD5=1·Farthest=1·Medoid=6**
  → **medoid 탈락**(coverage-max가 제작/메타 쿼리 유입). MD5가 content-natural·최고 재현성 →
  **MD5 + content-filter(META/NAV/product/near-dup skip)** 채택(04f_final_md5). **bare 추천검색어**도
  비교(04l2): **동물 eligible 3(<4) feasibility 실패 + 교육부·시사타파·스타일러·차량용품 등 기관/상품
  오염** → 기각. **최종 = 초성 sweep + MD5+content-filter, 56 freeze**(재retrieval pool 22.3·재시트).
  세 generation(음절/초성/bare) × 세 sampling(MD5/farthest/medoid) 전수 비교 완료.
  **query 재론 완전 종료 — 이후 라벨링만.**
- **🔒 2026-08-14c (N 56→70 확대 — 라벨 생성 前, §0.6 범위 내)**: 카테고리당 4→**5개(14×5=70)**.
  §0.6이 허용한 56~84 범위 내 조정(라벨 전이라 HARKing 아님). 5번째 픽의 약한 meta(스포츠
  데이터 분석가·브이로그 나레이션 등)는 필터 보강(META에 '분석가'·'나레이션' 추가)으로 정리 →
  스포츠 레전드·브이로그 롯데월드 등으로 교체. 재retrieval(pool 22.7)·재시트(**1,587쌍/인**).
  통계적 이득은 marginal이나 (쿼리,관련영상) 쌍·robustness 확보 목적. 잔여 약쿼리(게임 낙원 등)는
  zero-relevance가 사후 정리.
