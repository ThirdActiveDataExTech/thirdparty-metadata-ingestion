-- ============================================================================
-- 벡터 테이블 청킹 구조 전환 (1:1 → 1:N) + 샘플 데이터 정리
--
-- 배경 : 2026-10-28 임베딩 33,903건을 만들었으나 **검색이 동작하지 않았다.**
--        모델(paraphrase-multilingual-mpnet-base-v2)은 문장쌍 패러프레이즈용이라
--        짧은 질의 ↔ 긴 문서 비대칭 비교에서 유사도가 무너진다.
--
--          질의 "위암 수술 후 관리"
--            문서 앞 10자 (= 질의와 동일)                cos 1.0000
--            문서 앞 40자 (+ "김희성 교수 / 서울아산병원")  cos 0.0292  ← 무너짐
--            무관한 문장 ("고양이 사진")                   cos 0.0832
--
--        제목이 글자까지 같은 영상이 29,029건 중 17,449위였다.
--        문장/줄 단위로 쪼개 청크별로 임베딩하고 검색에서 청크 최대 유사도를
--        쓰면 정답이 1위로 올라온다(실측 1.0000).
--
-- 구조 : PK가 meta_id → (meta_id, chunk_index)로 바뀐다.
--        ADR-014에 따라 정본 DDL(sql/*_vec.sql)을 함께 고쳤다.
--        와이즈넛 정형은 이 테이블들을 쓰지 않는다(비정형 전용).
--
-- 데이터: 샘플 데이터를 전부 비우고 실제 수집으로 다시 채운다(사용자 지시).
--        ⚠️ 아래 5개 테이블은 **보존한다** —
--           catalog_entry / column_relation / metadata_entry
--           metric_registry / relation_type_registry
--        앞의 셋은 v0.1 레거시, 뒤의 둘은 와이즈넛 합의 표준값 시드다.
--
-- 백업 : 삭제 전 전체 197,517행을 CSV로 받아 두었다.
--
-- 트랜잭션 안에서 실행하고 §C 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. 데이터 정리 ──────────────────────────────────────────────────────────
-- dcat_dataset을 지우면 FK CASCADE로 자식이 전부 따라간다.
-- dcat_provenance는 FK가 없어(이력 보존 목적) 별도로 지운다.
DELETE FROM dcat_provenance;
DELETE FROM dcat_dataset;

-- CASCADE가 닿지 않는 곳이 없는지 확인차 남은 것을 비운다(정상이면 0행 영향)
DELETE FROM active_meta_dataset;
DELETE FROM active_meta_file;
DELETE FROM dcat_dataset_draft;
DELETE FROM meta_file_relation;


-- ── B. 벡터 테이블 재생성 (1:1 → 1:N) ───────────────────────────────────────
-- 기존 벡터는 전부 버린다. 청킹 전 구조로 만든 값이라 쓸 수 없다.

DROP TABLE IF EXISTS dcat_dataset_vec CASCADE;
CREATE TABLE dcat_dataset_vec (
    dataset_id   TEXT NOT NULL
                 REFERENCES dcat_dataset(dataset_id) ON UPDATE CASCADE ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    embedding    vector(768) NOT NULL,
    embed_text   TEXT NOT NULL,
    model_name   TEXT NOT NULL
                 DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    embedded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, chunk_index)
);
CREATE INDEX idx_dcat_dataset_vec_dataset ON dcat_dataset_vec (dataset_id);

DROP TABLE IF EXISTS meta_video_vec CASCADE;
CREATE TABLE meta_video_vec (
    meta_id     BIGINT NOT NULL REFERENCES meta_video(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    embedding   vector(768) NOT NULL,
    embed_text  TEXT NOT NULL,
    model_name  TEXT NOT NULL
                DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_id, chunk_index)
);
CREATE INDEX idx_meta_video_vec_meta ON meta_video_vec (meta_id);

DROP TABLE IF EXISTS meta_news_vec CASCADE;
CREATE TABLE meta_news_vec (
    meta_id     BIGINT NOT NULL REFERENCES meta_news(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    embedding   vector(768) NOT NULL,
    embed_text  TEXT NOT NULL,
    model_name  TEXT NOT NULL
                DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_id, chunk_index)
);
CREATE INDEX idx_meta_news_vec_meta ON meta_news_vec (meta_id);

DROP TABLE IF EXISTS meta_blog_vec CASCADE;
CREATE TABLE meta_blog_vec (
    meta_id     BIGINT NOT NULL REFERENCES meta_blog(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    embedding   vector(768) NOT NULL,
    embed_text  TEXT NOT NULL,
    model_name  TEXT NOT NULL
                DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (meta_id, chunk_index)
);
CREATE INDEX idx_meta_blog_vec_meta ON meta_blog_vec (meta_id);


-- ── C. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- C-1. 보존 대상 5개 테이블이 그대로인가 (이게 틀리면 즉시 롤백해야 한다)
    SELECT string_agg(t || '=' || c, ', ') INTO txt FROM (
        SELECT 'catalog_entry' t, count(*) c FROM catalog_entry
        UNION ALL SELECT 'column_relation', count(*) FROM column_relation
        UNION ALL SELECT 'metadata_entry', count(*) FROM metadata_entry
        UNION ALL SELECT 'metric_registry', count(*) FROM metric_registry
        UNION ALL SELECT 'relation_type_registry', count(*) FROM relation_type_registry
    ) s WHERE c = 0;
    IF txt IS NOT NULL THEN
        RAISE EXCEPTION 'C-1 실패: 보존 대상이 비었다 — %', txt;
    END IF;

    -- C-2. 수집 데이터는 전부 비었는가
    SELECT string_agg(t || '=' || c, ', ') INTO txt FROM (
        SELECT 'dcat_dataset' t, count(*) c FROM dcat_dataset
        UNION ALL SELECT 'data_registry', count(*) FROM data_registry
        UNION ALL SELECT 'dcat_provenance', count(*) FROM dcat_provenance
        UNION ALL SELECT 'meta_video', count(*) FROM meta_video
        UNION ALL SELECT 'meta_news', count(*) FROM meta_news
        UNION ALL SELECT 'meta_blog', count(*) FROM meta_blog
        UNION ALL SELECT 'meta_shopping_insight', count(*) FROM meta_shopping_insight
        UNION ALL SELECT 'meta_persona_insight', count(*) FROM meta_persona_insight
        UNION ALL SELECT 'active_meta_video', count(*) FROM active_meta_video
        UNION ALL SELECT 'active_meta_news', count(*) FROM active_meta_news
        UNION ALL SELECT 'active_meta_blog', count(*) FROM active_meta_blog
        UNION ALL SELECT 'active_meta_shopping_insight', count(*) FROM active_meta_shopping_insight
        UNION ALL SELECT 'active_meta_persona_insight', count(*) FROM active_meta_persona_insight
    ) s WHERE c > 0;
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'C-2 실패: 남은 데이터 — %', txt; END IF;

    -- C-3. 벡터 테이블 4종의 PK가 (키, chunk_index) 복합키인가
    SELECT count(*) INTO n
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage k USING (constraint_name)
     WHERE tc.constraint_type = 'PRIMARY KEY'
       AND tc.table_name IN ('dcat_dataset_vec','meta_video_vec','meta_news_vec','meta_blog_vec')
       AND k.column_name = 'chunk_index';
    IF n <> 4 THEN RAISE EXCEPTION 'C-3 실패: chunk_index PK가 %개 (기대 4)', n; END IF;

    RAISE NOTICE '검증 C-1~C-3 전부 통과';
END $$;
