-- ============================================================================
-- 공통 분류를 자동 확정에서 추천으로 — [ADR-020](../docs/adr/020_Category_Suggestion_Not_Assignment.md)
--
-- 배경 : 수집 파이프라인이 `category`를 매번 자동으로 덮어쓰고 있었다.
--        2026-11-02 전수 확인에서 자동 확정을 지탱할 근거가 없음이 드러났다.
--
--          HBM 뉴스 상위 5개 유사도 0.8186 ~ 0.8116 (폭 0.042)
--          1위 `문화 > 방송·미디어`  ← 저장됨
--          3위 `기술 > 정보·통신`    ← 사람이 보면 이것
--
--        1위와 3위 차이가 0.0055로 잡음 수준이고, MIN_SIMILARITY=0.0이라
--        아무것도 걸러지지 않는다. 어휘 유사도에도 끌린다 —
--        `치질`이 "치" 한 글자로 `의료 > 치의학`에, `화장품`이 `의료 > 의약품`에 붙었다.
--
--        더 근본적으로, 분류 76종은 학술·공공 체계라 **소비재 영역이 없다.**
--        패션·화장품·식품·디지털가전은 무엇을 골라도 틀린다.
--
-- 변경 : `category_source`를 추가해 **누가 정했는지**를 구분한다.
--        기존 25건은 전부 자동 부여분이므로 'auto'로 표시한다.
--        값을 지우지는 않는다 — 사람이 확인해 고칠 때까지 잠정값으로 남긴다.
--
-- ⚠️ 이 마이그레이션은 **데이터를 지우지 않는다.** 다만 적용 후부터
--    수집 파이프라인이 `category`를 덮어쓰지 않고, 추천만
--    `meta_feature(feature_name='suggested_category')`에 쌓는다.
--
-- 트랜잭션 안에서 실행하고 §C 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

BEGIN;

-- ── A. 컬럼 추가 ────────────────────────────────────────────────────────────
ALTER TABLE dcat_dataset
    ADD COLUMN category_source TEXT
        CHECK (category_source IN ('user', 'auto'));
-- 'user' : 사람이 등록·수정 화면에서 고른 값. **자동으로 덮어쓰지 않는다**
-- 'auto' : 분류기가 넣은 잠정값. 사람이 확인하기 전까지의 상태
-- NULL   : 분류 없음. 체계에 맞는 라벨이 없으면 이 상태가 정상이다
--          (억지 분류보다 빈 분류가 낫다 — ADR-020)

-- ── B. 기존 값 표시 ─────────────────────────────────────────────────────────
-- 지금 채워진 25건은 전부 자동 부여분이다. 사람이 고른 것은 하나도 없다.
UPDATE dcat_dataset
   SET category_source = 'auto'
 WHERE category IS NOT NULL
   AND jsonb_array_length(category) > 0;

-- ── C. 검증 ─────────────────────────────────────────────────────────────────
-- 1) 컬럼이 생기고 CHECK가 걸렸는가
SELECT column_name, is_nullable FROM information_schema.columns
WHERE  table_name = 'dcat_dataset' AND column_name = 'category_source';

-- 2) 분류가 있는 행은 전부 출처가 표시됐는가 (기대: 불일치 0)
SELECT count(*) FILTER (WHERE jsonb_array_length(category) > 0
                          AND category_source IS NULL) AS 출처없는_분류,
       count(*) FILTER (WHERE category_source = 'auto') AS 자동부여,
       count(*) FILTER (WHERE category_source = 'user') AS 사람확정
FROM   dcat_dataset;

COMMIT;
