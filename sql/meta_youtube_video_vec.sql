-- ═══════════════════════════════════════════════════════════════
-- meta_youtube_video_vec : YouTube 영상 단위 임베딩 (pgvector)
-- meta_youtube_video 와 1:1 대응 (meta_id PK 겸 FK)
-- 영상 제목 + 설명 + 태그를 합쳐 임베딩 — 아이템 레벨 벡터 검색 용도
-- ═══════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS meta_youtube_video_vec;

CREATE TABLE meta_youtube_video_vec (

    meta_id     BIGINT PRIMARY KEY
                REFERENCES meta_youtube_video(id) ON DELETE CASCADE,
    -- meta_youtube_video 와 1:1
    -- ON DELETE CASCADE: 영상 메타 삭제 시 임베딩도 자동 삭제

    embedding   vector(768) NOT NULL,
    -- paraphrase-multilingual-mpnet-base-v2 기준 768차원

    embed_text  TEXT NOT NULL,
    -- 임베딩에 사용된 원본 텍스트 (재현 및 디버깅용)
    -- 형식: "{title}. {description}. 태그: {tags}"

    model_name  TEXT NOT NULL
                DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',

    embedded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 코사인 유사도 검색용 인덱스 (데이터 수천 건 이상 시 효과적)
-- CREATE INDEX ON meta_youtube_video_vec USING hnsw (embedding vector_cosine_ops);
