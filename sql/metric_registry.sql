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


-- ═══════════════════════════════════════════════════════════════
-- 모비젠 추가 제안 (2026-10-27) — 와이즈넛 합의 후 적재
--
-- 그래프 분석 산출물(중심성·커뮤니티)을 별도 테이블 없이 active_meta_dataset에
-- 적재하기 위한 지표 코드. observed_at에 그래프 산출 실행 시각을 넣으면
-- 시점별 네트워크 변화를 그대로 얻는다 (ADR-012).
--
-- 유의: 이 테이블은 본래 "관측값"을 담고 그래프 지표는 "분석 산출물"이다.
--      구조는 맞지만 성격이 다르므로 source 컬럼에 산출 주체를 명시해 구분한다
--      (예: source='GRAPH_ANALYZER').
-- ═══════════════════════════════════════════════════════════════
--
-- INSERT INTO metric_registry
--     (metric_code, label, layer, value_type, unit, applies_to, default_source, description) VALUES
-- ('graph_degree', '연결 차수', 'dataset', 'count', '개', '["*"]'::jsonb, 'GRAPH_ANALYZER',
--  '관계 그래프에서 해당 데이터셋에 연결된 엣지 수. 가중 차수는 weight 합'),
-- ('graph_pagerank', 'PageRank', 'dataset', 'ratio', NULL, '["*"]'::jsonb, 'GRAPH_ANALYZER',
--  '관계 그래프 내 영향력 지표. 추천 랭킹에 사용. seed 고정 필요'),
-- ('graph_community_id', '커뮤니티 ID', 'dataset', 'index', NULL, '["*"]'::jsonb, 'GRAPH_ANALYZER',
--  'Louvain 커뮤니티 탐지 결과의 군집 번호. 같은 run 안에서만 의미가 있다');
