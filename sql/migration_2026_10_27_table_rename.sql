-- ═══════════════════════════════════════════════════════════════
-- migration_2026_10_27_table_rename.sql
--
-- 테이블명에서 벤더명을 제거하고 source_type과 일치시킨다.
--   meta_{source_type} / active_meta_{source_type} 규칙으로 통일
--   → 테이블명을 source_type에서 코드로 유도할 수 있다
--     (A1 수집 어댑터화·C3 템플릿 파이프라인에서 매핑 테이블이 불필요해진다)
--
-- 수집기·파이프라인(naver_*_collector.py, youtube_pipeline.py 등)은 이름을 유지한다.
-- 실제로 벤더 API에 묶여 있으므로 벤더명이 맞다.
--   데이터 계층 = source_type 기준 / 수집 계층 = 벤더 기준
--
-- ⚠️ 코드와 함께 적용해야 한다. 저장소는 이미 새 이름으로 바뀌어 있어
--    이 스크립트를 적용하기 전에는 파이프라인이 동작하지 않는다.
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. 뷰 제거 (테이블에 의존하므로 선행) ────────────────────
-- 개명 후 sql/views.sql을 재실행해 새 이름으로 다시 만든다
DROP VIEW IF EXISTS v_meta_naver_blog_latest CASCADE;
DROP VIEW IF EXISTS v_meta_naver_news_latest CASCADE;
DROP VIEW IF EXISTS v_meta_naver_persona_latest CASCADE;
DROP VIEW IF EXISTS v_meta_naver_shopping_latest CASCADE;
DROP VIEW IF EXISTS v_meta_youtube_latest CASCADE;

-- ── 2. 테이블 개명 ───────────────────────────────────────────
ALTER TABLE meta_youtube_video RENAME TO meta_video;
ALTER TABLE meta_youtube_video_vec RENAME TO meta_video_vec;
ALTER TABLE active_meta_youtube RENAME TO active_meta_video;
ALTER TABLE meta_naver_news RENAME TO meta_news;
ALTER TABLE meta_naver_news_vec RENAME TO meta_news_vec;
ALTER TABLE active_meta_naver_news RENAME TO active_meta_news;
ALTER TABLE meta_naver_blog RENAME TO meta_blog;
ALTER TABLE meta_naver_blog_vec RENAME TO meta_blog_vec;
ALTER TABLE active_meta_naver_blog RENAME TO active_meta_blog;
ALTER TABLE meta_naver_shopping RENAME TO meta_shopping_insight;
ALTER TABLE active_meta_naver_shopping RENAME TO active_meta_shopping_insight;
ALTER TABLE meta_naver_persona RENAME TO meta_persona_insight;
ALTER TABLE active_meta_naver_persona RENAME TO active_meta_persona_insight;

-- ── 3. 인덱스 개명 ───────────────────────────────────────────
ALTER INDEX active_meta_naver_blog_meta_id_collected_at_key RENAME TO active_meta_blog_meta_id_collected_at_key;
ALTER INDEX active_meta_naver_blog_pkey RENAME TO active_meta_blog_pkey;
ALTER INDEX active_meta_naver_news_meta_id_collected_at_key RENAME TO active_meta_news_meta_id_collected_at_key;
ALTER INDEX active_meta_naver_news_pkey RENAME TO active_meta_news_pkey;
ALTER INDEX active_meta_naver_persona_meta_id_period_gender_age_key RENAME TO active_meta_persona_insight_meta_id_period_gender_age_key;
ALTER INDEX active_meta_naver_persona_pkey RENAME TO active_meta_persona_insight_pkey;
ALTER INDEX active_meta_naver_shopping_meta_id_period_gender_age_key RENAME TO active_meta_shopping_insight_meta_id_period_gender_age_key;
ALTER INDEX active_meta_naver_shopping_pkey RENAME TO active_meta_shopping_insight_pkey;
ALTER INDEX active_meta_youtube_meta_id_collected_at_key RENAME TO active_meta_video_meta_id_collected_at_key;
ALTER INDEX active_meta_youtube_pkey RENAME TO active_meta_video_pkey;
ALTER INDEX meta_naver_blog_dataset_id_post_url_key RENAME TO meta_blog_dataset_id_post_url_key;
ALTER INDEX meta_naver_blog_pkey RENAME TO meta_blog_pkey;
ALTER INDEX meta_naver_blog_vec_pkey RENAME TO meta_blog_vec_pkey;
ALTER INDEX meta_naver_news_dataset_id_article_url_key RENAME TO meta_news_dataset_id_article_url_key;
ALTER INDEX meta_naver_news_pkey RENAME TO meta_news_pkey;
ALTER INDEX meta_naver_news_vec_pkey RENAME TO meta_news_vec_pkey;
ALTER INDEX meta_naver_persona_dataset_id_category_id_key RENAME TO meta_persona_insight_dataset_id_category_id_key;
ALTER INDEX meta_naver_persona_pkey RENAME TO meta_persona_insight_pkey;
ALTER INDEX meta_naver_shopping_dataset_id_category_id_key RENAME TO meta_shopping_insight_dataset_id_category_id_key;
ALTER INDEX meta_naver_shopping_pkey RENAME TO meta_shopping_insight_pkey;
ALTER INDEX meta_youtube_video_dataset_id_video_id_key RENAME TO meta_video_dataset_id_video_id_key;
ALTER INDEX meta_youtube_video_pkey RENAME TO meta_video_pkey;
ALTER INDEX meta_youtube_video_vec_pkey RENAME TO meta_video_vec_pkey;

-- ── 4. 제약 개명 (FK·CHECK만) ────────────────────────────────
-- PK·UNIQUE 제약은 뒷받침 인덱스와 이름을 공유한다. 3단계의 ALTER INDEX가
-- 제약 이름까지 함께 바꾸므로 여기서 다시 건드리면 "제약이 없다" 오류가 난다.
ALTER TABLE active_meta_blog RENAME CONSTRAINT active_meta_naver_blog_meta_id_fkey TO active_meta_blog_meta_id_fkey;
ALTER TABLE active_meta_news RENAME CONSTRAINT active_meta_naver_news_meta_id_fkey TO active_meta_news_meta_id_fkey;
ALTER TABLE active_meta_persona_insight RENAME CONSTRAINT active_meta_naver_persona_meta_id_fkey TO active_meta_persona_insight_meta_id_fkey;
ALTER TABLE active_meta_shopping_insight RENAME CONSTRAINT active_meta_naver_shopping_meta_id_fkey TO active_meta_shopping_insight_meta_id_fkey;
ALTER TABLE active_meta_video RENAME CONSTRAINT active_meta_youtube_meta_id_fkey TO active_meta_video_meta_id_fkey;
ALTER TABLE meta_blog RENAME CONSTRAINT meta_naver_blog_dataset_id_fkey TO meta_blog_dataset_id_fkey;
ALTER TABLE meta_blog_vec RENAME CONSTRAINT meta_naver_blog_vec_meta_id_fkey TO meta_blog_vec_meta_id_fkey;
ALTER TABLE meta_news RENAME CONSTRAINT meta_naver_news_dataset_id_fkey TO meta_news_dataset_id_fkey;
ALTER TABLE meta_news_vec RENAME CONSTRAINT meta_naver_news_vec_meta_id_fkey TO meta_news_vec_meta_id_fkey;
ALTER TABLE meta_persona_insight RENAME CONSTRAINT meta_naver_persona_dataset_id_fkey TO meta_persona_insight_dataset_id_fkey;
ALTER TABLE meta_shopping_insight RENAME CONSTRAINT meta_naver_shopping_dataset_id_fkey TO meta_shopping_insight_dataset_id_fkey;
ALTER TABLE meta_video RENAME CONSTRAINT meta_youtube_video_dataset_id_fkey TO meta_video_dataset_id_fkey;
ALTER TABLE meta_video_vec RENAME CONSTRAINT meta_youtube_video_vec_meta_id_fkey TO meta_video_vec_meta_id_fkey;

-- ── 5. 시퀀스 개명 ───────────────────────────────────────────
ALTER SEQUENCE active_meta_naver_blog_id_seq RENAME TO active_meta_blog_id_seq;
ALTER SEQUENCE active_meta_naver_news_id_seq RENAME TO active_meta_news_id_seq;
ALTER SEQUENCE active_meta_naver_persona_id_seq RENAME TO active_meta_persona_insight_id_seq;
ALTER SEQUENCE active_meta_naver_shopping_id_seq RENAME TO active_meta_shopping_insight_id_seq;
ALTER SEQUENCE active_meta_youtube_id_seq RENAME TO active_meta_video_id_seq;
ALTER SEQUENCE meta_naver_blog_id_seq RENAME TO meta_blog_id_seq;
ALTER SEQUENCE meta_naver_news_id_seq RENAME TO meta_news_id_seq;
ALTER SEQUENCE meta_naver_persona_id_seq RENAME TO meta_persona_insight_id_seq;
ALTER SEQUENCE meta_naver_shopping_id_seq RENAME TO meta_shopping_insight_id_seq;
ALTER SEQUENCE meta_youtube_video_id_seq RENAME TO meta_video_id_seq;

-- ── 6. data_registry 값 갱신 ─────────────────────────────────
-- pg_meta_table / pg_active_table에 테이블명이 문자열로 들어 있어 FK가 전파하지 않는다
UPDATE data_registry SET pg_meta_table   = 'meta_video' WHERE pg_meta_table   = 'meta_youtube_video';
UPDATE data_registry SET pg_active_table = 'meta_video' WHERE pg_active_table = 'meta_youtube_video';
UPDATE data_registry SET pg_meta_table   = 'meta_video_vec' WHERE pg_meta_table   = 'meta_youtube_video_vec';
UPDATE data_registry SET pg_active_table = 'meta_video_vec' WHERE pg_active_table = 'meta_youtube_video_vec';
UPDATE data_registry SET pg_meta_table   = 'active_meta_video' WHERE pg_meta_table   = 'active_meta_youtube';
UPDATE data_registry SET pg_active_table = 'active_meta_video' WHERE pg_active_table = 'active_meta_youtube';
UPDATE data_registry SET pg_meta_table   = 'meta_news' WHERE pg_meta_table   = 'meta_naver_news';
UPDATE data_registry SET pg_active_table = 'meta_news' WHERE pg_active_table = 'meta_naver_news';
UPDATE data_registry SET pg_meta_table   = 'meta_news_vec' WHERE pg_meta_table   = 'meta_naver_news_vec';
UPDATE data_registry SET pg_active_table = 'meta_news_vec' WHERE pg_active_table = 'meta_naver_news_vec';
UPDATE data_registry SET pg_meta_table   = 'active_meta_news' WHERE pg_meta_table   = 'active_meta_naver_news';
UPDATE data_registry SET pg_active_table = 'active_meta_news' WHERE pg_active_table = 'active_meta_naver_news';
UPDATE data_registry SET pg_meta_table   = 'meta_blog' WHERE pg_meta_table   = 'meta_naver_blog';
UPDATE data_registry SET pg_active_table = 'meta_blog' WHERE pg_active_table = 'meta_naver_blog';
UPDATE data_registry SET pg_meta_table   = 'meta_blog_vec' WHERE pg_meta_table   = 'meta_naver_blog_vec';
UPDATE data_registry SET pg_active_table = 'meta_blog_vec' WHERE pg_active_table = 'meta_naver_blog_vec';
UPDATE data_registry SET pg_meta_table   = 'active_meta_blog' WHERE pg_meta_table   = 'active_meta_naver_blog';
UPDATE data_registry SET pg_active_table = 'active_meta_blog' WHERE pg_active_table = 'active_meta_naver_blog';
UPDATE data_registry SET pg_meta_table   = 'meta_shopping_insight' WHERE pg_meta_table   = 'meta_naver_shopping';
UPDATE data_registry SET pg_active_table = 'meta_shopping_insight' WHERE pg_active_table = 'meta_naver_shopping';
UPDATE data_registry SET pg_meta_table   = 'active_meta_shopping_insight' WHERE pg_meta_table   = 'active_meta_naver_shopping';
UPDATE data_registry SET pg_active_table = 'active_meta_shopping_insight' WHERE pg_active_table = 'active_meta_naver_shopping';
UPDATE data_registry SET pg_meta_table   = 'meta_persona_insight' WHERE pg_meta_table   = 'meta_naver_persona';
UPDATE data_registry SET pg_active_table = 'meta_persona_insight' WHERE pg_active_table = 'meta_naver_persona';
UPDATE data_registry SET pg_meta_table   = 'active_meta_persona_insight' WHERE pg_meta_table   = 'active_meta_naver_persona';
UPDATE data_registry SET pg_active_table = 'active_meta_persona_insight' WHERE pg_active_table = 'active_meta_naver_persona';

COMMIT;

-- ── 7. 뷰 재생성 ─────────────────────────────────────────────
-- psql -f sql/views.sql  (이미 새 이름으로 갱신돼 있다)

-- ── 8. 적용 후 확인 ──────────────────────────────────────────
-- SELECT pg_meta_table, pg_active_table FROM data_registry ORDER BY 1;
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'meta%' ORDER BY 1;
