-- ============================================================================
-- 원천 스키마 드리프트 감지용 컬럼 추가 (C4 최소선 완료 기준)
--
-- 배경 : C4 완료 기준은 둘이다 —
--          (1) 등록만으로 주기 수집이 자동 수행됨   → scripts/scheduler_tick.py (2026-11-02)
--          (2) **소스 스키마 변경이 자동 감지·기록됨** → 이 마이그레이션
--
--        우리 어댑터 스펙(configs/sources/*.yaml)은 원천 응답의 경로를
--        `fields: {title: snippet.title}` 처럼 **문자열로** 박아 둔다.
--        원천이 그 경로를 바꾸거나 없애면 `dig()`가 None을 돌려주고,
--        **오류 없이** 해당 컬럼이 NULL로 들어간다. 수집은 "성공"으로 끝난다.
--        그래서 사람이 알아채는 시점이 "검색 결과가 이상한데?"가 된다.
--
-- 방식 : 수집한 원본 레코드의 **필드 경로 집합**을 정렬·해시해 보관하고,
--        다음 수집 때 비교한다. 자세한 규격은 src/pipeline_engine/drift.py.
--
-- 영향 : data_registry 25행. 전부 **NULL 허용·기본값 없음**이라
--        PostgreSQL 11+ 에서 테이블 재작성이 없다(메타데이터만 변경).
--        되돌리려면 DROP COLUMN 네 번이면 된다.
--
-- 이름 : 계획서(NEXT_STEPS C4)에는 `schema_changed_at`으로 적혀 있으나
--        `source_schema_*`로 둔다. 이 테이블에서 "schema"만 쓰면
--        **우리 DB 스키마**로 읽힌다 — 여기 담기는 것은 원천 응답의 모양이다.
--
-- 트랜잭션 안에서 실행하고 §C 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

BEGIN;

-- ── A. 컬럼 추가 ────────────────────────────────────────────────────────────

ALTER TABLE data_registry
    ADD COLUMN source_schema_fingerprint TEXT,
    -- 핵심 필드 경로 집합의 SHA-256(hex). 이 값이 달라지면 원천 모양이 바뀐 것이다

    ADD COLUMN source_schema_fields      JSONB,
    -- 그 지문의 원재료 — 정렬된 경로 배열. 지문만 있으면 "바뀌었다"까지만 알고
    -- **무엇이** 바뀌었는지는 모른다. 차이를 짚으려면 직전 집합이 있어야 한다
    -- 예) ["description","link","originallink","pubDate","title"]

    ADD COLUMN source_schema_checked_at  TIMESTAMPTZ,
    -- 마지막으로 **검사한** 시각. 변경이 없어도 갱신된다.
    -- 이게 오래 멈춰 있으면 감지기 자체가 안 도는 것이다(조용한 실패 방지)

    ADD COLUMN source_schema_changed_at  TIMESTAMPTZ;
    -- 마지막으로 **달라진** 시각. 변경이 있을 때만 갱신된다

-- ── B. 인덱스 ───────────────────────────────────────────────────────────────
-- 25행짜리 테이블이라 조회 성능 때문이 아니다. "최근 바뀐 원천"을 운영 화면에서
-- 뽑는 질의가 고정이라 넣어 둔다. NULL(한 번도 안 바뀜)은 색인에서 뺀다.

CREATE INDEX idx_data_registry_schema_changed
    ON data_registry (source_schema_changed_at DESC)
    WHERE source_schema_changed_at IS NOT NULL;

-- ── C. 검증 ─────────────────────────────────────────────────────────────────
-- 1) 컬럼 4종이 생겼는가 (기대: 4행, 전부 is_nullable=YES)
SELECT column_name, data_type, is_nullable
FROM   information_schema.columns
WHERE  table_name = 'data_registry'
  AND  column_name LIKE 'source_schema_%'
ORDER  BY column_name;

-- 2) 기존 25행이 그대로이고 새 컬럼은 전부 NULL인가
SELECT count(*) AS rows,
       count(source_schema_fingerprint) AS fingerprinted
FROM   data_registry;

-- 3) 부분 인덱스가 생겼는가 (기대: 1행)
SELECT indexname FROM pg_indexes WHERE indexname = 'idx_data_registry_schema_changed';

COMMIT;
