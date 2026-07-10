-- ═══════════════════════════════════════════════════════════════
-- meta_naver_blog_vec : Naver 블로그 게시물 단위 임베딩 (pgvector)
-- meta_naver_blog 와 1:1 대응 (meta_id PK 겸 FK)
-- 게시물 제목 + 요약 + 본문을 합쳐 임베딩 — 아이템 레벨 벡터 검색 용도
-- 본문(content)이 없는 경우 제목 + 요약만으로 임베딩
-- ═══════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS meta_naver_blog_vec;

CREATE TABLE meta_naver_blog_vec (

    meta_id     BIGINT PRIMARY KEY
                REFERENCES meta_naver_blog(id) ON DELETE CASCADE,
    -- meta_naver_blog 와 1:1
    -- ON DELETE CASCADE: 게시물 메타 삭제 시 임베딩도 자동 삭제

    embedding   vector(768) NOT NULL,
    -- paraphrase-multilingual-mpnet-base-v2 기준 768차원

    embed_text  TEXT NOT NULL,
    -- 임베딩에 사용된 원본 텍스트 (재현 및 디버깅용)
    -- 형식: "{title}. {description}. {content[:500]}" (has_content=TRUE)
    --       "{title}. {description}"                  (has_content=FALSE)

    model_name  TEXT NOT NULL
                DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',

    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 코사인 유사도 검색용 인덱스 (데이터 수천 건 이상 시 효과적)
-- CREATE INDEX ON meta_naver_blog_vec USING hnsw (embedding vector_cosine_ops);
