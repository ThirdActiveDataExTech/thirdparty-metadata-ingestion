-- ═══════════════════════════════════════════════════════════════
-- metric_registry : 지표 표준값 (지표 코드 1개 = 1행)
--
-- 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서 [3. 지표 표준값] 시트 기준.
-- 모비젠이 제안하고 와이즈넛이 반영한 신규 테이블 (NEXT_STEPS.md §7.2).
--
-- 목적: 정형·비정형 지표 코드가 한 테이블(active_meta_dataset/active_meta_file)에
--       섞여도 범위 밖 적재·오생성을 FK로 차단한다.
--       active_meta_dataset.metric_code / active_meta_file.metric_code가 이 표를 참조.
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS metric_registry CASCADE;

CREATE TABLE metric_registry (

    metric_code     TEXT PRIMARY KEY,
    -- 지표 코드 | 전역 유일
    -- 예) 'download_request_count', 'subscriber_count', 'content_view_count'

    label           TEXT NOT NULL,
    -- 한글명 | 화면 표기용 명칭
    -- 예) '다운로드·활용신청 건수', '구독자 수'

    layer           TEXT NOT NULL,
    -- 적용 레이어 | 'dataset' = active_meta_dataset, 'file' = active_meta_file
    -- 어느 이력 테이블에 적재되는 지표인지를 결정한다

    value_type      TEXT NOT NULL DEFAULT 'count',
    -- 값 유형 | count / ratio / index 등

    unit            TEXT,
    -- 단위 | 건 / 명 / 점 / 회 등

    applies_to      JSONB NOT NULL,
    -- 적용 소스 유형 | 적용 가능한 source_type 배열. ["*"] = 전체 공통
    -- 예) ["structured_file"]  ← 정형 전용
    -- 예) ["*"]                ← 정형·비정형 공통

    default_source  TEXT,
    -- 기본 수집 출처 | PORTAL_CATALOG / PORTAL_LOG / CRAWLER / API_*

    description     TEXT
    -- 설명 | 지표 정의, 산출 방식
);

-- 적용 범위 조회용
CREATE INDEX idx_metric_registry_applies ON metric_registry USING GIN (applies_to);
CREATE INDEX idx_metric_registry_layer   ON metric_registry (layer);
