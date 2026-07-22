# 다음 작업 로드맵

> **Last Updated:** 2026-07-22
> **목적:** 세션이 끊겨도 여기서부터 바로 이어갈 수 있도록, 남은 작업을 순서대로 기록한다.
> 완료된 작업의 상세 이력은 `git log` 참조 — 이 문서는 "지금 무엇을 해야 하는가"만 담는다.
> 항목을 끝내면 체크하고, 새로 발견한 항목은 해당 순서 구간에 추가한다.

---

## 0. (진행 중) `meta_naver_shopping` / `meta_naver_persona` / `meta_naver_blog` 스키마 리뷰

**담당: 사용자 직접 검토 중.** 세 테이블의 컬럼 목록은 대화 중 정리해서 전달함 — 필요하면
`sql/meta_naver_shopping.sql`, `sql/meta_naver_persona.sql`, `sql/meta_naver_blog.sql` 직접 참조.

검토 중 이미 발견된 비대칭 (참고용):
- `meta_naver_shopping`의 `cat_level1~4`는 컬럼마다 예시 주석이 있는데, `meta_naver_persona`의 동일 4개
  컬럼은 주석이 하나도 없음 (구조는 동일). 의도적 생략인지 그냥 누락인지 확인 필요.
- `meta_naver_blog`는 `blog_id`/`log_no`만 파싱해두고 `is_naver_hosted` 같은 플랫폼 구분 컬럼이 없음
  (아래 2-2 항목과 연결).

- [ ] 세 테이블 컬럼 검토 완료, 추가/변경 사항 확정
- [ ] 확정된 변경사항을 DDL(`sql/*.sql`)에 반영
- [ ] 컬럼이 추가/변경되면 `sql/seeds.sql`의 해당 INSERT도 같이 갱신
- [ ] `docs/database/datagokr_schema.md` 테이블 목록·ERD도 갱신

---

## 1. 실제 DB 반영

지금까지(오늘 세션 이전 포함) 만든 DDL 변경사항은 전부 롤백 트랜잭션으로만 검증했고
실제 서버에는 한 번도 반영하지 않았다. `dcat_dataset.sql`이 `DROP TABLE ... CASCADE`라
전체 자식 테이블이 함께 재생성된다.

- [ ] 0번 스키마 리뷰가 먼저 끝나야 함 (한 번에 반영하는 게 효율적)
- [ ] DDL 18개 파일 순서대로 서버에 재실행 (`docs/database/datagokr_schema.md`의 "DDL 적용 순서" 참조,
      `sql/dataset_credentials.sql` 포함 — `dcat_dataset.sql` 다음 아무 때나 가능, FK만 있으면 됨)
- [ ] `sql/seeds.sql` 재실행
- [ ] 임베딩 스크립트 재실행: `embed_datasets.py`, `embed_youtube_videos.py`, `embed_naver_news.py`
      (`embed_naver_blog.py`는 3번 항목에서 먼저 작성해야 같이 실행 가능)
- [ ] 검색 스크립트로 sanity check: `search_datasets.py`, `search_youtube_videos.py`, `search_naver_news.py`

---

## 2. 남은 스키마·API 결정 3가지

- [ ] **2-1. `active_meta_naver_blog` 실제 API 조사 → ADR-006**
      댓글/공감/조회수를 실제로 수집할 수 있는지 미검증 (ADR-005가 뉴스에 대해 했던 것과 동일한 수준의
      실제 API 호출 테스트 필요). 확정 전까지 이 테이블은 수집 코드에서 미사용.
- [ ] **2-2. `meta_naver_blog` 플랫폼 구분 확인**
      Naver 블로그 검색 API가 blog.naver.com 외 다른 플랫폼도 반환하는지 확인. 섞여 있다면
      news의 `is_naver_hosted`처럼 구분 컬럼 추가 여부 결정 (0번 리뷰와 함께 진행하면 좋음).
- [ ] **2-3. `dcat_dataset.publisher` NOT NULL 여부**
      `description`/`source_type`을 NOT NULL로 바꿀 때 같이 후보에 올랐다가 범위 밖이라 보류한 항목.
- [ ] **2-4. ADR-002("Airflow 도입 전 K8s CronJob") 갱신 여부**
      [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
      설계상 프론트엔드발 동적 데이터셋 등록은 정적 CronJob YAML로 구조적으로 안 됨 →
      사실상 Airflow 도입 조건 충족으로 판단. 동의하면 ADR-002를 Superseded 처리하고
      새 ADR로 "Airflow 도입 확정" 기록 필요.
- [x] ~~2-5. API Key 저장 모델~~ — **결정: 데이터셋별 저장.** `sql/dataset_credentials.sql`
      작성 완료(pgcrypto 암호화, 롤백 트랜잭션으로 암복호화 라운드트립 검증 완료).
      `04_Collection_Pipeline_Operations.md §6`, `05_Secrets_ConfigMaps.md` 반영 완료.
      남은 후속 작업:
      - [ ] `dataset-credentials-encryption-key` K8s Secret 실제 생성 (1번 "실제 DB 반영"과 함께)
      - [ ] `dataset_credentials.sql`을 DDL 적용 순서에 포함 (dcat_dataset 다음, FK 의존)
      - [ ] 데이터셋 등록 API(§5.3)에서 암호화 저장/폴백 조회 로직 구현
      - [ ] Collector 공통 유틸에 "dataset_credentials 우선 조회 → 없으면 플랫폼 공유 Secret" 폴백 로직 추가

---

## 3. 임베딩 파이프라인 마무리

- [ ] `scripts/embed_naver_blog.py` 작성 — `scripts/embed_naver_news.py` 패턴 그대로 이식
      (`meta_naver_blog` → `meta_naver_blog_vec`, has_content 분기 동일)
- [ ] `scripts/search_naver_blog.py` 작성 — `search_naver_news.py` 패턴
- [ ] 1번(실제 DB 반영) 이후 실행해 검증
- [ ] **증분 임베딩 방식으로 전환** — 지금 `embed_*.py`는 전체 DELETE→INSERT 재계산 방식이라
      새 데이터셋이 동적으로 등록돼도 자동으로 임베딩되지 않음 (수동 재실행 필요). §5의
      Airflow 파이프라인에 편입하려면 "새로 추가된 아이템만" 임베딩하는 방식으로 바꿔야
      자동화가 완성됨 (runbooks/04_Add_New_Dataset_Existing_Source.md 검증 항목에서도 언급)

---

## 4. AI 메타데이터 테이블

- [ ] `meta_youtube_video_ai` DDL 작성 (필드 초안은 `datagokr_schema.md`의
      "AI 메타데이터 파이프라인" 절에 이미 있음: ai_summary/ai_keywords/ai_entities/
      ai_content_type/ai_key_points). P03 연구 주제와 직결.
- [ ] `meta_naver_news_ai` 필드 설계 (초안조차 없음)
- [ ] `meta_naver_blog_ai` 필드 설계 (초안조차 없음)

---

## 5. 수집 코드 작성 (가장 큰 작업)

`src/collectors/` 등이 전부 비어있음 (`.gitkeep`만 존재). `03_Component_Architecture.md`에
설계된 구조(`collectors/ → preprocess/ → extractor/ → storage/`)를 실제로 채워야 한다.
운영 방식(스케줄링·신규 데이터셋 온보딩) 상세 설계는
[architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md) 참조 —
착수 전 그 문서 §8의 미결정 사항(2-4, 2-5와 동일)부터 확정할 것.

### 5.1 Collector 코드

- [ ] 레거시 코드(`3amd/naver_shopping_insight.py`, `3amd/naver_persona.py`)를
      `src/collectors/`로 이식 (config.yaml → 환경변수/설정 체계 전환 포함)
- [ ] YouTube 수집 코드 신규 작성
- [ ] Naver 뉴스 수집 코드 신규 작성 (본문 스크래핑 포함)
- [ ] Naver 블로그 수집 코드 신규 작성 (2-1, 2-2 결정 이후)
- [ ] 각 Collector: `run(dataset_id=...)` 함수 노출, 성공/실패 시
      `dcat_provenance` INSERT + `data_registry` UPDATE(status/next_collect_at/item_count)
      공통 로직 적용 (04_Collection_Pipeline_Operations.md §3.4)

### 5.2 오케스트레이션 (Airflow)

- [ ] 2-4 결정(ADR-002 갱신) 먼저 확정
- [ ] Airflow 자체 K8s 배포 (Helm chart 등 방식 결정 — 별도 인프라 문서 필요,
      `docs/infrastructure/07_Airflow.md` 후보)
- [ ] `dags/` 폴더 신설, source_type당 DAG 작성 (04_Collection_Pipeline_Operations.md §3)
- [ ] `data_registry` 조회 공통 함수(`get_due_datasets` 등) 작성
- [ ] `metadata-ingestion` K8s 네임스페이스 실제 생성
      (`kubectl apply -f k8s/namespaces/metadata-ingestion-ns.yaml`)

### 5.3 프론트엔드 연동 API

- [ ] 2-5 결정(API Key 모델) 먼저 확정
- [ ] `POST /api/datasets` 등 신규 데이터셋 등록 API 구현
      (04_Collection_Pipeline_Operations.md §7 초안 계약 참조, `docs/api/`로 정식 문서화 필요)
- [ ] runbooks/04_Add_New_Dataset_Existing_Source.md의 A/B 경로를 API가 내부적으로 구현

---

## 참고 문서

- 데이터 설계 상세 및 다른 "미결정 사항": [datagokr_schema.md](database/datagokr_schema.md)
- 수집 파이프라인 운영 설계(Airflow, 신규 데이터셋 온보딩): [architecture/04_Collection_Pipeline_Operations.md](architecture/04_Collection_Pipeline_Operations.md)
- 인프라 현황: [01_Current_Infrastructure.md](infrastructure/01_Current_Infrastructure.md)
- 전체 문서 인덱스: [00_Index.md](00_Index.md)
