# 다음 작업 로드맵

> **Last Updated:** 2026-07-22
> **목적:** 세션이 끊겨도 여기서부터 바로 이어갈 수 있도록, 남은 작업을 순서대로 기록한다.
> 완료된 작업의 상세 이력은 `git log` 참조 — 이 문서는 "지금 무엇을 해야 하는가"만 담는다.
> 항목을 끝내면 체크하고, 새로 발견한 항목은 해당 순서 구간에 추가한다.
>
> 수집 파이프라인 운영 설계(§가 자주 인용됨) 전체는
> [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md) 참조.

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
      `embed_naver_news.py`(3건) 전부 완료. `embed_naver_blog.py`는 아직 없어서 제외
      (§4 항목, 작성 후 별도 실행 필요)
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

- [ ] **2-1. `active_meta_naver_blog` 실제 API 조사 → ADR-006**
      댓글/공감/조회수를 실제로 수집할 수 있는지 미검증 (ADR-005가 뉴스에 대해 했던 것과 동일한 수준의
      실제 API 호출 테스트 필요). 확정 전까지 이 테이블은 수집 코드에서 미사용.
- [x] ~~2-2. `meta_naver_blog` 플랫폼 구분 확인~~ — **결정: `platform TEXT` 컬럼 추가**
      (0번 리뷰에서 완료. Naver 블로그 검색 API가 blog.naver.com 외 티스토리/브런치/
      워드프레스/Blogger 등도 반환한다고 판단 — 실제 라이브 API 호출로 재검증은 아직
      안 함, 2-1의 ADR-006 실측 작업 때 같이 확인 권장).
- [ ] **2-3. `dcat_dataset.publisher` NOT NULL 여부**
      `description`/`source_type`을 NOT NULL로 바꿀 때 같이 후보에 올랐다가 범위 밖이라 보류한 항목.
- [ ] **2-4. ADR-002("Airflow 도입 전 K8s CronJob") 갱신 여부**
      프론트엔드발 동적 데이터셋 등록은 정적 CronJob YAML로 구조적으로 안 됨 → 사실상 Airflow
      도입 조건 충족으로 판단(04_Collection_Pipeline_Operations.md 서두). 동의하면 ADR-002를
      Superseded 처리하고 새 ADR로 "Airflow 도입 확정" 기록 필요.
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
- [ ] **2-10. `next_collect_at` 드리프트 허용 여부**
      04_Collection_Pipeline_Operations.md §6.3. 지금 설계는 "수집 종료 시각 + 주기"로
      재계산해서 매번 조금씩 밀릴 수 있다. "매일 정확히 새벽 2시" 같은 고정 스케줄이
      필요하면 계산식을 바꿔야 한다.
- [ ] **2-11. 즉시 수집 트리거 필요 여부**
      04_Collection_Pipeline_Operations.md §5.4. MVP 범위에 Airflow REST API 트리거를
      넣을지, 15분 지연을 감수할지.

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
| 7 | `meta_naver_news.updated_at` | 컬럼 추가 (미확정) | ⏳ 미결정 | 예전 세션에서 발견한 비대칭 — `meta_youtube_video`/`meta_naver_blog`는 `updated_at`이 있는데 `meta_naver_news`만 없음. 오늘 범위는 아니었어서 반영 안 함, 필요하면 0번 리뷰와 같이 처리 |
| 8 | 계정 테이블 FK 연결 (`dcat_dataset.owner_id → <계정테이블>.<PK>`) | FK 제약 추가 (조건부, 남의 팀 일정 종속) | ⏳ **계정 테이블 스펙 확정 대기** | 계정/인증 테이블은 metadata-ingestion 팀이 아니라 플랫폼 다른 담당자가 만듦. 같은 `datagokr` DB 안에 별도 스키마로 생성될 예정(2026-07-23 기준 계획 단계, 테이블명·PK 타입 미정). 생성되면: (1) 실제로 같은 database인지 재확인 (다른 database면 FK 불가), (2) PK 타입에 맞춰 `owner_id` 타입 조정, (3) FK 추가 |

---

## 4. 임베딩 파이프라인 마무리

- [ ] `scripts/embed_naver_blog.py` 작성 — `scripts/embed_naver_news.py` 패턴 그대로 이식
      (`meta_naver_blog` → `meta_naver_blog_vec`, has_content 분기 동일)
- [ ] `scripts/search_naver_blog.py` 작성 — `search_naver_news.py` 패턴
- [ ] 1번(실제 DB 반영) 이후 실행해 검증
- [ ] **증분 임베딩 방식으로 전환** — 지금 `embed_*.py`는 전체 DELETE→INSERT 재계산 방식이라
      새 데이터셋이 동적으로 등록돼도 자동으로 임베딩되지 않음 (수동 재실행 필요). Airflow
      파이프라인에 편입하려면 "새로 추가된 아이템만" 임베딩하는 방식으로 바꿔야 자동화가 완성됨

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

`src/collectors/` 등이 전부 비어있음 (`.gitkeep`만 존재). `03_Component_Architecture.md`에
설계된 구조(`collectors/ → preprocess/ → extractor/ → storage/`)를 실제로 채워야 한다.
운영 방식 상세 설계는 [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
전체 참조 — 착수 전 §12(결정 사항 요약)부터 확정할 것.

### 6.1 Collector 코드

- [ ] 레거시 코드(`3amd/naver_shopping_insight.py`, `3amd/naver_persona.py`)를
      `src/collectors/`로 이식 (config.yaml → 환경변수/설정 체계 전환 포함)
- [ ] YouTube 수집 코드 신규 작성 — 발견형 로직 (04_Collection_Pipeline_Operations.md §6.1:
      신규/기존 분기 + `is_removed` 삭제 감지)
- [ ] Naver 뉴스 수집 코드 신규 작성 (본문 스크래핑 포함, 발견형 로직 동일 적용)
- [ ] Naver 블로그 수집 코드 신규 작성 (2-1, 2-2 결정 이후, 발견형 로직 동일 적용)
- [ ] 쇼핑/Persona 수집 코드는 선언형 로직 (§6.2: 신규/기존 분기·삭제 감지 불필요,
      카테고리 목록 고정 + 일별 지수만 갱신)
- [ ] 각 Collector: `run(dataset_id=...)` 함수 노출, 성공/실패 시
      `dcat_provenance` INSERT + `data_registry` UPDATE(status/next_collect_at/item_count)
      공통 로직 적용 (§6.3 next_collect_at 재계산 포함)

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
