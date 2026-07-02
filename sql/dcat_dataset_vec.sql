-- ═══════════════════════════════════════════════════════════════
-- dcat_dataset_vec : 데이터셋 description 임베딩 (pgvector)
-- dcat_dataset 의 dataset_id 를 PK 겸 FK 로 사용 (1:1)
-- 자연어 질의 → 유사 데이터셋 탐색 용도
-- ═══════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS dcat_dataset_vec;

CREATE TABLE dcat_dataset_vec (

    dataset_id   TEXT PRIMARY KEY
                 REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    -- dcat_dataset 과 1:1 대응
    -- ON DELETE CASCADE: 데이터셋 삭제 시 임베딩도 자동 삭제

    embedding    vector(768) NOT NULL,
    -- paraphrase-multilingual-mpnet-base-v2 기준 768차원
    -- 향후 Qdrant 전환 또는 모델 변경 시 재임베딩 필요

    embed_text   TEXT NOT NULL,
    -- 임베딩에 사용된 원본 텍스트 (재현 및 디버깅용)
    -- 형식: "{title}. {description}. 키워드: {keywords}"

    model_name   TEXT NOT NULL
                 DEFAULT 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
    -- HuggingFace 전체 식별자로 저장 (재현성 보장)

    embedded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 임베딩 생성 일시
);

-- 코사인 유사도 검색용 인덱스 (데이터 100건 이상 시 효과적)
-- 현재 소량이라 생략, 향후 필요 시 추가:
-- CREATE INDEX ON dcat_dataset_vec USING hnsw (embedding vector_cosine_ops);
