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
                        REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    -- dcat_dataset 의 dataset_id 를 PK 겸 FK 로 사용 (1:1 관계)
    -- ON DELETE CASCADE: 데이터셋 삭제 시 레지스트리 항목도 함께 삭제

    -- ── 저장 위치 : MinIO ─────────────────────────────────────
    minio_raw_prefix    TEXT,
    -- MinIO raw 데이터 경로 prefix (버킷 루트 기준)
    -- 예) 'raw/shopping/naver_shopping_insight/'
    -- 실제 오브젝트: {prefix}YYYY/MM/DD/{dataset_id}_{timestamp}.json

    minio_jsonld_prefix TEXT,
    -- MinIO JSON-LD 경로 prefix
    -- 예) 'jsonld/shopping/naver_shopping_insight/'

    -- ── 저장 위치 : PostgreSQL ────────────────────────────────
    pg_meta_table       TEXT,
    -- 소스별 상세 메타 테이블명 (Schema.org 기반)
    -- 예) 'meta_naver_shopping', 'meta_youtube_video', 'meta_naver_news'
    -- NULL = 아직 테이블 미생성

    pg_active_table     TEXT,
    -- 소스별 시계열 Active Meta 테이블명
    -- 예) 'active_naver_shopping', 'active_youtube_video'
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
    -- 다음 수집 예정 시각 (K8s CronJob 스케줄 기준)
    -- 예) 매일 02:00 → 오늘 수집 완료 후 내일 02:00 로 갱신

    last_error          TEXT,
    -- 마지막 실패 시 에러 메시지 (status='error' 일 때 채워짐)
    -- 성공 시 NULL 로 초기화

    -- ── 데이터 현황 ───────────────────────────────────────────
    row_count           BIGINT,
    -- 현재 수집된 총 행 수 (수집 완료 후 자동 갱신)

    temporal_start      DATE,
    -- 수집 데이터 실제 시작일 (수집 후 자동 갱신)
    -- dcat_dataset.temporal_start 와 동기화

    temporal_end        DATE,
    -- 수집 데이터 실제 종료일 (수집 후 자동 갱신, NULL=진행 중)
    -- dcat_dataset.temporal_end 와 동기화

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
