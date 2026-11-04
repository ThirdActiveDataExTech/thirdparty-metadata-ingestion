# 다음 작업 로드맵

> **Last Updated:** 2026-10-30
> **목적:** 세션이 끊겨도 여기서부터 바로 이어갈 수 있도록, 남은 작업을 순서대로 기록한다.
> 완료된 작업의 상세 이력은 `git log` 참조 — 이 문서는 "지금 무엇을 해야 하는가"만 담는다.
> 항목을 끝내면 체크하고, 새로 발견한 항목은 해당 순서 구간에 추가한다.
>
> 수집 파이프라인 운영 설계(§가 자주 인용됨) 전체는
> [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md) 참조.

---

## ⭐ 현재 상태: 과제 개발 재착수 — §8 로드맵에 따라 진행 (2026-10-27 갱신)

**P05 논문(썸네일–텍스트 후기 융합 검색) 완료** — 2026-10-23 KIICE 발표까지 종료. 산출물은
`research/P05_thumbnail_fusion/`(로컬 전용). 과제 소개 영상도 제작 완료(`research/과제소개_영상.mp4`).

**이제부터는 연구개발계획서 기반 개발이 최우선이다.**

- 👉 **무엇을 할지는 [§8 최종 완성 로드맵](#8-연구개발계획서-기반-최종-완성-로드맵-2026-10-27-수립)** 참조.
  주관기관(모비젠) **1~4차년도 전 과업**을 구현 상태와 대조해 작업 단위(A1~D2)로 정리해 두었다.
- 핵심 사실: **1·2차년도 과업 중 미이행분이 다수**(특징 추출·분석, 패턴 기반 관계 분석,
  지식그래프 생성, 목적 기반 자동 탐색, 템플릿 파이프라인). 연차 순서가 아니라 **의존성 순서**로 진행한다.
- §1~§6은 과거 이력·세부 설계 보존용. §7(와이즈넛 정형)은 §8의 A3·B4와 연결된다.

---

## 진행 순서 (2026-07-23 합의)

남은 작업을 성격별로 분류해 아래 순서로 진행하기로 합의:

1. ~~**A. 결정만 필요한 것** — 2-3, 2-4, 2-10, 2-11, §3의 7번~~ **완료 (2026-07-23)**
2. ~~**B-1. 2-1(blog API 실측 → ADR-006)**~~ **완료 (2026-07-24)** — §5 AI 필드 실측
   검증은 D 순서(§6.1 이후)로 이미 미뤄둔 상태라 B의 나머지 항목 아님
3. **C. 외부 의존 (대기)** — §3의 8번(계정테이블 FK, 다른 팀 작업 대기)만 남음.
   ~~K8s Secret 생성~~ **완료 (2026-07-28)** — §1 항목 참조, 더 이상 외부 의존 아니었음
   (`RnD-analyzer01`에서 `sudo kubectl` 접근 가능해서 바로 처리)
4. **D. 구현 작업** — ~~§6.1 Phase 1(YouTube+쇼핑 파일럿)~~ **완료 (2026-07-27)**,
   ~~§6.1 Phase 2(Persona+뉴스+블로그)~~ **완료 (2026-07-28)**,
   ~~SeaweedFS raw/JSON-LD export + YouTube 트랜스크립트(자체 STT)~~ **완료
   (2026-07-28)** — 5개 소스 전부 실 서버·실 API 검증 끝남, `RnD-analyzer01`에도
   배포·파일럿 검증 완료 → 다음은 §5(AI 필드 실측·DDL·collector에 통합) 또는
   §6.2(Airflow 오케스트레이션) → §6.3(프론트엔드 API), 그 사이 성능 개선(커넥션
   재사용)·YouTube 트랜스크립트 백로그 소진도 병행 가능
   → **(2026-08-03) 위 '다음' 대신 P05 논문으로 전환 → 논문 완료(⭐ 참조), 현재 10/23 발표
   준비 중. 보류됐던 §6.2/§7 재개 여부는 발표 후 결정.**

---

## 0. (완료) `meta_shopping_insight` / `meta_persona_insight` / `meta_blog` 스키마 리뷰

**사용자 최종 확인 완료 (2026-07-23).** 세 테이블의 컬럼 목록은 대화 중 정리해서 전달함 —
필요하면 `sql/meta_shopping_insight.sql`, `sql/meta_persona_insight.sql`, `sql/meta_blog.sql`
직접 참조.

검토 중 발견된 비대칭:
- [x] ~~`meta_shopping_insight`의 `cat_level1~4` 예시 주석이 `meta_persona_insight`엔 없던 문제~~
      — `meta_persona_insight.sql`에 동일한 예시 주석 추가 완료, 롤백 트랜잭션 검증 완료.
- [x] ~~`meta_blog`에 플랫폼 구분 컬럼 없던 문제 (2-2)~~ — **결정: `platform TEXT NOT NULL`
      컬럼 추가** (news의 `is_naver_hosted` boolean 패턴 대신 `platform` 문자열 채택 — Naver
      블로그 검색 API가 blog.naver.com 외 티스토리/브런치/워드프레스/Blogger 등도 반환하기
      때문에 단순 boolean보다 세분화가 필요하다고 판단). `blog_id`/`log_no`/ADR-006 댓글·공감
      수집 가능 여부는 `platform='naver'`일 때만 해당하도록 주석 갱신. `sql/meta_blog.sql`,
      `sql/seeds.sql`(기존 3건 모두 `platform='naver'`) 반영·검증 완료.
- [x] ~~`meta_blog.updated_at`과 `meta_shopping_insight`/`meta_persona_insight`의
      `updated_at`이 갱신 계기가 다른 문제~~ — **결정: 스키마 변경 불필요, 문서화로 해결.**
      우연한 불일치가 아니라 §4의 발견형(아이템 자체가 재수집·변경 대상)/선언형(카테고리는
      거의 불변, 실측값은 `active_meta_*` 자식 테이블) 구분의 직접적 결과. 각 컬럼 주석이
      이미 정확히 설명하고 있어 스키마는 그대로 두고, §4 비교표에 이 차이를 명시하는 행 추가
      완료 (04_Collection_Pipeline_Operations.md §4.2 아래 표).

- [x] ~~세 테이블 컬럼 검토~~ — 위 3건 확인 완료 (2026-07-23)
- [x] ~~확정된 변경사항을 DDL(`sql/*.sql`)에 반영~~ — 완료
- [x] ~~컬럼 추가/변경 시 `sql/seeds.sql`의 해당 INSERT도 갱신~~ — 완료 (blog 3건)
- [x] ~~`docs/database/datagokr_schema.md` 테이블 목록·ERD 갱신 필요 여부 확인~~ — 그 문서의
      테이블 목록/ERD는 컬럼 단위가 아니라 한 줄 요약 수준이라 이번 변경(persona 주석,
      blog platform 컬럼)으로 갱신할 내용 없음 확인 완료

---

## 1. (완료) 실제 DB 반영

**2026-07-23 실제 서버에 반영 완료.** 기존 데이터는 전부 예시/시드 데이터라 재생성해도
무방하다고 확인 후 진행 — 롤백 아니라 실제 커밋.

- [x] ~~0번 스키마 리뷰가 먼저 끝나야 함~~ — 완료
- [x] ~~DDL 18개 파일 순서대로 서버에 재실행~~ — 완료 (`dataset_credentials.sql` 포함)
- [x] ~~`sql/seeds.sql` 재실행~~ — 완료
- [x] ~~`sql/views.sql` 재실행~~ — 완료 (DDL 적용 순서 7단계, 기존 체크리스트에 누락돼 있었음)
- [x] ~~임베딩 스크립트 재실행~~ — `embed_datasets.py`(6건), `embed_video.py`(4건),
      `embed_news.py`(3건) 전부 완료. 이 시점엔 `embed_blog.py`가 아직 없어서
      제외했었는데, 바로 다음(§4)에서 작성·실행까지 완료함(3건)
- [x] ~~검색 스크립트로 sanity check~~ — `search_datasets.py`/`search_video.py`/
      `search_news.py` 전부 실행, 결과 의미상 정상 확인
- [x] ~~`dataset-credentials-encryption-key` K8s Secret 실제 생성 (§9 참조)~~ —
      **완료 (2026-07-28)**. `RnD-analyzer01`에서 `sudo kubectl`로 `metadata-ingestion`
      네임스페이스 생성 + Secret 생성(`openssl rand -base64 32` 값), 같은 값을 `.env`의
      `ENCRYPTION_KEY`에도 반영(앱은 K8s API를 직접 안 부르고 `.env`에서만 읽으므로
      필수 — 안 하면 Secret만 만들어지고 계속 폴백 경로로 감). 실 서버에서
      `dataset_credentials` 테이블에 테스트 자격증명 삽입 → `dcat.get_api_key()`로
      복호화 → 원본과 정확히 일치 확인 → 테스트 행 정리까지 라운드트립 검증 완료.
      이제 사용자별 API Key 저장 기능(§9 설계)이 실제로 동작한다 — 이전엔
      `ENCRYPTION_KEY` 부재로 항상 플랫폼 공유 키 폴백만 조용히 타고 있었음

---

## 2. 남은 스키마·API 결정

- [x] ~~2-1. `active_meta_blog` 실제 API 조사 → ADR-006~~ — **결정 완료 (2026-07-24).**
      실제 API 호출로 검증: 반응(공감 등) 수는 `blog.like.naver.com`으로 브라우저 자동화
      없이 수집 가능(확인), 댓글 수는 cbox 계열 API가 정책적으로 차단됨(보류), 조회수는
      페이지에 아예 노출 안 됨(미수집). [ADR-006](adr/006_Naver_Blog_Metrics_Decision.md)
      작성 완료. `sql/active_meta_blog.sql` 재설계(`reaction_count`/
      `reaction_breakdown`/`delta_reactions`), 실 서버 반영·검증 완료.
- [x] ~~2-2. `meta_blog` 플랫폼 구분 확인~~ — **결정: `platform TEXT` 컬럼 추가.**
      2-1 실측 때 같이 재검증 완료: 다양한 검색어 350건 샘플에서 blog.naver.com 96%,
      tistory.com 3.4%, 커스텀 도메인 소수 확인 — GPT 근거 추정이 아니라 실측으로 확정.
- [x] ~~2-3. `dcat_dataset.publisher` NOT NULL 여부~~ — **결정: NOT NULL로 변경.** 모든
      시드 데이터가 값을 가지고 있고 NULL이 되는 시나리오가 없다고 판단. `sql/dcat_dataset.sql`
      반영·실 서버 적용 완료 (2026-07-23).
- [x] ~~2-4. ADR-002("Airflow 도입 전 K8s CronJob") 갱신 여부~~ — **결정: Superseded 처리.**
      [ADR-007](adr/007_Airflow_Adoption.md)로 Airflow 도입 확정 기록 완료.
      04_Collection_Pipeline_Operations.md §12, `00_Index.md` 반영 완료.
- [x] ~~2-5. API Key 저장 모델~~ — **결정: 데이터셋별 저장.** `sql/dataset_credentials.sql`
      작성 완료(pgcrypto 암호화, 롤백 트랜잭션으로 암복호화 라운드트립 검증 완료).
      04_Collection_Pipeline_Operations.md §9, `05_Secrets_ConfigMaps.md` 반영 완료.
- [x] ~~2-6. `dcat_dataset.owner_id` 모델~~ — **결정: 계정 테이블은 다른 담당자가 만들되,
      같은 `datagokr` database 안에 별도 스키마로 생성될 예정이라 FK를 나중에 걸 수 있음.**
      `owner_id TEXT` 컬럼 추가 완료(FK 없음, 롤백 트랜잭션 검증 완료).
      04_Collection_Pipeline_Operations.md §10 반영 완료. **단, 계정 테이블 스펙(테이블명/
      PK 타입)이 아직 미정 — FK 추가는 그 팀 작업 완료 후로 보류, §3의 1번·8번 항목 참조.**
- [x] ~~2-7. anchor 카테고리 UX~~ — **결정: 사용자가 고른 첫 번째 카테고리를 자동으로 anchor 지정.**
      04_Collection_Pipeline_Operations.md §4.3 반영 완료.
- [x] ~~2-8. admin 데이터셋 등록 경로~~ — **결정: YAML+git 동기화 방식 채택 안 함.** admin도
      user와 동일한 등록 핸들러를 그대로 사용 (`dataset_origin`만 다름, 서버가 caller 권한으로
      결정 — 클라이언트가 값을 보내면 안 됨). 04_Collection_Pipeline_Operations.md §5.7 반영 완료.
- [x] ~~2-9. 발견형 소스의 영상/기사/게시물 삭제 감지~~ — **결정: `is_removed`/`removed_at`
      컬럼으로 표시, 행은 보존.** `meta_video`/`meta_news`/`meta_blog`
      DDL에 반영 완료(오늘), 롤백 트랜잭션으로 검증 완료. 04_Collection_Pipeline_Operations.md
      §6.1 반영 완료.
- [x] ~~2-10. `next_collect_at` 드리프트 허용 여부~~ — **결정: 드리프트 허용.** "수집 종료
      시각 + 주기" 재계산 방식 그대로 유지 — 고정 시각이 필요한 다운스트림 소비자가 없음.
      04_Collection_Pipeline_Operations.md §12 반영 완료.
- [x] ~~2-11. 즉시 수집 트리거 필요 여부~~ — **결정: MVP엔 넣지 않는다.** 최대 15분 지연
      감수, Airflow REST API 트리거는 나중에 필요해지면 추가.
      04_Collection_Pipeline_Operations.md §12 반영 완료.

---

## 3. 추가로 필요한 테이블/컬럼 — 검토용 리스트업

이번 설계 논의(파이프라인 운영, 프론트엔드 연동)에서 드러난, 지금 스키마에 없는 것들이다.
"새 테이블"보다는 대부분 기존 테이블에 컬럼을 추가하는 정도다.

| # | 대상 | 종류 | 상태 | 설명 |
|---|------|------|------|------|
| 1 | `dcat_dataset.owner_id` | 컬럼 추가 | ✅ **컬럼 완료 · FK는 보류** | 데이터셋을 만든 사용자 식별. 컬럼(`TEXT`, FK 없음) 추가·검증 완료. 계정 테이블은 다른 담당자가 같은 `datagokr` DB 안에 별도 스키마로 만들 예정이나 스펙 미정 — 테이블 생성 후 FK 추가 필요 (8번 항목과 연결) |
| 2 | `meta_video.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 채널에서 사라진 영상 표시. 오늘 DDL 반영·검증 완료 |
| 3 | `meta_news.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 위와 동일 (발견형 소스라 동일 패턴 적용) |
| 4 | `meta_blog.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 위와 동일 |
| 5 | `dataset_credentials` | 신규 테이블 | ✅ **완료** | 데이터셋별 API Key 암호화 저장 (pgcrypto). 유일하게 "새 테이블"이 필요했던 항목 |
| 6 | `UNIQUE(owner_id, source_type, ...)` 형태의 중복 방지 제약 | 인덱스 추가 | ⏳ 보류 (owner_id 컬럼은 생겼으나 실사용 데이터 필요) | 04_Collection_Pipeline_Operations.md §7.2~7.3. JSONB `subjects` 배열 특성상 완벽한 DB 제약보다 애플리케이션 레벨 체크에 가까울 수 있음 |
| 7 | `meta_news.updated_at` | 컬럼 추가 | ✅ **완료** | 예전 세션에서 발견한 비대칭 — `meta_video`/`meta_blog`와 동일 패턴으로 추가, 실 서버 반영 완료 (2026-07-23) |
| 8 | 계정 테이블 FK 연결 (`dcat_dataset.owner_id → <계정테이블>.<PK>`) | FK 제약 추가 (조건부, 남의 팀 일정 종속) | ⏳ **계정 테이블 스펙 확정 대기** | 계정/인증 테이블은 metadata-ingestion 팀이 아니라 플랫폼 다른 담당자가 만듦. 같은 `datagokr` DB 안에 별도 스키마로 생성될 예정(2026-07-23 기준 계획 단계, 테이블명·PK 타입 미정). 생성되면: (1) 실제로 같은 database인지 재확인 (다른 database면 FK 불가), (2) PK 타입에 맞춰 `owner_id` 타입 조정, (3) FK 추가 |

---

## 4. (거의 완료) 임베딩 파이프라인 마무리

- [x] ~~`scripts/embed_blog.py` 작성~~ — `embed_news.py` 패턴 그대로 이식 완료
      (`meta_blog` → `meta_blog_vec`, has_content 분기 동일)
- [x] ~~`scripts/search_blog.py` 작성~~ — `search_news.py` 패턴으로 완료
- [x] ~~실행해 검증~~ — 실 서버에 3건 임베딩 완료, 검색 결과 의미상 정상 확인 (2026-07-23)
- [ ] **증분 임베딩 방식으로 전환** — 지금 `embed_*.py`는 전체 DELETE→INSERT 재계산 방식이라
      새 데이터셋이 동적으로 등록돼도 자동으로 임베딩되지 않음 (수동 재실행 필요). §6.2
      Airflow 오케스트레이션 구축 시점에 같이 처리 — 그 전까진 급하지 않음(수동 재실행으로
      충분), 지금 당장 할 필요는 없음. **순서 제안(2026-07-27)**: 증분 전환을 먼저 하고
      그 다음에 Airflow task로 연결 — 지금 방식 그대로 자동 연결하면 영상 1개 늘 때마다
      수천 개 재임베딩하는 비효율 발생. SeaweedFS export(§6.1, `architecture/
      05_Object_Storage_Export.md` §6)와 구조적으로 같은 처지("수집 후 후속 단계, 현재 수동")

---

## 5. AI 메타데이터 테이블

> **⏸ 2026-08-03 잠정 보류 — P05 논문 작업 우선. 논문 완료 후 재개.**
> 아래는 보류 시점까지 확정/논의된 내용 전부 (재개 시 이걸로 바로 이어감).

**설계 제약 (2026-07-23 확정): 이 프로젝트를 위한 별도 학습·파인튜닝은 하지 않는다.**
사전학습된 오픈소스 모델(Groq API 경유 LLM 프롬프트, HuggingFace 사전학습 분류기/NER/
감성분석 모델 등)을 그대로 쓰는 것만 허용 — 어느 모델을 쓸지는 필드별로 구현 단계에서
후보를 비교해 결정. 상세: `datagokr_schema.md`의 "AI 메타데이터 파이프라인" 절.

**추가 결정/논의 (2026-07-29~31, 보류 직전):**
- **방향: 로컬 사전학습 모델 우선, Groq/LLM은 마지막 후보.** 로컬(KoBART 요약, KeyBERT
  키워드, 한국어 NER, 감성분석, zero-shot 분류, 정규식)으로 되는 데까지 먼저 밀고,
  안 되는 소수 필드만 나중에 LLM 검토. 23개 필드 중 17~18개는 로컬로 가능 추정,
  🔴(로컬 어려움)은 blog `ai_pros_cons`, youtube 썸네일 `ai_visual_emotion` 정도.
- **Groq 조사**: 무료티어 카드 없이 발급, 조직 단위 한도, llama-3.3-70b는 하루 1000건/
  llama-3.1-8b는 하루 14400건. 유저별 Groq 키는 §6.3(프론트 API) 때 dataset_credentials에
  `groq_api_key`로 추가(선택 항목, 안 주면 플랫폼 공유 키 폴백) — 지금 뉴스/블로그는
  admin이라 무관.
- **순서**: 뉴스 파일럿 → 블로그 복제 → YouTube.
- **재개 시 먼저 정할 검토 3가지**: (1) 후보 로컬모델 실측 검증부터(추천 — HuggingFace
  실존/유지보수/라이선스/CPU속도) (2) 필드 범위 축소 여부(🟢부터, 🟡🔴는 나중; 특히
  YouTube 썸네일 4필드 재검토) (3) 실행 시점(수집 run() 인라인 vs 별도 배치).
- 필드별 로컬 처리방식·확신도(🟢🟡🔴) 상세 표는 memory `project-metadata-ingestion-status` 참조.

- [ ] `meta_video_ai` DDL 작성 — 필드 후보 정리 완료(트랜스크립트 5개 +
      썸네일 VLM 4개, `datagokr_schema.md` 참조). P03/P06 연구 주제와 직결.
- [ ] `meta_news_ai` 필드 후보 정리 완료(신규, `datagokr_schema.md` 참조:
      ai_summary/keywords/entities/related_companies/sentiment/topic_category/is_opinion) —
      DDL은 아직. 실측 검증 필요(어느 필드가 실제로 유용한 정확도가 나오는지)
- [ ] `meta_blog_ai` 필드 후보 정리 완료(신규, `datagokr_schema.md` 참조:
      ai_summary/keywords/content_type/sponsored_likelihood/product_mentions/sentiment/
      pros_cons) — DDL은 아직. 실측 검증 필요

---

## 6. 수집 코드 작성 (가장 큰 작업)

운영 방식 상세 설계는 [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
전체 참조. 실제 `src/` 레이어 구조는 [architecture/03_Component_Architecture.md](architecture/03_Component_Architecture.md)
참조(`collectors/`+`pipelines/`+`database/` 분리 — 파일럿 구현 중 확정).

### 6.1 Collector 코드

**Phase 1 완료 (2026-07-27): YouTube(발견형) + Naver Shopping(선언형) 파일럿.**
실 서버·실 API로 끝까지 검증 완료:
- [x] ~~YouTube 수집 코드~~ — `src/collectors/youtube_collector.py`(페이지네이션·50개
      배치·Shorts 필터, 레거시 `youtube_channel_extractor.py`/`youtube_video_extractor.py`
      포팅) + `src/pipelines/youtube_pipeline.py`(신규/기존 분기, `is_removed` 삭제감지 +
      재등장 시 자동 해제). 실제 Samsung 채널(`UCWwgaK7x0_FR1goeSRazfsQ`)로 검증 —
      1431개 영상 발견, 재실행 시 delta 정확히 계산됨(중복 없음)
- [x] ~~쇼핑 수집 코드~~ — `src/collectors/naver_shopping_collector.py` +
      `src/collectors/naver_datalab_scale.py`(intra/inter_scale, persona도 재사용 가능) +
      `src/pipelines/naver_shopping_pipeline.py`(선언형, anchor 3개/호출 배칭). 실 API로
      검증 — 70행 반영, 재실행해도 upsert로 중복 없음
- [x] ~~공통 인프라~~ — `src/database/dcat.py`(provenance/registry/API키 공통 헬퍼),
      `src/common/retry.py`(레거시엔 없던 재시도+백오프 신규 추가), `src/main.py`
      (`python -m src.main run <dataset_id>` 수동 실행 CLI)
- [x] ~~단위 테스트~~ — `tests/`에 scale 보정 수학·Shorts 판정·재시도 로직 17건, 전부 통과

**Phase 2 (진행 중)**: Phase 1에서 검증된 패턴을 복제
- [x] ~~Naver Persona 수집 코드~~ — **완료 (2026-07-28).** `src/collectors/
      naver_persona_collector.py`(성별/연령 API 독립 호출) + `src/pipelines/
      naver_persona_pipeline.py`(stacked median으로 gender_scale/age_scale,
      12조합 persona_index = gender_pv×age_pv). `naver_datalab_scale.py`를
      shopping과 그대로 공유 재사용. 실 API로 검증 — 4카테고리×12조합=48행,
      재실행해도 upsert로 중복 없음
- [x] ~~Naver 뉴스 수집 코드~~ — **완료 (2026-07-28).** `src/collectors/
      naver_news_collector.py`(검색 API 페이지네이션, 본문 스크래핑, ADR-005 댓글수
      API) + `src/pipelines/naver_news_pipeline.py`. 자격증명 하드코딩·본문 셀렉터는
      레거시에서 정리해서 포팅.
      **개발 중 중요한 버그 발견·수정**: 처음엔 YouTube와 같은 "검색 결과에 없으면
      삭제" 방식을 썼는데, 뉴스 검색은 `sort=date` 슬라이딩 윈도우라 몇 분 만에도
      상위 N건 밖으로 밀려날 수 있음 — 실측 결과 기존 기사 146건이 "부재"로 나왔는데
      91건(62%)이 실제로는 살아있는 200 응답이었음. `check_article_still_exists()`로
      URL을 직접 재확인(404/410 확정시만 삭제 처리)하는 방식으로 수정 —
      04_Collection_Pipeline_Operations.md §6.1에 원칙 기록, **블로그도 동일 원칙
      적용 필요**. 실 API로 검증 — 1334개 기사, 댓글수(ADR-005) 987건 수집
- [x] ~~Naver 블로그 수집 코드~~ — **완료 (2026-07-28), Phase 2 마지막 항목.**
      `src/collectors/naver_blog_collector.py`(플랫폼 판정, 본문 스크래핑, ADR-006
      반응수 API) + `src/pipelines/naver_blog_pipeline.py`. 뉴스에서 확립한
      "검색 결과 부재만으로 삭제 판정 금지 — URL 직접 재확인" 원칙 처음부터 적용해서
      뉴스와 같은 버그를 반복하지 않음. 실 API로 검증 — 1283개 게시물(naver 대부분,
      tistory 일부), 반응수(ADR-006) 수집 정상.
      **버그 발견·수정 (뉴스에도 있던 버그, 3개 파이프라인 전부 수정)**: `item_count`
      계산이 `len(existing) + new_count`였는데, 여러 검색어에 매칭되는 항목을
      실행 중 `existing`에 추가하다 보니 이미 늘어난 `len(existing)`에 `new_count`를
      또 더해서 거의 2배로 뻥튀기됨(실측: blog 975건인데 1947로 기록). `meta_*` 테이블
      `count(*)` 직접 조회로 교체 — news/blog/youtube 파이프라인 전부 수정, 실 DB의
      틀린 값도 재계산해서 정정 완료
- [x] ~~Phase 2 전체 완료~~ — **2026-07-28.** YouTube(Phase 1)+쇼핑(Phase 1)+Persona+
      뉴스+블로그 5개 소스 전부 실 API·실 DB로 검증 완료. 다음은 §5(AI 필드) 또는
      §6.2(Airflow)
- [x] ~~쇼핑/Persona "오늘 하루만 수집" → inter_scale 항상 1.0으로 죽는 버그~~ —
      **완료 (2026-07-28), Phase 2 마무리 후 사용자 질문으로 발견.** "다음 수집 때
      정확히 무슨 일이 일어나는지" 설명하다가 발견 — 매번 새 날짜만 조회하니 DB
      기존 데이터와 겹치는 날짜가 없어 `inter_scale`(수집 구간 간 보정)이 실질적으로
      작동을 안 하고 있었음. **사용자 제안대로** "마지막 저장 날짜 - N일부터 어제까지"
      재조회하는 방식(`OVERLAP_DAYS=14`)으로 수정 — 겹치는 구간이 생겨 inter_scale이
      실제로 계산되고, 부수 효과로 Airflow 중단 후 재개 시 최대 14일 결측도 자동
      보충됨. `naver_shopping_pipeline.py`/`naver_persona_pipeline.py`/
      `meta_shopping_insight.py`/`meta_persona_insight.py`(`get_last_period` 추가) 수정.
      실 API로 검증 — scale_factor가 1.0이 아닌 실제 값(예: 1.130692)으로 계산됨 확인.
      04_Collection_Pipeline_Operations.md §6.2에 원칙 기록
- [x] ~~레거시와 재검증 후 추가 발견: API 호출 rate limiting 누락 + 최초 수집 소급
      백필 없음~~ — **완료 (2026-07-28).** 사용자가 레거시(`3amd/naver_shopping_insight.py`,
      `naver_persona.py`)와 라인 단위 대조를 요청해서 발견:
      1) 레거시는 매 호출 사이 `time.sleep(1초)`가 있었는데 포팅 시 빠뜨림 →
         `naver_shopping_collector.py`/`naver_persona_collector.py`의 `fetch_insight`/
         `fetch_ratios`가 호출 성공 직후 자체적으로 쉬도록 수정
      2) 레거시 `--auto`의 "데이터 없으면 1년 전부터 2단계 백필" 로직이 없었음 →
         `dcat_dataset.temporal_start`를 소급 수집 시작일로 재활용(사용자 제안).
         등록 시 지정하면 최초 수집이 그 날짜부터 통째로 가져옴(레거시처럼 2단계로
         안 나눔), 첫 수집 성공 후 실제 관측된 최솟값으로 자동 갱신.
         `src/database/dcat.py`에 `update_dcat_dataset()` 추가,
         `scripts/register_dataset.py --temporal-start` 옵션 추가.
         실 API로 검증 — `--temporal-start 2026-06-27` 지정 후 실제로 그 날짜부터
         720행(2카테고리×30일×12조합) 수집, `temporal_start`도 정확히 갱신됨 확인
- [x] ~~**성능 개선**: DB 커넥션 재사용~~ — **완료 (2026-07-28)**. `src/database/db.py`만
      수정 — 프로세스당 커넥션 1개를 지연 생성해 재사용, `get_conn()` 호출마다
      `SELECT 1`로 가볍게 생존 확인 후 죽어있으면 재연결(STT 처리처럼 쿼리 사이
      유휴 시간이 긴 경우 서버가 유휴 커넥션을 끊을 수 있어서 필요 — `.closed`
      속성만으로는 서버 쪽 끊김을 못 잡음). 호출부(`database/meta_*.py`,
      `pipelines/*.py`)는 인터페이스가 동일해서(`conn = get_conn(); ...; conn.close()`)
      **단 한 줄도 안 건드림** — `close()`가 실제로 닫지 않고 트랜잭션만 정리하도록
      의미만 바뀜. 실 서버로 `youtube_samsung_official`(1434개 영상) 재실행 검증 —
      기존 ~5분 → **2분 31초**로 단축, `data_registry`/S3 export 정합성 이상 없음.
      ⚠️ **멀티스레드 주의**: psycopg2 커넥션이 스레드 세이프하지 않아 이 설계는
      "프로세스=순차 실행" 전제 — Airflow가 같은 프로세스 안에서 태스크를 스레드로
      동시 실행하는 구조로 바뀌면(§6.2 실행 방식 미정) 그 전에 반드시 `psycopg2.pool`로
      마이그레이션할 것(인터페이스는 유지되므로 `db.py` 내부만 바꾸면 됨).
      KubernetesExecutor(태스크=별도 Pod)로 가면 이 문제 자체가 없음 — §6.2 착수
      시점에 실행 방식 결정하며 재검토 필요
- [x] ~~**YouTube 채널 전체 발견 + 개별 영상 큐레이션 혼합 지원**~~ — **완료
      (2026-07-28)**. "위암수술전 환자 추천영상"처럼 여러 채널에서 영상을 하나씩
      골라 만드는 큐레이션형 데이터셋은 기존 "채널 지속 모니터링" 모델로 표현이
      안 되던 문제 — `dcat_dataset.subjects`를 `{"channels":[...],"videos":[...]}`로
      확장(DB 컬럼은 이미 JSONB라 마이그레이션 불필요, 기존 3개 데이터셋의 subjects
      값만 새 형식으로 UPDATE). `youtube_collector.py`에 `fetch_specific_videos`
      추가(기존 `get_video_details`에 `filter_shorts` 옵션만 얹어 재사용 — 개별
      지정 영상은 Shorts라도 제외 안 함, 명시적 선택 존중), `youtube_pipeline.py`의
      `_fetch_remote_videos`가 채널 발견분+개별 지정분을 중복 제거해서 합침(같은
      영상이 양쪽에 다 걸릴 수 있어 news/blog와 같은 이유로 dedup 필요),
      `register_dataset.py`에 `--videos` 옵션 추가. 신규/기존 분기·삭제 감지·STT·
      SeaweedFS export 로직은 영상 출처를 안 가려서 전혀 안 건드림 — 삭제 감지도
      개별 지정 영상은 `videos.list` 직접 조회라 news/blog식 재확인 없이 기존
      "결과에 없으면 삭제" 방식 그대로 안전하게 적용됨. 단위 테스트 6건 추가,
      실 서버로 기존 채널 재실행(회귀 없음) + 채널 없이 개별 영상 2개만으로 신규
      등록·재실행(신규→기존 전환 정상 확인) 검증 완료.
- [x] ~~**SeaweedFS raw/JSON-LD 저장**~~ — 구현·검증 완료 (2026-07-27, 설계는
      [architecture/05_Object_Storage_Export.md](architecture/05_Object_Storage_Export.md)):
      `src/storage/{s3_client,raw_export,jsonld_export}.py` 신설, `src/collectors/
      youtube_transcript_collector.py`(yt-dlp+faster-whisper 자체 STT) 신설, 5개
      파이프라인 전부 통합, `meta_video.has_transcript`/`transcribed_at`
      컬럼 추가, `scripts/backfill_youtube_transcripts.py`(기존 영상 백로그 소급
      처리용) 작성. 실 서버로 `naver_news_ai`(뉴스, 1815개 raw txt + JSON-LD 1개)와
      `youtube_samsung_official`(트랜스크립트 JSON) 둘 다 검증 완료 — `data_registry.
      s3_raw_prefix`/`s3_jsonld_prefix` 정상 채워짐. 백로그(~2,076개)는 **지금 처리
      안 함**(§6.2 안전망 태스크 항목 참조 — 현재 데이터셋이 개발/테스트용이라 교체
      가능성 큼)

### 6.2 오케스트레이션 (Airflow)

- [ ] **실행 방식 결정 시 DB 커넥션 재사용 설계 재검토 필요** (2026-07-28 기록, §6.1
      성능 개선 항목 참조): `src/database/db.py`는 "프로세스=순차 실행" 전제로
      커넥션 1개를 재사용한다 — Airflow가 같은 프로세스 안에서 태스크를 스레드로
      동시 실행하는 구조(예: 특정 LocalExecutor 설정)로 가면 psycopg2 커넥션이
      스레드 세이프하지 않아 데이터가 조용히 꼬일 수 있음. **KubernetesExecutor
      (태스크=별도 Pod)라면 이 문제 자체가 없음** — 실행 방식(Helm chart, Executor
      종류) 결정하는 이 시점에 반드시 같이 확인할 것. 멀티스레드 방식으로 갈 경우
      `psycopg2.pool`로 마이그레이션(인터페이스 유지되므로 `db.py` 내부만 수정하면 됨)
- [ ] **YouTube 트랜스크립트 안전망 태스크 — 확정, Airflow 착수 시 같이 구현**
      (2026-07-28 결정, [architecture/05_Object_Storage_Export.md](architecture/05_Object_Storage_Export.md) §4.6):
      기존 백로그(2,076개, 실측 순수 연산 52~77시간)는 **지금 처리하지 않는다** —
      현재 YouTube 데이터셋 2개는 개발/테스트용이라 실제 서비스 데이터셋으로 교체될
      가능성이 커서, 지워질 수도 있는 데이터에 미리 연산을 쏟지 않기로 함(기능
      자체는 이미 이 2개로 검증 완료). 대신 주 1회 `backfill_youtube_transcripts.py
      --limit N`을 자동 실행하는 **저빈도 안전망 DAG 태스크를 Airflow 설계에 처음부터
      포함**시켜, 기존 백로그든 신규 데이터셋 등록 후 인라인 STT 실패분이든 사람 개입
      없이 걷어내도록 한다. 참고: 신규 데이터셋 등록 시 최초 수집에서 영상이 대량
      발견되면(`run()`이 전부 순차 인라인 처리하므로) 그 최초 실행 자체가 몇 시간
      단위로 길어질 수 있음 — 정상 동작이며 다른 데이터셋 태스크엔 영향 없음
- [x] ~~2-4 결정(ADR-002 갱신) 먼저 확정~~ — §2에서 이미 완료(Superseded, ADR-007)
- [x] ~~`metadata-ingestion` K8s 네임스페이스 실제 생성~~ — **완료 (2026-07-28)**,
      §1의 K8s Secret 작업 중 `RnD-analyzer01`에서 `sudo kubectl create namespace`로 생성
- [ ] Airflow 자체 K8s 배포 (Helm chart 등 방식 결정 — 별도 인프라 문서 필요,
      `docs/infrastructure/07_Airflow.md` 후보) — **Executor 종류 결정 시 위 커넥션
      재사용/안전망 태스크 항목 같이 검토**
- [ ] `dags/` 폴더 신설, source_type당 DAG 작성 (§3 — 3-레이어 구조: Scheduler/판단 태스크/실행 태스크)
- [ ] `data_registry` 조회 공통 함수(`get_due_datasets` 등) 작성

### 6.3 프론트엔드 연동 API

**⚠️ `owner_id` 컬럼은 추가됐지만 FK는 아직 없다(§3의 8번 항목, 계정 테이블 스펙 대기 중).
아래 API들은 FK 없이도 구현 가능하지만, `owner_id` 값의 유효성(존재하는 계정인지)은
당분간 애플리케이션 레벨(인증 토큰 검증)로만 보장된다는 점을 감안할 것.**

- [ ] `POST /api/datasets` 신규 데이터셋 등록 API 구현 — **소스 타입별 핸들러로 분리**
      (§4.4: video/news/blog는 발견형 핸들러, shopping/persona는 선언형 핸들러 — 등록
      시점에 `meta_*`까지 바로 쓰는 게 다름, §5.3 예시 참조)
- [ ] `PATCH /api/datasets/{id}/subjects` — 기존 데이터셋에 채널/키워드 추가 (§5.6,
      runbooks/04_Add_New_Dataset_Existing_Source.md B 경로)
- [ ] `GET /api/datasets/{id}/status` — 최초 수집 실패를 명확히 구분해서 반환 (§7.4,
      "등록 중..." 무한 스피너 방지)
- [ ] `GET /api/datasets?owner=...` — 내 데이터셋 목록 (`owner_id` 컬럼 존재하므로 구현 가능)
- [ ] `dataset_id` 채번 로직 — slug + 랜덤 접미사, `unique_violation` 시 재시도 (§7.1)
- [ ] `dataset_origin`은 요청 바디로 받지 않고 서버가 caller 권한으로 결정 (§5.7 보안 주의사항)
- [ ] 위 전체가 `docs/api/`로 정식 문서화 필요 (지금 완전히 비어있음)

---

## 7. 와이즈넛 정형(공공데이터) 저장 설계 반영 (🔄 테이블 생성 완료 · 2026-10-27 실측 갱신)

> **2026-10-16 기록.** 와이즈넛 「백엔드 설계 초안 v2」(+ 별첨 테이블정의서) 검토 완료,
> 메일로 회신 전달함. 모비젠은 **대부분 수용** + 추가 의견 몇 건만 전달. **와이즈넛과
> 협의가 확정되면** 아래 DB 작업(테이블 생성·컬럼 추가)과 규칙 변경을 함께 진행한다.
>
> 배경: data.go.kr 등 **정형(엑셀/파일) 데이터**를 플랫폼에 저장하기 위한 계층 추가.
> 우리 비정형(video/news/blog/shopping/persona)과 `source_type`이 다른 **별개 축으로
> 가산**이며, 기존 `dcat_dataset`/`dcat_provenance`/`data_registry`/`dcat_dataset_vec`
> 뼈대를 그대로 재사용한다. (원문 PDF 2종은 레포 밖 — 메일 첨부 참조)

### 7.1 신규 테이블 생성 (8종) — ✅ **DB 생성 완료 (2026-10-27 확인)**

> 8종 전부 DB에 생성돼 있으나 `sql/`에 DDL이 없어, 실제 구조를 떠서 한글 주석과 함께
> 저장소에 추가했다. 와이즈넛 DDL 수령 시 `scripts/compare_wisenut_spec.py`로 재대조한다.
> 별첨 v2에 없는 컬럼 3종이 발견됐다 — `dcat_dataset_attr.stat_name`·`spatial_unit`,
> `dcat_dataset_relation.relation_label` (와이즈넛 개정판으로 보임, 확인 필요).


- [ ] `dcat_dataset_attr` — 데이터셋 현황 메타 17항목 (DCAT 미대응 정형 고유), 1:1
- [ ] `active_meta_dataset` — 데이터셋 단위 지표 시계열 (EAV·관측값만). **정형+비정형 공용** (별첨 지표표준값 + 모비젠 비정형 코드 추가)
- [ ] `dcat_dataset_relation` — 데이터셋 간 관계. **정형+비정형 공용**
- [ ] `meta_datagokr_file` — 파일 단위 메타 + `column_names`/`column_profile` 기술통계
- [ ] `active_meta_file` — 파일/아이템 지표 시계열 (EAV·관측값만). 정형 전용 (비정형은 기존 active_meta_* wide가 그 역할)
- [ ] `meta_file_relation` — 파일·컬럼 간 관계
- [ ] `meta_datagokr_file_vec` — 파일 임베딩, 1:1
- [ ] `dcat_dataset_draft` — 표준 매핑 초안·검토 큐 + 원본 스냅샷 참조 (원본 실체는 SeaweedFS raw)

### 7.2 레지스트리 2종 신설 (모비젠 추가 제안) — ✅ **생성 완료 · 표준값 적재됨**

> `metric_registry` 11행, `relation_type_registry` 8행. 와이즈넛이 반영했다.
> ⚠️ 관계 유형 8종 중 **비정형(`applies_to=["*"]`)에 쓸 수 있는 것은 2종뿐**이다
> (`SEMANTICALLY_RELATED`, `KEYWORD_OVERLAP`). 비정형용 유형 추가는 가능하다는 회신을 받았다.


- [ ] `metric_registry` — 지표 코드 표준값 (8컬럼, `applies_to` JSONB로 적용 source_type 관리)
- [ ] `relation_type_registry` — 관계 유형 표준값 (6컬럼, `applies_to` + `scope`)
- 목적: 정형·비정형 코드가 한 테이블(`active_meta_*`, `*_relation`)에 섞여도 **범위 밖 적재·오생성 차단**. 별첨의 지표/관계 "표준값 시트"를 DB 테이블로 승격 + FK 강제. (`["*"]` = 전체 공통)

### 7.3 기존 `dcat_dataset` 컬럼 추가 (6종) + backfill — ✅ **적용 완료 (2026-10-27)**

> [sql/migration_2026_10_27_wisenut_alignment.sql](../sql/migration_2026_10_27_wisenut_alignment.sql)
> 테이블 정의서대로 **6종 전부 추가**한다(`theme` 포함).
> 분류 저장은 **`theme` 하나로 통일**하고, 용도가 겹치는 `category`(별첨에 없고 DB에만 있던
> 컬럼, 18건 전부 빈 배열)는 **미사용 처리**한다. 우리가 만든 컬럼이 아니므로 단독 삭제하지
> 않고 와이즈넛 확인 후 제거한다.
> `dataset_id` URN 전환은 [database/dataset_id_urn_migration.md](database/dataset_id_urn_migration.md) 참조.


- [ ] 컬럼 추가: `source`, `publisher_code`, `theme`(jsonb,GIN), `external_ids`(jsonb,GIN), `party`, `visibility`
- [ ] backfill: 기존 18개 데이터셋 — 현 `publisher`의 원천값(Naver/YouTube)을 `source`로 이전, `publisher`는 실제 제공기관으로 재설정; `visibility` NOT NULL 기본값(PUBLIC/ORG) 지정
- 전제: `dataset_id`/`file_id`는 **TEXT 자연키 유지**(대리키 없음) — 3시스템(모비젠·케이웨어·포털) 참조 경로 일치. 단 **URN 불변·병합 시 survivor ID 유지·생성규칙 합의** 조건 (회신에 명시함)

### 7.4 규칙/방식 변경

- [ ] **이력 지표 delta**: 신규 정형(active_meta_dataset/file)은 **관측값만 저장 + 뷰(LAG) 계산**. 기존 비정형(active_meta_video/news/blog)은 현재 delta 저장 유지 → 리스크 낮아 **후속 전환**(여유 시 delta 컬럼 제거 + 뷰 교체). `v_*_latest`(최신값+증감) 인터페이스는 양쪽 동일 유지. (근거: 누락·백필 시 저장 delta가 틀어짐)
- [ ] **지표 표현 EAV**: `metric_code` EAV는 신규 정형에만. 기존 비정형은 타입 컬럼(wide) 유지. shopping/persona 다차원·blog `reaction_breakdown`은 전용 테이블 유지(평면 EAV 부적합)
- [ ] **재수집 시점 분리**: `next_registration_date`(원천 공시, dcat_dataset_attr) vs `next_collect_at`(스케줄러, data_registry). 비정형은 `next_registration_date` NULL. `next_collect_at` 산정 로직을 "예정일 우선 → `accrual_periodicity` → 주간"으로 보강
- [ ] **컬럼 관계 산출**: 데이터셋 관계로 후보 쌍을 좁힌 뒤 종속 산출(와이즈넛 알고리즘 — 조합 폭발·도메인 교차 오탐 방지). 우리 스키마 조치 없음
- [ ] **임베딩**: 1:1 `*_vec` 분리 유지 (이미 우리 방식)

### 7.5 모비젠이 회신에 전달한 추가 의견

- `metadata_entry`(미분류 EAV) 재사용 **재검토 요청** — 원본은 이미 SeaweedFS raw + JSON-LD + `dcat_dataset_draft.raw_storage_key`에 있음. 필요 시 `raw_metadata jsonb`로 갈음(별도 EAV 재적재 실익 재검토)
- 위 7.2 레지스트리 + `applies_to` 제안
- active_meta_dataset/dcat_dataset_relation 정형·비정형 공용 사용

### 7.6 레거시 정리 (이 작업과 함께)

- Model B(`catalog_entry`·`metadata_entry`·`column_relation`) — 예전 공공데이터 카탈로그 시도의 잔재, **폐기 예정**. 와이즈넛이 `metadata_entry` 재사용 안 하기로 확정되면 정리
- `ad_keyword_naver_category_map` — **2026-10-15 삭제 완료**(코드 참조 0건·FK/뷰 의존 없음, 고아 테이블)
- `users`(빈 테이블, 임시) — 계정 통합은 타 팀 협의 중(§3-8과 연결), `owner_id` FK는 그 후

### 7.7 문서 갱신

- [ ] `docs/database/datagokr_schema.md`에 신규 테이블/컬럼/레지스트리 반영, ERD 갱신
- [ ] 필요 시 ADR 추가(정형 저장 설계 채택, 관측값-온리 전환 등)

### 7.8 (예정) 정형데이터 오브젝트 저장소

- **배경**: 현재 오브젝트 스토리지(SeaweedFS `raw/` · `jsonld/`)는 영상·뉴스·블로그·인사이트 등 **발견형/선언형 소스** 중심. 공공데이터포털(data.go.kr) 등 **정형(엑셀·CSV·파일) 데이터 원본**을 담을 저장 구획이 아직 없음.
- **방향(예정)**: 기존 `raw/`/`jsonld/` 패턴을 따라 **정형 데이터용 저장 경로·형식을 신설**. (예: `raw/structured/{dataset_id}/...` 원본 파일 보관 + 데이터셋 단위 JSON-LD/카탈로그 연계) — 세부 경로·네이밍·포맷은 **와이즈넛 정형 저장 설계(§7.1~7.4)와 함께 확정 예정**.
- **연계**: `active_meta_dataset`/`active_meta_file`(지표 EAV), `data_registry`의 `s3_*_prefix` 기록 규칙을 정형에도 동일 적용 검토.
- **상태**: ⏳ **예정** — 현재는 기록·문서화만. 저장 형식 명세 문서([architecture/06_Object_Storage_Format_Spec.md](architecture/06_Object_Storage_Format_Spec.md) §7)에 "예정" 섹션으로 반영해 둠.

---

## 8. 연구개발계획서 기반 최종 완성 로드맵 (2026-10-27 수립)

> **목적**: 협약 계획서(RS-2024-00340834)의 **주관기관 1~4차년도 전 과업**을 구현 상태와 대조하고,
> **바로 착수 가능한 수준**의 작업 단위·구현 방법·완료 기준을 고정한다.
> 1·2차년도 미이행분이 다수이므로 **연차 순서가 아닌 의존성 순서**로 진행한다.
> ※ "근거"는 계획서 원문, **"구현"은 본 저장소 기준 제안**(착수 시 조정 가능).
>
> 🔧 **기술 선정 근거·구현 상세·제외 항목·라이선스 점검은**
> **[development/04_Implementation_Methods.md](development/04_Implementation_Methods.md)** 에 분리 기록한다.
> 이 문서는 **무엇을 언제 누가**, 저 문서는 **어떻게**를 다룬다. 작업 ID(A1~D2)는 양쪽이 동일하다.

### 8.0 기본 원칙 — 최소선(러프) 우선, 이후 고도화

과제 요구사항을 **100% 만족시키기 어려운 항목은 "걸치는 수준"으로 먼저 구현**하고,
여력이 생기면 목표선으로 끌어올린다. 평가·점검 관점에서 중요한 것은 다음 두 가지다.

1. **해당 기능이 실제로 동작한다는 증거**(실행 가능한 코드 + 산출 데이터 + 재현 절차)
2. **한계의 명시**(무엇을 어디까지 했고, 무엇은 범위 밖인지 문서화)

따라서 각 작업은 **🟩 최소선(러프)** 과 **🟦 목표선** 을 나눠 적는다.
일정이 부족하면 **모든 작업을 최소선까지 먼저 채우는 것**이 일부만 완벽히 하는 것보다 낫다.

### 8.1 선행 과제 (P0) — 신규 개발보다 먼저

전수 검증 과정에서 드러난 **기존 결함·공백 5건**. 비용 대비 효과가 가장 크고,
이걸 두고 신규 기능을 쌓으면 뒤에서 전부 흔들린다. 상세는
[04_Implementation_Methods.md §1](development/04_Implementation_Methods.md).

| # | 내용 | 성격 | 영향 |
|---|---|---|---|
| **P0-1** | **임베딩 입력이 128토큰에서 잘린다.** `content[:500]`으로 자른 뒤 모델이 다시 128토큰(한국어 약 200~300자)에서 절단 → 뉴스 본문의 10% 내외만 검색에 반영 | 🔴 기존 결함 | C1·C2 전체 |
| **P0-2** | **YouTube 자막이 수집만 되고 아무도 쓰지 않는다.** S3에만 있고 DB에는 플래그뿐, 임베딩도 제목·설명·태그만 사용 | 🔴 미활용 자산 | B1·C1·A2 |
| **P0-3** | ~~**Dockerfile 부재**~~ — 작성 완료 (2026-11-02, [docker/Dockerfile](../docker/Dockerfile)). 모델을 이미지에 굽고 `HF_HUB_OFFLINE=1`로 폐쇄망 다운로드 리스크 제거. ⚠️ **빌드 미검증** — 로컬에 Docker 데몬이 없어 `docker build`를 못 돌렸다 | 🟡 작성됨·미빌드 | C3·C4 |
| ~~P0-4~~ | **외부 LLM API — 사용 불가로 결정** ([ADR-013](adr/013_No_External_LLM_API.md)) | ✅ 해소 | 로컬 추론 전용. 추출 요약·공기어 확장·사람 라벨로 대체 경로 확정 |
| ~~P0-5~~ | **메타데이터 품질 실측** — 완료 (2026-11-02, [database/metadata_quality_probe.md](database/metadata_quality_probe.md)) | ✅ 측정 끝 | 아래 P0-7 발견 |
| **P0-7** | **수집이 멈춰 있다.** 18개 데이터셋이 `next_collect_at`을 2~3일 경과. K8s에 CronJob이 없고 Airflow 미도입이라 사람이 직접 쳐야만 돈다. 그 결과 발견형 3종(video/news/blog)의 `active_meta_*` 관측일이 **1일**뿐이라 **B2 시계열 공변동이 정의되지 않는다** | 🟡 도구 작성됨 | B2 · C4 · 모든 시계열 분석 |
| | → [scripts/scheduler_tick.py](../scripts/scheduler_tick.py) + [k8s/cronjobs/collector-tick-cronjob.yaml](../k8s/cronjobs/collector-tick-cronjob.yaml) 작성 완료. **아직 아무것도 돌리지 않았다** — 마이그레이션 적용이 선행이고(수집이 `token_text`를 쓴다), CronJob은 P0-3 이미지 빌드가 선행이다 | | |
| **P0-6** | **검색 평가셋** — 하네스·known-item 라벨 완료 (2026-11-04). **topical 라벨은 사람 판정 대기** | 🟡 절반 | C1 완료기준·C2·C6 |
| | → `src/eval/`, `scripts/eval_search.py`, `eval/search/video/`. 질의 50건(known-item 30 자동 + topical 20 설계). 사람 판정 후보 **393건** 풀링 완료 | | |
| | → **즉시 성과**: RRF `k` 스윕의 답이 **"k로는 안 된다"**로 나왔다. k를 60→30→20→10으로 낮춰도 `recall@1`이 전부 **0.7333**으로 동일하다. k는 깊이만 바꾸고 1위를 뺏기는 것은 못 막는다 | | |

> P0-4는 2026-10-27 **사용 불가로 결정**되어 ADR-013으로 대체 경로가 확정되었다.
> P0-1·P0-2는 **새 기능이 아니라 이미 만든 것을 제대로 동작시키는 일**이라 우선순위가 높다.

### 8.2 최종 완성품 (계획서 End Product) 대비 현황

| # | 산출 소프트웨어 | 현재 | 담당 작업 |
|---|---|---|---|
| 1 | 액티브 메타데이터 **저장/관리** SW | 🟡 스키마·저장 구현, 관리 기능 부족 | A1·A2·D1 |
| 2 | **AI 기반 데이터 관계 생성·분석** SW | 🔴 미착수 | B1·B2·B3·B4 |
| 3 | 액티브 메타데이터 **검색·탐색** SW | 🟡 벡터검색만 | C1·C2·C6 |
| 4 | **데이터 동적 변화 분석·자동 반영** SW | 🔴 미착수 | C3·C4 |
| 5 | **데이터 패키징** SW | 🔴 미착수 | C5 |
| — | **써드파티 데이터 활용 통합 플랫폼** | 🔴 API·운영기능 없음 | C6·D1 |

### 8.3 연차별 주관 과업 ↔ 구현 상태 (전수)

| 연차 | 주관(모비젠) 과업 | 상태 | 작업 |
|---|---|---|---|
| 1차 | ① 비정형 액티브 메타데이터 **처리** | 🟡 STT만 | A2 |
| 1차 | ② 데이터 **특징 추출·분석** 〔SW모듈 명시: 모비젠〕 | 🔴 | **B1** |
| 1차 | ② **패턴 모델링 기반 관계 분석** | 🔴 | **B2** |
| 1차 | ③ 액티브 메타데이터 기반 **검색** 〔전처리 모듈: 모비젠〕 | 🟡 벡터만 | **C1** |
| 2차 | ① 비정형 액티브 메타데이터 **수집** 〔모듈: 모비젠〕 | 🟢 | — |
| 2차 | ② **네트워크 생성·관계 분석** 〔모듈: 모비젠〕 | 🔴 | **B3** |
| 2차 | ③ **활용 목적 기반 자동 탐색** 〔검색·탐색 모듈: 모비젠〕 | 🔴 | **C2** |
| 2차 | ③ **템플릿 기반 파이프라인 구성** 〔모듈: 모비젠〕 | 🔴 | **C3** |
| 3차 | ① **확장 가능한 수집** | 🔴 | **A1** |
| 3차 | ③ **탐색 확장·통합 구성** | 🔴 | **C6** |
| 3차 | ③ **신뢰성 보장 패키징** | 🔴 | **C5** |
| 4차 | ③ **동적 변화 파이프라인** 〔모듈: 모비젠〕 | 🔴 | **C4** |
| 4차 | ③ **능동형 패키징** 〔모듈: 모비젠〕 | 🔴 | C5 |
| 4차 | ③ **외부 모듈 연계** | 🔴 | **C7** |
| 1~4차 | ⑤ 실증·시범서비스 | 🟡 | D2 |

🟢 완료 · 🟡 부분 · 🔴 미착수

---

### A. 메타데이터 생성·처리

#### A1. 수집 어댑터화 〔3차 · 모비젠 단독〕 — 🟩 **최소선 완료 (2026-11-04, C3에서 적재층 보완)**
- **현재**: `src/collectors/*.py` 5종 독립 구현 → 신규 소스마다 수집기·파이프라인·DB헬퍼 신규 작성.
- 🟩 **최소선**: 공통 `BaseCollector` + **범용 REST/JSON 어댑터 1종** + 소스 스펙(YAML)으로 **신규 소스 1종** 수집 성공 ✅
  - `src/collectors/base.py`(계약), `src/collectors/adapters/rest_json.py`(어댑터),
    `configs/sources/{naver_news,youtube_search}.yaml`. 테스트 26건
  - **검증은 기존 수집기와 대조로 했다** — 같은 질의로 네이버 뉴스 **300건 완전 일치**
    (겹침 300 / 어댑터만 0 / 기존만 0). 상상한 추상화가 아니라 실물에 맞춘 추상화다
  - **완료 기준 충족**: `youtube_search.yaml`을 추가하자 **코드 수정 없이** cursor 페이징
    150건이 수집됐다. 네이버는 offset(`start=1,101,201`), 유튜브는 cursor(`pageToken`)로
    방식이 다르다
  - ⚠️ **`detect_removed` 기본값이 "판정 불가"다.** 2026-07-28 뉴스 사고(부재 146건 중
    91건이 생존)를 새 어댑터가 반복하지 않도록, 삭제 감지는 스펙에 명시해야 켜진다.
    검색형 원천은 `verify_each`가 강제된다
  - 자격증명은 **환경변수 이름만** 스펙에 적는다. 평문이 들어가면 테스트가 파일·위치를
    짚어 잡는다
- 🟦 **목표선**: 기존 5종 전부 어댑터 이관 + CSV/엑셀 어댑터 추가 + 증분 커서 공통화.
- **구현**
  - `src/collectors/base.py` — `fetch(cursor) -> list[raw]`, `normalize(raw) -> dict`, `detect_removed(ids) -> list`
  - `src/collectors/adapters/rest_json.py` — 엔드포인트·페이징·필드매핑을 스펙에서 읽어 동작
  - `configs/sources/<source>.yaml` — `endpoint / auth_env / paging / fields / id_field / cursor_field / rate_limit`
  - 인증은 **환경변수 키 이름만** 스펙에 기록(값 금지)
- **완료 기준**: 코드 수정 없이 YAML 추가만으로 신규 소스 수집 → `meta_*`·`data_registry` 적재 확인
  → ✅ **충족 (2026-11-04, C3에서 닫음).** 어댑터가 수집한 60건이 `meta_news`에
  적재되고 임베딩까지 됐다. `scripts/run_pipeline.py naver_news_adapter`
  → 아래는 C3 이전의 기록이다.
  → 🟡 (이전) 검증한 것은 **fetch·normalize까지**였다 —
  `youtube_search.yaml`로 150건을 읽고 정규화했고, 네이버 뉴스는 기존 수집기와
  300건 완전 일치했다. 그러나 **적재는 하지 않았다.** 어댑터를 거쳐 `meta_*`·
  `data_registry`에 들어간 행은 **0건**이다.
  → 남은 것은 "정규화된 행을 원천별 `meta_*` 테이블에 쓰는 층"이고, 그게 **C3**다.
  원천마다 테이블 스키마가 달라 `normalize` 계약만으로는 부족하다 — C3의
  템플릿 러너가 그 매핑을 맡는다.
- **의존**: 없음 (최우선 착수 가능)

#### A2. AI 생성 메타데이터 〔1·2차 미이행분 · 모비젠〕 — 🟩 **최소선 완료 (2026-11-04)**
- **현재**: STT + **추출 요약·키워드 적재 완료**. VLM 미구현.
- 🟩 **최소선**: **1개 소스(YouTube)**에 대해 **요약·키워드 2개 필드**만 생성·적재 ✅
  - `sql/meta_video_ai.sql`, `src/ai_meta/{extractive,runner}.py`,
    `scripts/generate_ai_meta.py`. 테스트 22건
  - **1개 데이터셋이 아니라 영상 전량 1,554건** 처리 — 생성 1,411 · 건너뜀 143 · **실패 0**
  - 완료 기준의 "검색 결과에 노출"도 충족 — `search_demo.py --ai`
  - **생성 요약이 아니라 추출 요약**이다(ADR-013). 원문에서 문장을 고르기만 하므로
    hallucination이 없고, 테스트가 "요약의 모든 문장이 원문에 있다"를 기계적으로 건다
  - B1과 단위가 다르다 — B1은 데이터셋(IDF 코퍼스 25개), A2는 **아이템**(수백~수천 건).
    IDF 해상도가 훨씬 세밀하다
  - **키워드는 명사만 쓴다.** 실측에서 동사 어간(`짧`·`보`·`느끼`)이 상위에 올랐는데,
    **df가 낮아서**(같 6.9%, 느끼 4.2%) IDF가 오히려 밀어 올린 것이었다 —
    문서빈도 상한으로는 못 잡고 품사로 걸러야 했다. 영어 기능어(`the`·`at`)도 같이 거른다
  - ⚠️ **입력 품질이 상한이다.** 자막 STT가 `항문`을 `학문`으로 듣는 등 오인식이
    그대로 요약에 들어간다(faster-whisper small). 모델 교체는 목표선
- 🟦 **목표선**: §5 전체 필드(개체명·분류·감성 + 썸네일 VLM 4종), 전 소스 확대.
- **구현**
  - `sql/meta_video_ai.sql` — `meta_id FK, ai_summary TEXT, ai_keywords TEXT[], model TEXT, generated_at`
  - `src/ai_meta/runner.py` — 입력(트랜스크립트/본문) → **C7 어댑터**로 모델 호출 → INSERT
  - 실패 시 레코드 스킵 + 재처리 대상 플래그(완전 실패로 파이프라인 중단 금지)
- **완료 기준**: 1개 데이터셋 전량에 AI 메타 생성, 검색 결과에 노출
- **의존**: C7(어댑터) — 최소선은 C7 없이 직접 호출로 시작해도 무방

#### A3. 정형 데이터 저장 〔협업 · §7〕
- 🟩 **최소선**: 정형 파일(CSV/엑셀) 1건을 **기존 DCAT 구조에 얹어** 수집·저장·검색까지 통과시킨다(전용 테이블 없이).
- 🟦 **목표선**: §7.1~7.4 와이즈넛 합의 스키마 + §7.8 정형 오브젝트 저장 경로 정식 반영.
- **의존**: A1(어댑터), 와이즈넛 회신

---

### B. 특징·관계 분석 — **1·2차년도 미이행 핵심**

#### B1. 데이터 특징 추출·분석 〔1차 미이행 · SW모듈 귀속: 모비젠〕 — 🟩 **최소선 완료 (2026-11-02)**
- **근거**: "액티브 메타데이터 기반 데이터 특징 추출 및 분석 기술" / 1차 SW 모듈 "데이터 특징 추출 및 분석 모듈(모비젠)"
- 🟩 **최소선**: 데이터셋 단위로 **기술통계 + 텍스트 상위 키워드**를 산출해 저장. 컬럼 단위·상관분석은 생략 가능. ✅
  - `sql/meta_feature.sql` (EAV + JSONB + GIN), `src/analysis/features/{text,stats,extract,sources}.py`,
    `scripts/extract_features.py`. 데이터셋 25개 · 특징 **155행** 적재 완료
  - 토큰은 ADR-010의 `token_text`를 **재사용**한다 — 따로 만들면 검색 채널과 어휘가 어긋난다
  - 요약은 **추출식**(상위 키워드가 조밀한 청크 선택). ADR-013이 외부 LLM을 금지했다
  - `MAX_DF_RATIO=0.5`는 **실측으로 골랐다** — 0.8/0.6은 `있·하·되`가 상위에 남고,
    0.4는 주제어(`전기`·`충전`·`배터리`)를 잃는다. 별도 불용어 사전 불필요
  - **효과**: 등록 키워드 대비 엣지 7.3%→**14.0%**, 고립 노드 10/25→**1/25**, 자카드 해상도 4종→17종
  - ⚠️ 컬럼 단위 통계(`tabular.py`)는 **제외** — 대상 `meta_datagokr_file`이 0건이다(정형 미수집).
    적재되면 `scope='column'`으로 같은 테이블에 들어간다
- 🟦 **목표선**: 컬럼 단위 통계·카디널리티·결측률, 상관(피어슨/스피어만), 시계열 특성, 토픽 모델링.
- 🟦 **목표선**: 컬럼 단위 통계·카디널리티·결측률, 상관(피어슨/스피어만), 시계열 특성, 토픽 모델링.
- **구현**
  - `src/analysis/features/tabular.py` — pandas `describe()`, 결측률, 고유값 수
  - `src/analysis/features/text.py` — scikit-learn TF-IDF 상위 N 키워드(한국어는 기존 형태소 처리 재사용)
  - 저장: **신규 테이블 `meta_feature`** — `dataset_id, scope('dataset'|'column'), target, feature_name, value JSONB, computed_at`
  - 실행: 수집 파이프라인 후단 호출 + `scripts/extract_features.py` 수동 실행 경로
- **완료 기준**: 전체 데이터셋에 특징 메타가 쌓이고, 값으로 필터 조회 가능
- **의존**: 없음

#### B2. 패턴 모델링 기반 관계 분석 〔1차 미이행 · 모비젠〕 — 🟩 **최소선 완료 (2026-11-03)**
- **근거**: "데이터 패턴 모델링 기반 데이터 관계 분석 기술"
- ⚠️ **P0-5 실측 결과 최소선 구성을 바꿔야 한다** ([database/metadata_quality_probe.md](database/metadata_quality_probe.md)):
  **등록 키워드로는 엣지가 안 선다** — 평균 2~3개뿐이라 300쌍 중 22쌍(7.3%)만 공유하고
  자카드 값이 `0/⅓/½/1` 같은 거친 이산값이 된다. 입력을 **B1이 아이템에서 집계한
  특징**으로 바꿔야 한다. → ✅ **B1 완료, 엣지 14.0%·고립 1/25로 개선**
- ⚠️ **비교 방식도 바꿔야 한다** ([ADR-019](adr/019_Dataset_Profile_Vectors.md), Proposed):
  B1 이후에도 자카드가 관계를 **거꾸로 매긴다** — `패션의류 트렌드 ↔ 패션 전체 트렌드`가
  0.000인데 `전기차 블로그 ↔ 캠핑 블로그`가 0.200이다(일반어 공유). 그리고 청크 최대
  유사도는 300쌍이 전부 0.89~0.99라 임계값을 못 쓴다. → **`vec_role`에 `profile` 역할 추가
  + `keyword` 입력을 B1 집계로 교체 + 상위 K 방식** (새 테이블 없음). 시계열 공변동은 발견형 3종의 관측일이 1일이라 **P0-7(수집 재개)
  없이는 불가능**하다.
- 🟩 **최소선**: **데이터셋 간 유사도 2종**으로 후보 관계와 점수 산출 ✅ **완료 (2026-11-03)**
  - `src/analysis/relations/{similarity,store}.py`, `scripts/build_relations.py`. 테스트 19건
  - **자카드 대신 두 축 모두 임베딩**을 쓴다(ADR-019). 실측: `KEYWORD_OVERLAP` 125건 중
    **58건(46%)이 자카드 0**이라 별첨대로 했으면 엣지 절반이 안 섰다.
    `패션의류 검색 트렌드 ↔ 패션의류 페르소나`는 자카드 0인데 코사인 **0.9797**이다
  - **고정 임계값 대신 상위 K**(기본 5). 300쌍이 전부 0.8922~0.9921에 뭉쳐 어떤 값도
    전부 연결하거나 전부 끊는다(ADR-018과 같은 결론)
  - `evidence`에 축·코사인·공유 키워드·자카드를 남긴다 — **왜 묶였는지 보인다.**
    로봇·바이오 뉴스가 `기업 기자 매출 분기` 같은 일반어로 묶이는 것도 여기서 드러난다
  - 적재 250건(두 축 각 125건), **고립 노드 0/25** (등록 키워드 기준으로는 10/25였다)
  - ⚠️ **벡터를 저장하지 않고 그때그때 만든다.** 영속화 위치는 D-2(와이즈넛 회신) 대기.
    확정되면 벡터 출처만 바꾸면 되고 비교 로직은 그대로다
- 🟦 **목표선**: 계층적 클러스터링, 연관규칙(FP-Growth), 컬럼명/타입 기반 조인 후보 탐지.
- **구현**
  - `src/analysis/relations/similarity.py` — B1 키워드 자카드 + **기존 `dcat_dataset_vec` 코사인**(pgvector 재사용)
  - 출력: `(src, dst, relation_type, score, evidence JSONB)` 리스트 → B3로 전달
  - 임계값·상위 K는 설정값으로(과도한 엣지 생성 방지)
- **완료 기준**: 임의 데이터셋의 상위 관련 데이터셋이 **근거 지표와 함께** 재현 가능하게 산출
- **의존**: B1

#### B3. 네트워크(지식그래프) 생성 〔2차 미이행 · SW모듈 귀속: 모비젠〕 — 🟩 **최소선 완료 (2026-11-03)**
- **근거**: "액티브 메타데이터 기반 네트워크 생성 및 관계 분석 기술" / 2차 SW 모듈 "네트워크 생성 및 분석 모듈(모비젠)"
- 🟩 **최소선**: 관계 테이블 + **1-hop 이웃 조회** ✅ **완료 (2026-11-03)**
  - 테이블은 와이즈넛 합의본(`dcat_dataset_relation`)을 그대로 쓴다 — 별도 신설하지 않았다
  - 조회는 `src/analysis/relations/store.py::neighbours()`.
    **상위 K가 방향을 갖고 저장**되므로(A의 top-5와 B의 top-5는 다르다) 단순 SELECT로 끝난다
  - `scripts/build_relations.py --show <id>`로 확인 가능
  - 다중 홉(재귀 CTE)·군집 탐지는 목표선
- 🟦 **목표선**: 다중 홉 경로·군집 탐지, 가중치 정규화, 시각화 연계(케이웨어 담당분과 접점).
- **구현**
  - ~~신규 테이블~~ — **와이즈넛 합의본이 이미 있다.** 컬럼명이 제안과 다르다:
    `source_dataset_id`/`target_dataset_id`, `score REAL`, `method('rule'|'embedding'|'llm'|'gnn')`,
    `status('PENDING'|'APPROVED'|'REJECTED')`, `evidence JSONB`. 그대로 쓴다
  - 적재: B2 산출 upsert(동일 쌍은 최신 점수로 갱신)
  - 조회: `src/analysis/graph.py` — 이웃 조회는 단순 SELECT, 다중 홉은 **재귀 CTE**
  - **그래프DB는 도입하지 않는다**(규모가 커지면 ADR로 재검토)
- **완료 기준**: "이 데이터셋과 연관된 데이터셋" 질의가 DB만으로 동작
- **의존**: B2

#### B4. 와이즈넛 관계 모델 결과 수용 〔공동 인터페이스〕
- **근거**: 와이즈넛 ②(의미 이해·연관성 분석·LM/GNN 관계 생성) 산출을 플랫폼이 저장·활용
- 🟩 **최소선**: **JSON 교환 규격**(src/dst/type/score/evidence/model/version) 합의 + 적재 CLI 1개.
- 🟦 **목표선**: 배치·증분 동기화, 모델 버전별 비교, `origin='model'` 결과와 규칙 기반 결과의 혼합 랭킹.
- **구현**: `scripts/import_relations.py` → `dcat_dataset_relation`에 `origin='model'`로 적재(규칙 기반과 공존)
- **완료 기준**: 외부 모델 산출 관계가 동일 스키마로 적재·조회
- **의존**: B3

---

### C. 탐색·패키징

#### C1. 검색 고도화 〔1차 보강 · 모비젠〕 — 🟩 **최소선 완료 (2026-10-30)**
- 🟩 **최소선**: **키워드(Postgres full-text) + 벡터** 결과를 **RRF**로 합치는 하이브리드 검색 1종. ✅
- 🟦 **목표선**: 동의어/유의어 사전, 필드 가중치, 필터(소스·기간·특징), 재현율 측정 체계. ⏳
- **구현** — 설계 근거·어긋난 점은 [ADR-010 §구현](adr/010_Korean_Fulltext_Search.md), 운영은
  [database/hybrid_search.md](database/hybrid_search.md)
  - [x] `src/search/tokenize.py` — Kiwi 형태소 토큰화(조사·어미 제거). 어절 색인 시
        문서빈도가 **65배** 틀어지는 문제를 제거(`대역폭을` 0.23% vs `대역폭` 15.04%)
  - [x] `src/search/hybrid.py` — tsvector + pgvector → RRF, **SQL 단일 CTE**
  - [x] `sql/migration_2026_10_30_keyword_channel.sql` — `*_vec` 4종에 토큰·tsv·GIN
  - [x] `scripts/backfill_tokens.py` — 기존 청크 163,407건 토큰 채우기
  - [x] `scripts/search_demo.py --mode hybrid|vector --why` — 채널별 순위·판정 근거 노출
  - [ ] 동의어 `synonym(term, alt)` 테이블 — 목표선
  - [ ] 필드 가중치(`setweight`) — 청크에 출처 필드 기록이 선행돼야 함(ADR-010 §구현)
  - [ ] 서비스 계층 승격 — C6에서 API로 노출할 때
- **완료 기준**: 동일 질의에서 단일 방식 대비 상위 결과 품질 개선을 **수치로 제시**
  → 🟡 **부분 충족 (2026-11-04).** known-item 30건으로 잰 결과 회귀는 해소됐다 —
  키워드 점수를 IDF 합으로 바꿔 `recall@1` 0.7333 → **0.9667**(기준선 1.0).
  다만 known-item은 dense retrieval에 유리한 조건이라 **"전반적 개선"의 근거는
  아직 아니다.** topical 라벨(사람 판정 393건) 뒤에 완료 판정한다.
  → (이전 기록) **순위 정답지가 없어 Recall@k를 만들 수 없다.** ADR-018의 19건은 "답이 있는가"의 불리언일 뿐이고,
  그 크기의 평가셋으로 얻은 분리는 신뢰할 수 없다는 것도 ADR-018이 경고한 바다.
  **검색 평가셋 확보가 선행 과제**(아래 P0-6).
  → ⚠️ 더 나아가 **질의 1건에서 회귀가 측정됐다** — `ts_rank_cd`가 IDF를 쓰지 않아
  고빈도어 밀집 문서가 희귀어를 담은 정답을 밀어낸다. 구조적 문제라 튜닝으로
  덮을 수 없고, 처방 선택에도 평가셋이 필요하다
  ([database/hybrid_search.md §6](database/hybrid_search.md)).
- **의존**: 없음

#### C2. 활용 목적 기반 자동 탐색·추천 〔2차 미이행 · 모비젠〕 — 🟩 **최소선 완료 (2026-11-04)**
- 🟩 **최소선**: 자연어 목적 → 임베딩 검색 → **B3 1-hop 확장**으로 "관련 데이터셋 묶음" 반환 ✅
  - `src/search/discovery.py`, `GET /v1/discover`. 테스트 15건
  - **점수를 더하지 않고 순위를 쓴다.** 검색 RRF(~0.03)와 관계 코사인(~0.9)은 단위가
    달라 그냥 더하면 관계가 전부를 압도한다 — ADR-018·ADR-010에서 두 번 겪은 함정이다
  - **씨앗 순위를 이웃 점수에 더한다.** 1위 씨앗의 이웃과 5위 씨앗의 이웃은 믿을 만한
    정도가 다른데 이웃 순위만 보면 둘이 같아진다
  - ⚠️ **실측에서 걸린 것**: 경로를 선형으로 더했더니 관계 기여가 검색 기여의 **3배**가
    됐다. 그러면 "목적에 맞는 것"이 아니라 **"많이 연결된 것"**이 1등이 되어 사용자
    의도가 그래프 구조에 밀린다. 경로 순번에 기하 감쇠(`HOP_DECAY^i`)를 걸어 합이
    수렴하게 했다 — 연결이 많을수록 올라가되 한 건의 검색 기여를 크게 넘지 못한다
  - 완료 기준의 "근거 제시" 충족 — 항목마다 `paths`에 **어떻게 도달했는지**가 실린다
    (직접 검색 몇 위 / 무엇을 통해 어떤 관계로, 공유 키워드 포함)
- ⚠️ **품질 상한이 카탈로그 검색에 묶여 있다.** `dcat_dataset_vec`는 **등록 텍스트**
  (제목+설명+키워드)를 임베딩하는데, 그 설명이 평균 24~36자다(P0-5). B1이 만든
  `top_keywords`·`representative_text`를 쓰면 씨앗 품질이 올라가지만 그건
  `vec_role='profile'`(ADR-019)이고 **D-2 와이즈넛 회신 대기**다.
- 🟦 **목표선**: 도메인 분류 기반 추천, 사용 이력(클릭·조회) 반영, 묶음 구성 근거 설명.
- **구현**: `src/search/discovery.py` — 후보 검색 → 관계 확장 → 중복 제거·랭킹 → 근거(점수·관계유형) 동봉
- **완료 기준**: 목적 질의 1건으로 데이터셋 묶음 + 근거 제시
- **의존**: C1, B3

#### C3. 템플릿 기반 파이프라인 구성 〔2차 미이행 · SW모듈 귀속: 모비젠〕 — 🟩 **최소선 완료 (2026-11-04)**
- 🟩 **최소선**: **고정 4단계 템플릿**으로 선언하고 A1 소스 스펙을 주입해 실행하는 러너 ✅
  - `src/pipeline_engine/{steps,runner}.py`, `configs/pipelines/naver_news_adapter.yaml`,
    `scripts/run_pipeline.py`. 테스트 20건
  - **A1의 미완성분이 여기서 닫혔다** — 어댑터가 수집한 60건이 실제로 `meta_news`에
    적재되고 임베딩까지 됐다(청크 220개). A1 완료 기준의 "`meta_*` 적재 확인" 충족
  - **단계 순서를 스펙이 바꾸지 못한다.** 스펙에 거꾸로 적어도 고정 순서로 돈다 —
    normalize 없이 store하면 원천 모양이 들어가고, store 없이 postprocess하면
    빈 데이터셋을 임베딩한다
  - **스펙의 `columns`에 적힌 것만 쓴다.** 원천이 필드를 늘려도 없는 컬럼에 쓰려다
    실패하거나 엉뚱한 컬럼에 들어가지 않는다
  - `UNIQUE(dataset_id, 고유키)` + `ON CONFLICT`로 멱등하다. 손으로 쓴 파이프라인과
    같은 테이블을 써도 중복이 쌓이지 않는다(재실행 검증: 중복 0건)
  - ⚠️ **실측에서 걸린 것**: 어댑터가 `<b>` 태그와 HTML 엔티티를 안 벗겨 **28건이
    오염**됐다. 네이버 검색 API는 질의어를 강조해 돌려준다. 손으로 쓴 수집기에는
    있던 처리가 어댑터에 없었다 — 기본으로 켜고 끄려면 스펙에 명시하게 했다
- 🟦 **목표선**: 단계 조합 자유화, 조건 분기, 코드↔설정 양방향 변환.
- **구현**
  - `configs/pipelines/<dataset>.yaml` — `source_spec, steps[], schedule`
  - `src/pipeline_engine/runner.py` — 스펙 로드 → 단계 순차 실행 → 결과·오류 기록
  - 기존 `src/pipelines/*.py`는 당분간 **공존**(점진 이관)
- **완료 기준**: 소스 스펙만으로 파이프라인 생성·실행
- **의존**: A1

#### C4. 동적 변화 파이프라인 자동 구성 〔4차 · SW모듈 귀속: 모비젠〕 — 🟨 **코드 완료 · DDL 미적용 (2026-11-04)**
- 🟩 **최소선**: **Airflow 없이** `next_collect_at` 폴링 러너(cron/K8s CronJob) + **스키마 드리프트 감지**(수집 필드 집합 해시 비교 → 변경 시 메타 갱신·로그·플래그).
  - 폴링 러너 ✅ (2026-11-02) / 드리프트 감지 ✅ 코드·테스트 (2026-11-04, 테스트 29건)
  - ⏸ **`sql/migration_2026_11_04_source_schema_drift.sql` 미적용** — `data_registry`에
    `source_schema_*` 4컬럼을 더하는 DDL이다. 적용 전까지 감지는 돌지만 **기록이 안 되고**,
    `load_previous`가 없는 컬럼을 읽어 매번 `status: error`로 떨어진다(수집은 유효)
  - ⏸ **CronJob 등록 미완** — P0-3(Docker 빌드 미검증)에 걸려 있다
- 🟦 **목표선**: Airflow 도입(ADR-007) + 동적 DAG 생성 + 사용량 기반 동시성 조절 + 자동 재구성.
- **구현**
  - 최소선: `scripts/scheduler_tick.py` — due 데이터셋 조회 → C3 러너 호출 → `last_collected_at/next_collect_at` 갱신
    ✅ **작성 완료 (2026-11-02)** — P0-7로 앞당겼다. 의존성상 C3 뒤가 맞지만 **시계열은
    벽시계 시간으로만 쌓이므로** 늦게 시작할수록 손해가 복리로 커진다. 갱신은 파이프라인이
    스스로 하므로 스케줄러는 due 조회·순차 호출·실패 격리만 한다. 중복 실행은
    `pg_try_advisory_lock`으로 막는다(스키마 변경 불필요). 테스트 14건
  - 드리프트: `src/pipeline_engine/drift.py` — 수집 결과 필드 경로 집합을 정렬·해시해
    `data_registry.source_schema_*`에 저장, 변경 시 `source_schema_changed_at` 기록 +
    깨진 매핑의 대체 후보 제안. 설계·실측은 [database/source_schema_drift.md](database/source_schema_drift.md)
    ✅ **작성 완료 (2026-11-04)**
    - **사건(지문 변화)과 상태(깨진 매핑)를 따로 본다.** 지문만 비교하면 새 지문을 저장한
      순간 "변경 없음"이 되어 **깨진 매핑을 그대로 둔 채 경보만 사라진다**
    - 선택 필드 때문에 매번 울리지 않도록 관측 비율 90% 이상만 스키마로 보고,
      **히스테리시스**로 임계선 깜빡임을 막는다 — YouTube 실측에서
      `thumbnails.maxres`가 93.6%로 문턱 바로 위였다
    - 컬럼 이름을 계획서의 `schema_changed_at`이 아니라 `source_schema_*`로 둔다.
      `data_registry`에서 "schema"만 쓰면 **우리 DB 스키마**로 읽힌다
    - **감지기가 수집을 죽이지 않는다** — 관측이지 관문이 아니다
  - Airflow 도입 시 **§6.2 DB 커넥션 재사용 재검토 선행**(KubernetesExecutor 우선)
- **완료 기준**: 등록만으로 주기 수집이 자동 수행되고, 소스 스키마 변경이 **자동 감지·기록**됨
  - 감지 ✅ / 기록 ⏸ (DDL 적용 대기) / 주기 자동 수행 ⏸ (CronJob 등록 — P0-3 종속)
- **의존**: C3

#### C5. 능동형 데이터 패키징 〔3·4차 · SW모듈 귀속: 모비젠〕 — 🟩 **최소선 완료 (2026-11-03)**
- 🟩 **최소선**: `manifest.json` + 데이터 파일 + **파일별 SHA-256**을 묶은 zip 패키지 생성·검증 CLI. 서명은 **HMAC-SHA256**(공유키). ✅
  - `src/packaging/{manifest,builder,verify}.py`, `scripts/package_dataset.py`. 테스트 22건
  - **신뢰의 사슬**: `manifest.sig` ──HMAC→ `manifest.json` ──SHA-256→ 데이터 파일.
    파일 하나만 바뀌어도 체크섬이 어긋나고, manifest를 고치면 서명이 깨진다
  - **서명은 manifest 안에 넣지 않는다** — 넣으면 "서명을 포함한 상태"를 서명해야
    하는 순환이 생긴다. 별도 파일로 둔다
  - **직렬화를 한 곳(`canonical_bytes`)으로 고정한다** — 키 순서나 공백이 달라지면
    같은 내용인데 서명이 깨진다
  - **검증은 DB도 네트워크도 쓰지 않는다**(완료 기준 "타 환경에서 검증 통과").
    테스트가 `get_conn`을 폭발시켜 그걸 강제한다
  - 변조 6종을 전부 거부하고 **사유를 각각 다르게** 짚는 것을 확인했다 —
    데이터 변조/manifest 변조/몰래 파일 추가/파일 누락/서명 제거/모르는 형식/틀린 키
- ⏸ **`data_package` 테이블은 만들지 않았다.** 최소선 완료 기준이 파일 수준이라
  없어도 성립한다. SeaweedFS `package/` 저장과 함께 C6(다운로드 API) 때 넣는다
- 🟦 **목표선**: 공개키 서명(ed25519), 접근제어·권한 메타, 리니지 자동 수집, 버전 관리.
- **구현**
  - `src/packaging/manifest.py` — 식별자·출처·생성일시·소유자·라이선스·기술통계(B1 재사용)·구성 파일 목록·체크섬
  - `src/packaging/builder.py` / `verify.py`, CLI `scripts/package_dataset.py`
  - 저장: SeaweedFS `package/{dataset_id}/{version}/`, prefix는 `data_registry`에 기록
  - **신규 테이블 `data_package`** — `package_id, dataset_id, version, s3_prefix, manifest_sha256, signed_at`
  - 완료 후 `docs/architecture/06_Object_Storage_Format_Spec.md`에 패키지 절 추가
- **완료 기준**: 타 환경에서 **체크섬·서명 검증 통과**, manifest만으로 출처 추적 가능
- **의존**: B1(기술통계) — 없어도 최소선 가능

#### C6. 탐색 확장·통합 + OpenAPI 〔3차 · 모비젠〕 — 🟩 **최소선 완료 (2026-11-04)**
- 🟩 **최소선**: **내부 카탈로그 OpenAPI** + 외부 포털 **1곳(CKAN)** 메타 수집해 내부 검색에 합류 ✅
  - `src/api/{main,schemas}.py`, `src/federation/ckan.py`,
    `scripts/harvest_external.py`, [docs/api/02_Catalog_API.md](api/02_Catalog_API.md). 테스트 22건
  - `GET /v1/datasets` · `/v1/datasets/{id}` · `/v1/datasets/{id}/jsonld` · `/v1/search` · `/healthz`
  - **API가 B1·B2·A2를 한자리에 모은다** — 상세 응답에 특징·관계·내려받기 경로가,
    검색 응답에 두 채널 순위와 추출 요약이 실린다
  - **연합 검색 확인**: 캐나다 공개데이터 포털에서 30건을 들여와 같은 색인에 합쳤다.
    `"health care system"`은 외부가, `"암 건강 정보"`는 내부가 올라온다
  - ⚠️ **읽기 전용이다.** 등록·수정은 D1의 일이고 인증이 먼저다
  - ⚠️ **공개 범위를 아직 못 좁혔다.** 모든 데이터셋이 `ORG`라 `PUBLIC`만
    내보내면 빈 응답이 된다. **이대로 외부에 열면 조직 내부용 데이터가 나간다** —
    D1에서 반드시 좁혀야 한다
  - 실측에서 걸린 것 둘: 포털 **429를 하드 실패로 처리**해 0건이 됐던 것(재시도 대상으로
    교정), `language`/`spatial` 기본값이 `'ko'`/`'KR'`이라 **캐나다 데이터가 한국어·한국
    소재로 기록될 뻔한 것**(포털 값 우선 + 소재는 NULL)
- 🟦 **목표선**: SDMX 등 다중 포털 연합 검색, 인증·쿼터, 사용 통계.
- **구현**
  - `src/api/main.py` (FastAPI) — `GET /v1/datasets`, `/v1/datasets/{id}`, `/v1/search`, `/v1/datasets/{id}/download`
  - `src/federation/ckan.py` — CKAN `package_search` → DCAT 매핑 → `dcat_dataset`에 `origin='external'`로 적재
  - 스펙 문서는 비어 있는 `docs/api/`에 생성
- **완료 기준**: 외부 포털 데이터셋이 내부 검색 결과에 함께 노출되고 OpenAPI로 호출 가능
- **의존**: C1

#### C7. 외부 모듈 연계 ((s)LLM) 〔4차 · 모비젠〕
- 🟩 **최소선**: **OpenAI 호환 API 어댑터 1종** + 설정으로 모델 교체. 실패 시 degrade.
- 🟦 **목표선**: 로컬 sLLM 어댑터, 비용·레이트리밋 제어, 기존 외부 시스템 연계 규격.
- **구현**: `src/llm/base.py`(`generate(prompt, **opts)`), `src/llm/adapters/openai_compat.py`, `configs/models/*.yaml`. **직접 호출 금지, 전부 어댑터 경유.**
- **완료 기준**: 설정 변경만으로 모델 교체, 장애 시 부분 성공으로 degrade
- **의존**: 없음 (A2와 규격 공유)

---

### D. 통합 플랫폼·실증

#### D1. 플랫폼 운영 기능 〔모비젠〕 — 🟨 **내부 콘솔 프로토타입 (2026-11-04)**
- 🟩 **최소선**: 데이터셋 등록·상태·수집 이력 조회 API(C6에 엔드포인트 추가).
  - ✅ 조회 API + **내부 개발 콘솔** — `src/api/console.py`, `src/api/static/index.html`,
    `scripts/run_console.py`. 설계·발견은 [api/03_Internal_Console.md](api/03_Internal_Console.md)
  - ⚠️ **포털이 아니다.** 실제 사용자 화면·디자인·배포는 케이웨어 과업이고, 이것은
    (a) 계획서 기능이 실 데이터에서 도는지 확인 (b) 사람이 판단해야 하는 일
    (관계 검토·라벨링)을 실제로 처리 (c) **C6 OpenAPI의 첫 소비자**로서 빠진 것 찾기
  - 붙이자마자 나온 불일치 3건(검색 파라미터 `why`→`explain`, 최희귀어 키 `term`→`token`,
    `keywords` 컬럼이 비밀값 필터에 걸려 사라짐). **API는 200을 돌려주고 있었다**
  - ⏸ 정형 탭은 **의도적으로 비워 둔다** — D-2 합의 전에 만들면 다시 만들게 된다
  - ⚠️ 콘솔은 **권한을 보지 않는다**(총괄 관리자 시점). `127.0.0.1` 고정
- 🟦 **목표선**: 품질·거버넌스 메타(권한·정책) 기록, 운영 대시보드 연계(케이웨어 접점).

#### D2. 실증·시범서비스 지원 〔모비젠 + 실증기관〕
- 🟩 **최소선**: 실증 환경 배포 절차 문서화 + 재현 스크립트.
- 🟦 **목표선**: 배포 자동화, 모니터링·알림, 도메인 시범 적용.

---

### 8.4 진행 순서 (의존성 기준)

**0단계 — 선행 과제 (P0)**
0. **P0-5** 품질 실측 SQL 2건 → **P0-1** 임베딩 청킹 → **P0-2** 자막 활용 경로 연결 → **P0-3** 컨테이너화

**1단계 — 토대 (병렬 가능, 전부 최소선까지)**
1. **A1** 수집 어댑터화 → 이후 C3·C4·A3의 전제
2. **B1** 특징 추출·분석 → B2·B3·C5의 입력
3. **C5** 패키징 (독립적 · 3차년도 과업 마감용)
4. **C1** 검색 고도화 (독립적)

**2단계 — 관계·탐색 축**
5. **B2** 관계 분석 → **B3** 지식그래프
6. **C2** 목적 기반 자동 탐색 (C1+B3)
7. **A2** AI 생성 메타데이터 (+ **C7** 어댑터)

**3단계 — 자동화·개방**
8. **C3** 템플릿 파이프라인 → **C4** 동적 변화 자동 구성
9. **C6** OpenAPI·통합 탐색 → **D1** 운영 기능

**4단계 — 협업·마무리**
10. **A3** 정형 저장 · **B4** 관계 모델 수용 (와이즈넛 일정 연동)
11. **C7** 목표선 확장, **D2** 실증·시범서비스, 전체 통합·안정화

> 핵심 의존성: `A1 → C3 → C4` / `B1 → B2 → B3 → C2` / `C1 → C6 → D1` / `A2 ↔ C7`

### 8.5 참고 — 모비젠 ↔ 와이즈넛 역할 분담 (계획서 기준)

계획서의 연차별 기관 과업과 **SW 모듈 귀속 명시**를 정리하면 다음과 같다.
대체로 **와이즈넛 = 설계·모델(알고리즘)**, **모비젠 = 수집·파이프라인·플랫폼 구현**으로 나뉜다.

**① 모비젠 단독 수행 가능 (계획서상 모비젠 모듈)**

| 영역 | 근거(SW 모듈 귀속) | 본 로드맵 |
|---|---|---|
| 데이터 특징 추출·분석 모듈 | 1차 SW 모듈 (모비젠) | B1 |
| 데이터 검색 전처리 모듈 | 1차 SW 모듈 (모비젠) | C1 |
| 비정형 액티브 메타 수집 모듈 | 2차 SW 모듈 (모비젠) | 완료 |
| 네트워크 생성·분석 모듈 | 2차 SW 모듈 (모비젠) | B3 |
| 데이터 검색·탐색 모듈 | 2차 SW 모듈 (모비젠) | C1·C2 |
| 템플릿 기반 파이프라인 생성 모듈 | 2차 SW 모듈 (모비젠) | C3 |
| 자동 파이프라인 구성 모듈 | 4차 SW 모듈 (모비젠) | C4 |
| 능동형 데이터 패키징 모듈 | 4차 SW 모듈 (모비젠) | C5 |
| 확장 가능 수집 · 탐색 확장/OpenAPI · 외부 모듈 연계 | 3·4차 주관 과업 | A1·C6·C7 |

**② 와이즈넛 단독 수행 (우리는 산출물만 수용)**

| 영역 | 근거 | 우리 쪽 접점 |
|---|---|---|
| 액티브 메타데이터 **구조·클래스 설계** | 1차 공동1 | 스키마 반영(§7) |
| **데이터 의미 이해**, 의미론적 연관성 분석 | 2차 공동1 | 산출 관계 수용(B4) |
| **데이터 특징 기반 분류**, 상호 연관성 분석 모델 | 3차 공동1 | 결과 적재 |
| **언어모델 기반 관계 생성**(3차), **GNN 기반 관계 생성·검증**(4차) | 3·4차 공동1 | B4 교환 규격 |
| **사용자 기반 액티브 메타데이터 관리 모듈** | 2차 SW 모듈 (와이즈넛) | 권한·주석 메타 연동 |
| ML 기반 **데이터 카탈로그 고도화**, 검증/평가 자동화, 표준화 방안 | 4차 공동1 | 카탈로그·품질 지표 제공 |

**③ 반드시 합의가 필요한 공동 인터페이스 (지금 정해둘 것)**

| # | 인터페이스 | 내용 | 상태 |
|---|---|---|---|
| 1 | **메타데이터 스키마** | 와이즈넛 구조 설계 ↔ 모비젠 저장 구현 | §7 협의 중 |
| 2 | **관계 데이터 교환 규격** | 모델 산출 관계(JSON) ↔ `dcat_dataset_relation` | **미합의 → B4에서 먼저 제안** |
| 3 | **파이프라인 자동화 아키텍처** | 와이즈넛 설계(2차) ↔ 모비젠 구현(C3·C4) | 미확인 |
| 4 | **데이터 카탈로그** | 와이즈넛 ML 고도화(4차) ↔ 모비젠 카탈로그 저장·API | 미확인 |
| 5 | **검증·평가 자동화** | 와이즈넛 자동화(4차) ↔ 모비젠 품질 지표 산출(B1) | 미확인 |

> **권고**: ②·③은 우리가 **먼저 규격 초안을 만들어 제안**하는 편이 유리하다.
> 저장·조회 구현은 모비젠 쪽이므로, 스키마를 선점해두면 이후 수용 비용이 낮아진다.

### 8.6 공통 수행 원칙

- 기능 단위 커밋 + 최소 1개 테스트(문서·소규모는 main 직접 커밋)
- 신규 모듈은 **설정 외부화·어댑터화** 기본(소스·모델·저장소 교체 가능성 확보)
- 자격증명은 **환경변수·K8s Secret만**(코드·문서 평문 금지)
- 스키마 변경 → `docs/database/datagokr_schema.md` + ERD 동시 갱신
- 저장 형식 변경 → `docs/architecture/06_Object_Storage_Format_Spec.md` 동시 갱신
- 설계 결정은 **ADR 추가**로 기록
- 각 작업 완료 시 **최소선/목표선 중 어디까지 했는지와 한계**를 해당 절에 기록

---

## ⏸ 보류 중인 결정

| # | 사항 | 막고 있는 것 | 근거 문서 |
|---|---|---|---|
| D-1 | **비정형에 공통 분류 체계(76종)를 쓸 것인가** — 소비재·생활 영역이 없어 패션·화장품·식품·디지털가전은 무엇을 골라도 틀린다. (A) 체계에 대분류 추가 / (B) 비정형 별도 체계 / (C) 비정형은 `category` 미사용 | `sql/migration_2026_11_02_category_source.sql` 적용 보류. C6 등록 API 설계 | [ADR-020](adr/020_Category_Suggestion_Not_Assignment.md) |
| D-2 | **`vec_role` 행 분리 채택 여부** — 와이즈넛 회신 대기 | B2 착수(대표 벡터 적재) | [ADR-019](adr/019_Dataset_Profile_Vectors.md) |
| D-3 | **임베딩 모델·프리픽스 규약** — 정형·비정형 교차 관계 계산의 전제. D-2가 거절돼도 별도 합의 필요 | `SEMANTICALLY_RELATED` 교차 산출 | 회신 초안 §5 (로컬 전용) |

> D-1은 **추천과 사람 선택이 쌓이면 데이터로 판단할 수 있다**(ADR-020). 지금 고르지 않는다.

---

## 참고 문서

- 데이터 설계 상세 및 다른 "미결정 사항": [datagokr_schema.md](database/datagokr_schema.md)
- 수집 파이프라인 운영 설계 전체(Airflow, 신규 데이터셋 온보딩, owner_id 갭 등): [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
- 인프라 현황: [01_Current_Infrastructure.md](infrastructure/01_Current_Infrastructure.md)
- 전체 문서 인덱스: [00_Index.md](00_Index.md)
