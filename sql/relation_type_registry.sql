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
