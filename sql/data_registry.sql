-- ═══════════════════════════════════════════════════════════════
-- data_registry : 통합 운영정보 허브
-- 데이터셋당 1행 (최신 상태를 유지, 수집할 때마다 UPDATE)
-- "이 데이터셋이 어디에 있고 지금 어떤 상태인가"를 기술
-- dcat_dataset  : 무엇인가 (표준, 잘 안 바뀜)
-- dcat_provenance : 수집 이력 (실행마다 INSERT)
-- data_registry : 현재 운영 상태 (실행마다 UPDATE)
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS data_registry;

CREATE TABLE data_registry (

    -- ── 식별 ──────────────────────────────────────────────────
    dataset_id          TEXT PRIMARY KEY
                        REFERENCES dcat_dataset(dataset_id) ON UPDATE CASCADE ON DELETE CASCADE,
    -- dcat_dataset 의 dataset_id 를 PK 겸 FK 로 사용 (1:1 관계)
    -- ON DELETE CASCADE: 데이터셋 삭제 시 레지스트리 항목도 함께 삭제

    -- ── 저장 위치 : SeaweedFS (S3 API) ───────────────────────
    s3_raw_prefix       TEXT,
    -- S3 raw 데이터 경로 prefix (버킷 루트 기준)
    -- 형식: raw/{source_type}/{storage_key(dataset_id)}/
    --       storage_key()는 URN의 'urn:' 접두를 떼고 ':'를 '_'로 바꾼다
    --       (콜론을 오브젝트 키에 넣지 않기 위함 — src/storage/s3_client.py)
    -- 예) 'raw/shopping_insight/naver_shopping_insight/'
    -- 실제 오브젝트: {prefix}{item_id}.txt (news/blog)
    --               {prefix}{video_id}.json (video 자막)
    --               {prefix}{storage_key}.csv (선언형 전체 시계열)
    -- 내보내기 전에는 NULL이다 — 경로는 첫 export_dataset() 때 채워진다

    s3_jsonld_prefix    TEXT,
    -- S3 JSON-LD 경로 prefix
    -- 예) 'jsonld/shopping/naver_shopping_insight/'

    -- ── 저장 위치 : PostgreSQL ────────────────────────────────
    pg_meta_table       TEXT,
    -- 소스별 상세 메타 테이블명 (Schema.org 기반)
    -- 예) 'meta_shopping_insight', 'meta_video', 'meta_news'
    -- NULL = 아직 테이블 미생성

    pg_active_table     TEXT,
    -- 소스별 시계열 Active Meta 테이블명
    -- 예) 'active_meta_shopping_insight', 'active_meta_video'
    -- NULL = 아직 테이블 미생성

    -- ── 저장 위치 : Vector ────────────────────────────────────
    vec_collection      TEXT,
    -- pgvector 테이블 또는 Qdrant collection 명
    -- 예) 'dcat_dataset_vec'  (현재 pgvector 단일 테이블)
    -- Qdrant 전환 시 collection 이름으로 교체

    -- ── 운영 상태 ─────────────────────────────────────────────
    status              TEXT NOT NULL DEFAULT 'pending',
    -- 현재 수집 운영 상태
    -- 'pending'  : 등록됐으나 첫 수집 전
    -- 'active'   : 정상 수집 중
    -- 'paused'   : 수집 일시 중단 (수동 또는 정책)
    -- 'error'    : 마지막 수집 실패 상태

    last_collected_at   TIMESTAMPTZ,
    -- 마지막 성공 수집 완료 시각
    -- dcat_provenance 의 MAX(ended_at) WHERE status='success' 와 동기화

    next_collect_at     TIMESTAMPTZ,
    -- 다음 수집 예정 시각 (DB가 스케줄을 보유, Airflow가 폴링 — ADR-007)
    -- 예) 매일 02:00 → 오늘 수집 완료 후 내일 02:00 로 갱신

    last_error          TEXT,
    -- 마지막 실패 시 에러 메시지 (status='error' 일 때 채워짐)
    -- 성공 시 NULL 로 초기화

    -- ── 데이터 현황 ───────────────────────────────────────────
    item_count           BIGINT,
    -- 이 데이터셋을 구성하는 고유 아이템(raw) 수 = pg_meta_table 행 수
    -- 예) YouTube 영상 수, 뉴스 기사 수, 블로그 게시물 수, 쇼핑/Persona 카테고리 수
    -- row_count와 달리 시간이 지나도 "새 아이템이 추가되지 않는 한" 잘 바뀌지 않는다
    -- (반면 쇼핑/Persona/뉴스 등 시계열 소스는 같은 아이템이라도 매 수집마다
    --  row_count만 증가하고 item_count는 그대로인 경우가 많다)
    -- temporal_start/end와 동일한 패턴으로 dcat_dataset.item_count와 동기화한다
    -- (여기가 운영 중 실시간 갱신되는 원본, dcat_dataset 쪽은 조회 편의를 위한 미러)

    row_count           BIGINT,
    -- 이 데이터셋의 시계열 누적 총 행 수 = pg_active_table 행 수 (수집 완료 후 자동 갱신)
    -- dcat_provenance.rows_affected 누적 합과 일치해야 한다
    -- item_count와의 차이: item_count는 "몇 개를 추적하는가", row_count는
    -- "그 추적 결과가 지금까지 몇 행 쌓였는가" — 수집 회차가 늘수록 row_count만 증가한다

    temporal_start      DATE,
    -- 수집 데이터 실제 시작일 (수집 후 자동 갱신)
    -- dcat_dataset.temporal_start 와 동기화

    temporal_end        DATE,
    -- 수집 데이터 실제 종료일 (수집 후 자동 갱신, NULL=진행 중)
    -- dcat_dataset.temporal_end 와 동기화

    -- ── 원천 스키마 드리프트 (C4, 2026-11-04 추가) ────────────
    -- 어댑터 스펙(configs/sources/*.yaml)은 원천 응답의 경로를 문자열로 박아 둔다.
    -- 원천이 그 경로를 옮기거나 없애면 dig()가 None을 주고 해당 컬럼이
    -- **오류 없이 NULL**로 들어간다 — 수집은 '성공'으로 끝난다.
    -- 그래서 수집할 때마다 응답의 모양을 재서 지난번과 비교한다.
    -- 규격: src/pipeline_engine/drift.py

    source_schema_fingerprint TEXT,
    -- 핵심 필드 경로 집합의 SHA-256(hex). 달라지면 원천 모양이 바뀐 것이다

    source_schema_fields      JSONB,
    -- 그 지문의 원재료 — 정렬된 경로 배열. 지문만으로는 '바뀌었다'까지만 알고
    -- **무엇이** 바뀌었는지는 모른다. 차이를 짚으려면 직전 집합이 있어야 한다
    -- 예) ["description","link","originallink","pubDate","title"]

    source_schema_checked_at  TIMESTAMPTZ,
    -- 마지막으로 **검사한** 시각. 변경이 없어도 갱신된다.
    -- 멈춰 있으면 감지기 자체가 안 도는 것이다(조용한 실패 방지)

    source_schema_changed_at  TIMESTAMPTZ,
    -- 마지막으로 **달라진** 시각. 변경이 있을 때만 갱신된다

    -- ── 관리 ──────────────────────────────────────────────────
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 레지스트리 최초 등록 일시

    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 마지막 갱신 일시 (수집 완료마다 업데이트)
);

-- 운영 모니터링용 인덱스
CREATE INDEX idx_data_registry_status   ON data_registry(status);
CREATE INDEX idx_data_registry_next     ON data_registry(next_collect_at);
CREATE INDEX idx_data_registry_updated  ON data_registry(updated_at DESC);

-- "최근 원천이 바뀐 데이터셋" 운영 조회용. 한 번도 안 바뀐 행(NULL)은 색인에서 뺀다
CREATE INDEX idx_data_registry_schema_changed
    ON data_registry (source_schema_changed_at DESC)
    WHERE source_schema_changed_at IS NOT NULL;
