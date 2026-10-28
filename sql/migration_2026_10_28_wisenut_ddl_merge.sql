-- ═══════════════════════════════════════════════════════════════
-- migration_2026_10_28_wisenut_ddl_merge.sql
--
-- 와이즈넛 수신 DDL 5건을 우리 정본(sql/*.sql)에 통합한 뒤, 실제 DB를 그 정본에 맞춘다.
--   수신 원본: sql/_received/wisenut_20261028/
--
-- 적용 대상 (2026-10-28 실측 기준 DB가 뒤처져 있던 항목)
--   1. dcat_dataset_relation UNIQUE에 method 추가 + method CHECK
--   2. 정본 뷰 dcat_dataset_relation_canonical 생성
--   3. dcat_dataset 인덱스 4종 추가 (keywords·party·periodicity·temporal)
--   4. JSONB/언어 컬럼 NOT NULL 전환
--
-- 모두 가산·완화 방향이며 데이터를 지우지 않는다.
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. 관계 테이블 — method 단위 보관 ────────────────────────
-- 원안은 쌍+유형당 1행이라 같은 쌍·유형에 규칙 산출과 모델 산출을 함께 둘 수 없었다.
-- 모비젠 제안 → 와이즈넛 수락(2026-10-28). 재계산은 method 단위로 한다.
ALTER TABLE dcat_dataset_relation
    DROP CONSTRAINT IF EXISTS dcat_dataset_relation_source_dataset_id_target_dataset_id_r_key,
    DROP CONSTRAINT IF EXISTS dcat_dataset_relation_pair_type_method_key,
    ADD  CONSTRAINT dcat_dataset_relation_pair_type_method_key
         UNIQUE (source_dataset_id, target_dataset_id, relation_type, method),
    DROP CONSTRAINT IF EXISTS dcat_dataset_relation_method_check,
    ADD  CONSTRAINT dcat_dataset_relation_method_check
         CHECK (method IN ('rule', 'embedding', 'llm', 'gnn'));

-- ── 2. 정본 뷰 ────────────────────────────────────────────────
-- 한 쌍·한 유형에 method별로 행이 여러 개가 되므로, 무엇을 정답으로 볼지를 뷰로 고정한다.
-- 조회하는 쪽은 테이블이 아니라 이 뷰를 읽는다.
DROP VIEW IF EXISTS dcat_dataset_relation_canonical;
CREATE VIEW dcat_dataset_relation_canonical AS
SELECT DISTINCT ON (source_dataset_id, target_dataset_id, relation_type) *
FROM dcat_dataset_relation
ORDER BY source_dataset_id, target_dataset_id, relation_type,
         (status = 'APPROVED') DESC, score DESC, created_at DESC;

-- ── 3. 와이즈넛 DDL에 있으나 우리 DB에 없던 인덱스 ───────────
-- keywords GIN이 없으면 KEYWORD_OVERLAP 판정이 전부 순차 스캔이 된다.
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_keywords    ON dcat_dataset USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_party       ON dcat_dataset (party);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_periodicity ON dcat_dataset (accrual_periodicity);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_temporal    ON dcat_dataset (temporal_start, temporal_end);

-- ── 4. NOT NULL 전환 ─────────────────────────────────────────
-- JSONB 배열에 NULL과 빈 배열 두 가지 "없음"이 생기면 조회가 조용히 틀어진다.
-- 예) keywords가 NULL인 행에서 `keywords ? '인공지능'`은 TRUE도 FALSE도 아닌 NULL을
--     반환해 결과에서 말없이 빠진다. 2026-10-28 기준 keywords 11건, theme 18건이 NULL이었다.
-- 코드 영향 없음 확인: jsonld_export·embed_datasets 모두 `or []` 패턴을 쓰고,
-- NULL로 분기하는 코드는 없다(파이프라인은 keywords가 아니라 subjects를 쓴다).
UPDATE dcat_dataset SET keywords     = '[]'::jsonb WHERE keywords     IS NULL;
UPDATE dcat_dataset SET theme        = '[]'::jsonb WHERE theme        IS NULL;
UPDATE dcat_dataset SET external_ids = '[]'::jsonb WHERE external_ids IS NULL;
UPDATE dcat_dataset SET language     = 'ko'        WHERE language     IS NULL;

ALTER TABLE dcat_dataset
    ALTER COLUMN keywords     SET DEFAULT '[]'::jsonb,
    ALTER COLUMN keywords     SET NOT NULL,
    ALTER COLUMN theme        SET DEFAULT '[]'::jsonb,
    ALTER COLUMN theme        SET NOT NULL,
    ALTER COLUMN external_ids SET DEFAULT '[]'::jsonb,
    ALTER COLUMN external_ids SET NOT NULL,
    ALTER COLUMN language     SET NOT NULL;

COMMIT;

-- ── 적용 후 확인 ─────────────────────────────────────────────
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conrelid='dcat_dataset_relation'::regclass;
-- SELECT viewname FROM pg_views WHERE viewname='dcat_dataset_relation_canonical';
-- SELECT indexname FROM pg_indexes WHERE tablename='dcat_dataset' ORDER BY 1;
