-- ═══════════════════════════════════════════════════════════════
-- relation_type_registry : 관계 유형 표준값 (관계 유형 1개 = 1행)
--
-- 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서 [5. 관계 유형 표준값] 시트 기준.
-- 모비젠이 제안하고 와이즈넛이 반영한 신규 테이블 (NEXT_STEPS.md §7.2).
--
-- dcat_dataset_relation.relation_type / meta_file_relation.relation_type이 이 표를 참조.
-- relation_type을 문자열 값으로 저장하므로 유형이 늘어도 스키마를 고치지 않는다.
--
-- 주의: FK로 묶여 있어 여기에 등록되지 않은 관계 유형은 INSERT 자체가 불가하다.
--       비정형 전용 유형을 추가하려면 와이즈넛과 합의 후 이 표에 먼저 넣어야 한다.
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS relation_type_registry CASCADE;

CREATE TABLE relation_type_registry (

    relation_type   TEXT PRIMARY KEY,
    -- 관계 유형 코드 | 전역 유일
    -- 예) 'SEMANTICALLY_RELATED', 'KEYWORD_OVERLAP', 'TIMESERIES_SUCCESSOR'

    label           TEXT NOT NULL,
    -- 한글명 | 화면 표기용 명칭
    -- 예) '의미 유사', '키워드 유사', '시계열 연속'

    scope           TEXT NOT NULL,
    -- 적용 레이어 | 저장 테이블 구분
    -- 'dataset' = dcat_dataset_relation, 'file' = meta_file_relation, 'both' = 양쪽

    applies_to      JSONB NOT NULL,
    -- 적용 소스 유형 | 적용 가능한 source_type 배열. ["*"] = 전체 공통
    -- 2026-10-27 현재 비정형에 적용 가능한 유형은 ["*"]인 2종뿐
    -- (SEMANTICALLY_RELATED, KEYWORD_OVERLAP) — 나머지는 ["structured_file"]

    required_fields JSONB NOT NULL,
    -- 판정 근거 필드 | 판정에 필요한 항목
    -- 예) ["column_names","column_profile"], ["title","description"]
    -- 이 필드가 비어 있는 데이터셋은 해당 관계가 산출되지 않는다

    description     TEXT
    -- 설명 | 판정 근거, 산출 방식
);

CREATE INDEX idx_relation_type_registry_applies ON relation_type_registry USING GIN (applies_to);
CREATE INDEX idx_relation_type_registry_scope   ON relation_type_registry (scope);


-- ═══════════════════════════════════════════════════════════════
-- 모비젠 추가 제안 (2026-10-27) — 와이즈넛 합의 후 적재
--
-- 2026-10-27 기준 등록된 8종 중 비정형(applies_to=["*"])에 쓸 수 있는 유형은
-- SEMANTICALLY_RELATED, KEYWORD_OVERLAP 2종뿐이다. 아래 3종을 제안한다.
-- ═══════════════════════════════════════════════════════════════
--
-- ① 비정형 관계 2종
--
-- INSERT INTO relation_type_registry
--     (relation_type, label, scope, applies_to, required_fields, description) VALUES
-- ('ENTITY_SHARED', '개체 공유', 'dataset', '["*"]'::jsonb,
--  '["keywords"]'::jsonb,
--  '두 데이터셋이 공유하는 개체(키워드·태그·카테고리명)의 수와 비중으로 판정. '
--  '겹친 개체 목록을 evidence에 남겨 추천 근거로 제시한다'),
--
-- ('TEMPORAL_COMOVEMENT', '시계열 공변동', 'dataset', '["*"]'::jsonb,
--  '["accrual_periodicity"]'::jsonb,
--  '두 데이터셋의 지표 시계열을 일 단위로 리샘플해 1차 차분 후 스피어만 상관으로 판정. '
--  '겹치는 구간 30포인트 이상인 쌍만 산출하고 다중비교 보정(BH FDR)을 적용한다. '
--  'KEYWORD_OVERLAP(기간 중첩 여부)과 달리 "같이 움직이는가"를 본다');
--
-- ② 모델 산출 엣지 분리용 — 접미 '_MODEL' 규약
--
-- 배경: UNIQUE(source, target, relation_type) 때문에 같은 쌍·같은 유형에는 1행만
--      존재할 수 있다. method 컬럼은 UNIQUE에 없어 구분자가 되지 못한다.
--      따라서 규칙 산출과 모델 산출을 동시에 보관하려면 유형을 분리해야 한다.
-- 효과: 규칙 엣지만으로 만든 그래프와 규칙+모델 그래프를 각각 산출해 비교할 수 있고,
--      그 차이(커뮤니티 변화·modularity 변화)가 협력사 모델 기여의 정량 증거가 된다.
--
-- INSERT INTO relation_type_registry
--     (relation_type, label, scope, applies_to, required_fields, description) VALUES
-- ('SEMANTICALLY_RELATED_MODEL', '의미 유사(모델)', 'dataset', '["*"]'::jsonb,
--  '["title","description"]'::jsonb,
--  '외부 언어모델·GNN이 산출한 의미 유사 관계. 규칙 기반 SEMANTICALLY_RELATED와 '
--  '같은 쌍에 공존시키기 위해 유형을 분리한다. method에 산출기를 기록한다');
