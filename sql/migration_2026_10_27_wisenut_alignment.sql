-- ═══════════════════════════════════════════════════════════════
-- migration_2026_10_27_wisenut_alignment.sql
--
-- 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서에 dcat_dataset을 맞춘다.
--
-- 왜 DROP → CREATE가 아니라 ALTER인가
--   sql/*.sql은 개발 단계 규칙상 DROP → CREATE 형식을 유지한다(파일이 정본).
--   그러나 2026-10-27 현재 DB에는 재생성 비용이 큰 데이터가 쌓여 있다.
--     meta_video 29,026행      → 재수집 시 YouTube API 쿼터 대량 소모
--     active_meta_video 32,540행     → 과거 시점 관측값은 재수집으로 복원 불가
--     active_meta_shopping_insight 72,914행 (601일치) → 현재 유일한 실제 시계열
--   dcat_dataset을 DROP하면 CASCADE로 위가 전부 삭제된다.
--   또한 dataset_id URN 전환이 예정돼 있어, 지금 재구축하면 두 번 버리게 된다.
--   → 전면 재구축은 URN 규칙 확정 시 seeds.sql 갱신과 함께 한 번에 수행한다.
--
-- 적용 전 확인
--   - 이 DB는 와이즈넛과 공유한다. 적용 시점을 사전에 공유할 것
--   - 모두 가산(ADD COLUMN)이며 기존 컬럼을 변경·삭제하지 않는다
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. dcat_dataset 신규 컬럼 ─────────────────────────────────
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS source         TEXT;
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS publisher_code TEXT;
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS theme          JSONB;
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS external_ids   JSONB;
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS party          TEXT;
ALTER TABLE dcat_dataset ADD COLUMN IF NOT EXISTS visibility     TEXT NOT NULL DEFAULT 'ORG';
-- visibility 기본값을 ORG로 두는 이유: PUBLIC을 기본으로 하면 등록 실수가 곧 외부 공개가 된다.

-- 분류 저장은 theme 하나로 통일한다 (2026-10-27 결정).
-- category(jsonb NOT NULL, 18건 전부 빈 배열)는 용도가 겹치므로 신규 적재하지 않는다.
-- 별첨에 없고 DB에만 있던 컬럼이라 우리가 단독으로 DROP하지 않고 와이즈넛 확인 후 제거한다.

-- ── 2. backfill ───────────────────────────────────────────────
-- 비정형은 source = publisher 원천값을 사용한다 (모비젠 회신 의견)
UPDATE dcat_dataset SET source = publisher WHERE source IS NULL;

-- 기존 slug를 external_ids에 보존한다 — URN 전환 후 추적 경로가 된다.
-- 와이즈넛 형식('네임스페이스:값' 문자열 배열)을 그대로 지키고 자체 네임스페이스를 쓴다.
--   예) ["legacy:youtube_samsung_official"]
-- 포털 번호와 섞이지 않고, 값이 데이터셋마다 유일해 중복 병합 판정에 오탐을 만들지 않는다.
UPDATE dcat_dataset
   SET external_ids = jsonb_build_array('legacy:' || dataset_id)
 WHERE external_ids IS NULL;

ALTER TABLE dcat_dataset ALTER COLUMN source SET NOT NULL;

-- ── 3. 인덱스 ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_source       ON dcat_dataset (source);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_visibility   ON dcat_dataset (visibility);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_external_ids ON dcat_dataset USING GIN (external_ids);
CREATE INDEX IF NOT EXISTS idx_dcat_dataset_theme        ON dcat_dataset USING GIN (theme);

-- ── 4. dcat_provenance 연쇄 삭제 제외 (2026-10-27 확정) ──────
--
-- 별첨 공통 규약: "전 자식 테이블 ON DELETE CASCADE (dcat_provenance 제외)"
-- 데이터셋을 폐기해도 수집 이력은 남긴다. CASCADE만 빼면 FK가 부모 삭제를 막으므로
-- FK 자체를 제거하고 값만 보존한다 — SET NULL은 "무엇에 대한 이력인가"를 잃는다.
--
-- 수집 스케줄은 data_registry.next_collect_at으로 돌아가고 dcat_provenance는
-- 이력 전용이므로, FK가 없어도 수집 동작에는 영향이 없다.

ALTER TABLE dcat_provenance DROP CONSTRAINT IF EXISTS dcat_provenance_dataset_id_fkey;

COMMENT ON COLUMN dcat_provenance.dataset_id IS
  'dcat_dataset 논리 참조. 데이터셋 폐기 후에도 이력 보존을 위해 FK를 두지 않는다';

-- FK 인덱스가 사라지므로 데이터셋별 이력 조회용 인덱스를 명시적으로 둔다
CREATE INDEX IF NOT EXISTS idx_dcat_provenance_dataset
    ON dcat_provenance (dataset_id, started_at DESC);

COMMIT;


-- ═══════════════════════════════════════════════════════════════
-- 이하는 합의 대기 — 확정 전까지 실행하지 않는다
-- ═══════════════════════════════════════════════════════════════

-- ── A. dataset_id URN 전환 대비: 우리 FK에 ON UPDATE CASCADE 부여 ──
--
-- 와이즈넛이 만든 테이블(dcat_dataset_attr, active_meta_dataset, dcat_dataset_relation,
-- meta_datagokr_file)의 FK에는 이미 ON UPDATE CASCADE가 걸려 있어 dataset_id 변경이
-- 자동 전파된다. 반면 우리 테이블은 NO ACTION이라 전파되지 않는다.
-- 아래를 적용해 두면 URN 전환이 UPDATE 한 번으로 끝난다.
--
-- ALTER TABLE data_registry       DROP CONSTRAINT data_registry_dataset_id_fkey,
--   ADD CONSTRAINT data_registry_dataset_id_fkey FOREIGN KEY (dataset_id)
--   REFERENCES dcat_dataset(dataset_id) ON UPDATE CASCADE ON DELETE CASCADE;
-- ALTER TABLE dcat_dataset_vec    DROP CONSTRAINT dcat_dataset_vec_dataset_id_fkey, ...
-- ALTER TABLE dataset_credentials DROP CONSTRAINT dataset_credentials_dataset_id_fkey, ...
-- ALTER TABLE meta_video  DROP CONSTRAINT meta_video_dataset_id_fkey, ...
-- ALTER TABLE meta_news     ...
-- ALTER TABLE meta_blog     ...
-- ALTER TABLE meta_shopping_insight ...
-- ALTER TABLE meta_persona_insight  ...
--
-- 주의: FK가 전파해도 아래는 따로 처리해야 한다.
--   - SeaweedFS 오브젝트 키 (raw/{source_type}/{dataset_id}/, jsonld/.../{dataset_id}.jsonld)
--   - 이미 생성된 JSON-LD 문서의 @id
--   - data_registry.s3_raw_prefix / s3_jsonld_prefix 문자열
--   - 케이웨어가 이미 우리 dataset_id를 받아갔다면 변경 통보
-- ── B. dcat_dataset_relation UNIQUE 확장 ─────────────────────
--
-- 규칙 산출 엣지와 모델 산출 엣지를 같은 쌍·같은 유형에 공존시키기 위한 변경.
-- 제안 내용과 함께 합의해야 할 3가지(UPSERT 충돌 대상·정본 우선순위·method 값 통제)는
-- sql/dcat_dataset_relation.sql 하단 주석 참조.
--
-- ALTER TABLE dcat_dataset_relation
--     DROP CONSTRAINT dcat_dataset_relation_source_dataset_id_target_dataset_id_r_key,
--     ADD  CONSTRAINT uq_dcat_dataset_relation
--          UNIQUE (source_dataset_id, target_dataset_id, relation_type, method);
