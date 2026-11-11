-- ═══════════════════════════════════════════════════════════════
-- 2026-11-11 활용 기록 테이블 신설 — dataset_usage_event
--
-- 정본: sql/dataset_usage_event.sql (이 파일은 운영 DB 적용용, DROP 없음)
-- 결정 3(2026-11-05): 활용 기록(조회·내려받기)을 모비젠이 먼저 만든다.
--
-- 영향: 새 테이블만 만든다. 공용 테이블(dcat_dataset 등)의 구조는 바꾸지 않는다(ADR-014).
--   dcat_dataset을 참조하는 FK를 거는 동안 dcat_dataset에 짧게 SHARE ROW EXCLUSIVE 잠금이 잡힌다
--   (읽기는 막지 않고, 같은 순간의 쓰기만 잠깐 기다린다). lock_timeout으로 오래 기다리지 않게 한다.
-- 되돌리기: DROP TABLE dataset_usage_event;  (다른 테이블이 이 테이블을 참조하지 않는다)
-- ═══════════════════════════════════════════════════════════════
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS dataset_usage_event (
    id            BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type    TEXT NOT NULL,
    dataset_id    TEXT NOT NULL REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    item_id       TEXT,
    detail        TEXT,
    user_id       TEXT,
    session_hash  TEXT,
    origin        TEXT NOT NULL DEFAULT 'portal'
);

CREATE INDEX IF NOT EXISTS idx_dataset_usage_event_dataset ON dataset_usage_event (dataset_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_dataset_usage_event_time    ON dataset_usage_event (occurred_at DESC);

COMMENT ON TABLE dataset_usage_event IS
    '데이터셋 활용 기록(조회·내려받기). IP·UA·검색어 미저장, 비로그인은 세션 해시만. 결정 3(2026-11-05)';

COMMIT;
