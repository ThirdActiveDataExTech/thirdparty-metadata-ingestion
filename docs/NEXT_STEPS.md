# 다음 작업 로드맵

> **Last Updated:** 2026-07-28
> **목적:** 세션이 끊겨도 여기서부터 바로 이어갈 수 있도록, 남은 작업을 순서대로 기록한다.
> 완료된 작업의 상세 이력은 `git log` 참조 — 이 문서는 "지금 무엇을 해야 하는가"만 담는다.
> 항목을 끝내면 체크하고, 새로 발견한 항목은 해당 순서 구간에 추가한다.
>
> 수집 파이프라인 운영 설계(§가 자주 인용됨) 전체는
> [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md) 참조.

## 진행 순서 (2026-07-23 합의)

남은 작업을 성격별로 분류해 아래 순서로 진행하기로 합의:

1. ~~**A. 결정만 필요한 것** — 2-3, 2-4, 2-10, 2-11, §3의 7번~~ **완료 (2026-07-23)**
2. ~~**B-1. 2-1(blog API 실측 → ADR-006)**~~ **완료 (2026-07-24)** — §5 AI 필드 실측
   검증은 D 순서(§6.1 이후)로 이미 미뤄둔 상태라 B의 나머지 항목 아님
3. **C. 외부 의존 (대기)** — §3의 8번(계정테이블 FK), K8s Secret 생성 — 여전히 대기 중,
   우리가 지금 처리 불가
4. **D. 구현 작업** — ~~§6.1 Phase 1(YouTube+쇼핑 파일럿)~~ **완료 (2026-07-27)**,
   ~~§6.1 Phase 2(Persona+뉴스+블로그)~~ **완료 (2026-07-28)** — 5개 소스 전부 실
   서버·실 API 검증 끝남 → 다음은 §5(AI 필드 실측·DDL·collector에 통합) 또는
   §6.2(Airflow 오케스트레이션) → §6.3(프론트엔드 API)

---

## 0. (완료) `meta_naver_shopping` / `meta_naver_persona` / `meta_naver_blog` 스키마 리뷰

**사용자 최종 확인 완료 (2026-07-23).** 세 테이블의 컬럼 목록은 대화 중 정리해서 전달함 —
필요하면 `sql/meta_naver_shopping.sql`, `sql/meta_naver_persona.sql`, `sql/meta_naver_blog.sql`
직접 참조.

검토 중 발견된 비대칭:
- [x] ~~`meta_naver_shopping`의 `cat_level1~4` 예시 주석이 `meta_naver_persona`엔 없던 문제~~
      — `meta_naver_persona.sql`에 동일한 예시 주석 추가 완료, 롤백 트랜잭션 검증 완료.
- [x] ~~`meta_naver_blog`에 플랫폼 구분 컬럼 없던 문제 (2-2)~~ — **결정: `platform TEXT NOT NULL`
      컬럼 추가** (news의 `is_naver_hosted` boolean 패턴 대신 `platform` 문자열 채택 — Naver
      블로그 검색 API가 blog.naver.com 외 티스토리/브런치/워드프레스/Blogger 등도 반환하기
      때문에 단순 boolean보다 세분화가 필요하다고 판단). `blog_id`/`log_no`/ADR-006 댓글·공감
      수집 가능 여부는 `platform='naver'`일 때만 해당하도록 주석 갱신. `sql/meta_naver_blog.sql`,
      `sql/seeds.sql`(기존 3건 모두 `platform='naver'`) 반영·검증 완료.
- [x] ~~`meta_naver_blog.updated_at`과 `meta_naver_shopping`/`meta_naver_persona`의
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

## 1. (거의 완료) 실제 DB 반영

**2026-07-23 실제 서버에 반영 완료.** 기존 데이터는 전부 예시/시드 데이터라 재생성해도
무방하다고 확인 후 진행 — 롤백 아니라 실제 커밋.

- [x] ~~0번 스키마 리뷰가 먼저 끝나야 함~~ — 완료
- [x] ~~DDL 18개 파일 순서대로 서버에 재실행~~ — 완료 (`dataset_credentials.sql` 포함)
- [x] ~~`sql/seeds.sql` 재실행~~ — 완료
- [x] ~~`sql/views.sql` 재실행~~ — 완료 (DDL 적용 순서 7단계, 기존 체크리스트에 누락돼 있었음)
- [x] ~~임베딩 스크립트 재실행~~ — `embed_datasets.py`(6건), `embed_youtube_videos.py`(4건),
      `embed_naver_news.py`(3건) 전부 완료. 이 시점엔 `embed_naver_blog.py`가 아직 없어서
      제외했었는데, 바로 다음(§4)에서 작성·실행까지 완료함(3건)
- [x] ~~검색 스크립트로 sanity check~~ — `search_datasets.py`/`search_youtube_videos.py`/
      `search_naver_news.py` 전부 실행, 결과 의미상 정상 확인
- [ ] **`dataset-credentials-encryption-key` K8s Secret 실제 생성 (§9 참조)** — 미완료.
      이 환경엔 클러스터 kubeconfig가 없어서 실행 불가. `metadata-ingestion` 네임스페이스
      자체도 아직 실제 생성 안 됐을 가능성 있음(YAML만 존재) — 먼저 확인 필요. 클러스터
      접근 가능한 곳에서 아래 실행:
      ```bash
      kubectl create namespace metadata-ingestion   # 없다면
      kubectl create secret generic dataset-credentials-encryption-key \
        --from-literal=key=$(openssl rand -base64 32) \
        -n metadata-ingestion
      ```

---

## 2. 남은 스키마·API 결정

- [x] ~~2-1. `active_meta_naver_blog` 실제 API 조사 → ADR-006~~ — **결정 완료 (2026-07-24).**
      실제 API 호출로 검증: 반응(공감 등) 수는 `blog.like.naver.com`으로 브라우저 자동화
      없이 수집 가능(확인), 댓글 수는 cbox 계열 API가 정책적으로 차단됨(보류), 조회수는
      페이지에 아예 노출 안 됨(미수집). [ADR-006](adr/006_Naver_Blog_Metrics_Decision.md)
      작성 완료. `sql/active_meta_naver_blog.sql` 재설계(`reaction_count`/
      `reaction_breakdown`/`delta_reactions`), 실 서버 반영·검증 완료.
- [x] ~~2-2. `meta_naver_blog` 플랫폼 구분 확인~~ — **결정: `platform TEXT` 컬럼 추가.**
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
      컬럼으로 표시, 행은 보존.** `meta_youtube_video`/`meta_naver_news`/`meta_naver_blog`
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
| 2 | `meta_youtube_video.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 채널에서 사라진 영상 표시. 오늘 DDL 반영·검증 완료 |
| 3 | `meta_naver_news.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 위와 동일 (발견형 소스라 동일 패턴 적용) |
| 4 | `meta_naver_blog.is_removed` / `removed_at` | 컬럼 추가 | ✅ **완료** | 위와 동일 |
| 5 | `dataset_credentials` | 신규 테이블 | ✅ **완료** | 데이터셋별 API Key 암호화 저장 (pgcrypto). 유일하게 "새 테이블"이 필요했던 항목 |
| 6 | `UNIQUE(owner_id, source_type, ...)` 형태의 중복 방지 제약 | 인덱스 추가 | ⏳ 보류 (owner_id 컬럼은 생겼으나 실사용 데이터 필요) | 04_Collection_Pipeline_Operations.md §7.2~7.3. JSONB `subjects` 배열 특성상 완벽한 DB 제약보다 애플리케이션 레벨 체크에 가까울 수 있음 |
| 7 | `meta_naver_news.updated_at` | 컬럼 추가 | ✅ **완료** | 예전 세션에서 발견한 비대칭 — `meta_youtube_video`/`meta_naver_blog`와 동일 패턴으로 추가, 실 서버 반영 완료 (2026-07-23) |
| 8 | 계정 테이블 FK 연결 (`dcat_dataset.owner_id → <계정테이블>.<PK>`) | FK 제약 추가 (조건부, 남의 팀 일정 종속) | ⏳ **계정 테이블 스펙 확정 대기** | 계정/인증 테이블은 metadata-ingestion 팀이 아니라 플랫폼 다른 담당자가 만듦. 같은 `datagokr` DB 안에 별도 스키마로 생성될 예정(2026-07-23 기준 계획 단계, 테이블명·PK 타입 미정). 생성되면: (1) 실제로 같은 database인지 재확인 (다른 database면 FK 불가), (2) PK 타입에 맞춰 `owner_id` 타입 조정, (3) FK 추가 |

---

## 4. (거의 완료) 임베딩 파이프라인 마무리

- [x] ~~`scripts/embed_naver_blog.py` 작성~~ — `embed_naver_news.py` 패턴 그대로 이식 완료
      (`meta_naver_blog` → `meta_naver_blog_vec`, has_content 분기 동일)
- [x] ~~`scripts/search_naver_blog.py` 작성~~ — `search_naver_news.py` 패턴으로 완료
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

**설계 제약 (2026-07-23 확정): 이 프로젝트를 위한 별도 학습·파인튜닝은 하지 않는다.**
사전학습된 오픈소스 모델(Groq API 경유 LLM 프롬프트, HuggingFace 사전학습 분류기/NER/
감성분석 모델 등)을 그대로 쓰는 것만 허용 — 어느 모델을 쓸지는 필드별로 구현 단계에서
후보를 비교해 결정. 상세: `datagokr_schema.md`의 "AI 메타데이터 파이프라인" 절.

- [ ] `meta_youtube_video_ai` DDL 작성 — 필드 후보 정리 완료(트랜스크립트 5개 +
      썸네일 VLM 4개, `datagokr_schema.md` 참조). P03/P06 연구 주제와 직결.
- [ ] `meta_naver_news_ai` 필드 후보 정리 완료(신규, `datagokr_schema.md` 참조:
      ai_summary/keywords/entities/related_companies/sentiment/topic_category/is_opinion) —
      DDL은 아직. 실측 검증 필요(어느 필드가 실제로 유용한 정확도가 나오는지)
- [ ] `meta_naver_blog_ai` 필드 후보 정리 완료(신규, `datagokr_schema.md` 참조:
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
      `meta_naver_shopping.py`/`meta_naver_persona.py`(`get_last_period` 추가) 수정.
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
- [ ] **성능 개선**: 지금 DB 헬퍼 함수들이 호출마다 새 커넥션을 열어서, 영상 1400개+
      채널 재실행이 ~5분 걸림. 커넥션을 pipeline 실행 단위로 재사용하도록 리팩터링 권장
      (배포 전 처리하는 게 좋음 — Airflow 스케줄로 자동 실행되면 체감 안 되지만 여전히
      비효율)
- [x] ~~**SeaweedFS raw/JSON-LD 저장**~~ — 구현·검증 완료 (2026-07-27, 설계는
      [architecture/05_Object_Storage_Export.md](../architecture/05_Object_Storage_Export.md)):
      `src/storage/{s3_client,raw_export,jsonld_export}.py` 신설, `src/collectors/
      youtube_transcript_collector.py`(yt-dlp+faster-whisper 자체 STT) 신설, 5개
      파이프라인 전부 통합, `meta_youtube_video.has_transcript`/`transcribed_at`
      컬럼 추가, `scripts/backfill_youtube_transcripts.py`(기존 영상 백로그 소급
      처리용) 작성. 실 서버로 `naver_news_ai`(뉴스, 1815개 raw txt + JSON-LD 1개)와
      `youtube_samsung_official`(트랜스크립트 JSON) 둘 다 검증 완료 — `data_registry.
      s3_raw_prefix`/`s3_jsonld_prefix` 정상 채워짐. 남은 것: 백로그 ~2,000개 영상은
      아직 대부분 미처리 상태라 `--limit`을 키워가며 여러 날에 걸쳐 백필 필요(05번
      문서 §8 참조, 처리 속도는 실제 대상 서버 `RnD-analyzer01`에서 재측정 권장)

### 6.2 오케스트레이션 (Airflow)

- [ ] 2-4 결정(ADR-002 갱신) 먼저 확정
- [ ] Airflow 자체 K8s 배포 (Helm chart 등 방식 결정 — 별도 인프라 문서 필요,
      `docs/infrastructure/07_Airflow.md` 후보)
- [ ] `dags/` 폴더 신설, source_type당 DAG 작성 (§3 — 3-레이어 구조: Scheduler/판단 태스크/실행 태스크)
- [ ] `data_registry` 조회 공통 함수(`get_due_datasets` 등) 작성
- [ ] `metadata-ingestion` K8s 네임스페이스 실제 생성
      (`kubectl apply -f k8s/namespaces/metadata-ingestion-ns.yaml`)

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

## 참고 문서

- 데이터 설계 상세 및 다른 "미결정 사항": [datagokr_schema.md](database/datagokr_schema.md)
- 수집 파이프라인 운영 설계 전체(Airflow, 신규 데이터셋 온보딩, owner_id 갭 등): [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
- 인프라 현황: [01_Current_Infrastructure.md](infrastructure/01_Current_Infrastructure.md)
- 전체 문서 인덱스: [00_Index.md](00_Index.md)
