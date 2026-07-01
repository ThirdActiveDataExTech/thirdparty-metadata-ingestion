-- ═══════════════════════════════════════════════════════════════
-- dcat_dataset_vec : 데이터셋 description 임베딩 (pgvector)
-- dcat_dataset 의 dataset_id 를 PK 겸 FK 로 사용 (1:1)
-- 자연어 질의 → 유사 데이터셋 탐색 용도
-- ═══════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dcat_dataset_vec (

    dataset_id   TEXT PRIMARY KEY REFERENCES dcat_dataset(dataset_id),
    -- dcat_dataset 과 1:1 대응

    embedding    vector(768),
    -- paraphrase-multilingual-mpnet-base-v2 기준 768차원
    -- 향후 Qdrant 전환 또는 모델 변경 시 재임베딩 필요

    embed_text   TEXT,
    -- 임베딩에 사용된 원본 텍스트 (재현 및 디버깅용)
    -- 형식: "{title}. {description}. 키워드: {keywords}"

    model_name   TEXT NOT NULL DEFAULT 'paraphrase-multilingual-mpnet-base-v2',
    -- 임베딩 생성에 사용된 모델명 (모델 교체 이력 추적)

    embedded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 임베딩 생성 일시
);

-- 코사인 유사도 검색용 인덱스 (데이터 100건 이상 시 효과적)
-- 현재 소량이라 생략, 향후 필요 시 추가:
-- CREATE INDEX ON dcat_dataset_vec USING hnsw (embedding vector_cosine_ops);
