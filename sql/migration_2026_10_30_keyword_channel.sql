-- ============================================================================
-- 키워드 검색 채널 추가 — 벡터 단일 채널 → 하이브리드 (ADR-010 구현)
--
-- 배경 : 2026-10-30 실측으로 **벡터 점수만으로는 "결과 없음"을 판정할 수 없다**는
--        것이 확인됐다(ADR-018). 질의 19건에서 여섯 지표 전부 정답 유무를
--        가르지 못했다 — 정답 있음 최저 0.8638, 정답 없음 최고 0.8856으로 겹친다.
--        판정도 랭킹도 키워드 채널이 있어야 한다.
--
--        그런데 PostgreSQL 기본 전문검색은 한국어 형태소를 모른다. 어절을 그대로
--        색인하면 조사 때문에 문서빈도가 무너진다 —
--          `대역폭을` 0.23%  vs  `대역폭` 15.04%   (**65배**)
--        질의 `대역폭`은 본문의 `대역폭을`에 영원히 걸리지 않는다.
--
-- 방식 : 앱단(Kiwi)에서 형태소로 끊은 결과를 `simple` 설정 tsvector에 넣는다.
--        DB 확장 설치가 필요 없어 이미지 재빌드·재기동이 전부 사라진다.
--        선택지 비교(pg_trgm/pg_bigm/PGroonga/OpenSearch)는 ADR-010 참조.
--
-- 위치 : 청크 테이블(`*_vec`)에 붙인다. 원본 테이블이 아니다.
--        `embed_text`는 chunker가 저작권 고지·구분선 같은 정형 문구를 이미
--        걷어낸 텍스트다. 같은 텍스트에서 두 채널을 만들어야
--        (a) 키워드 채널이 그 정제를 그대로 물려받고,
--        (b) 두 채널이 같은 단위로 랭크돼 RRF 결합이 성립한다.
--
-- ⚠️ `array_to_tsvector(tokens)`를 쓰지 않는다 — 위치 정보가 없어 `ts_rank_cd`를
--    못 쓰고 소문자 정규화도 안 된다. 반드시 `to_tsvector('simple', <공백구분>)`.
--    (ADR-010 "구현 시 반드시 지킬 것")
--
-- ⚠️ 생성 컬럼(GENERATED)이라 ALTER 시 **테이블 재작성**이 일어난다.
--    대상 163,407행(video 19,039 / news 41,410 / blog 102,884 / dataset 74).
--
-- ⚠️ **배포 순서가 있다.** `src/embedding/sync.py`가 청크를 넣을 때 token_text를
--    같이 쓰므로, **이 마이그레이션 전에 새 코드로 수집을 돌리면 파이프라인이
--    실패한다.** 반드시 이 순서다:
--
--      1) 이 마이그레이션 적용
--      2) PYTHONPATH=. python scripts/backfill_tokens.py   (기존 163,407청크)
--      3) 수집·검색 재개
--
--    2)를 건너뛰어도 오류는 안 난다 — 키워드 채널이 **조용히 0건**을 반환하고
--    하이브리드가 벡터 단독으로 수렴한다. 그래서 더 위험하다.
--
-- 트랜잭션 안에서 실행하고 §C 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

BEGIN;

-- ── A. 컬럼 추가 ────────────────────────────────────────────────────────────
-- token_text    : Kiwi 토큰을 공백으로 이은 문자열. 재현·디버깅용이자 tsv의 원천
-- tokenizer_ver : 어느 토크나이저로 만든 토큰인지. 질의 쪽과 불일치하면
--                 **오류 없이 리콜이 0이 되므로** 검색 진입점에서 대조한다
-- tsv           : 실제 색인. token_text에서 자동 파생되므로 둘이 어긋날 수 없다

ALTER TABLE meta_video_vec
    ADD COLUMN token_text    TEXT,
    ADD COLUMN tokenizer_ver TEXT,
    ADD COLUMN tsv           tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(token_text, ''))) STORED;

ALTER TABLE meta_news_vec
    ADD COLUMN token_text    TEXT,
    ADD COLUMN tokenizer_ver TEXT,
    ADD COLUMN tsv           tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(token_text, ''))) STORED;

ALTER TABLE meta_blog_vec
    ADD COLUMN token_text    TEXT,
    ADD COLUMN tokenizer_ver TEXT,
    ADD COLUMN tsv           tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(token_text, ''))) STORED;

ALTER TABLE dcat_dataset_vec
    ADD COLUMN token_text    TEXT,
    ADD COLUMN tokenizer_ver TEXT,
    ADD COLUMN tsv           tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(token_text, ''))) STORED;

-- ── B. GIN 인덱스 ───────────────────────────────────────────────────────────
-- 벡터 쪽 HNSW와 달리 GIN은 이 규모(10만행)에서 비용이 작아 지금 건다.

CREATE INDEX idx_meta_video_vec_tsv   ON meta_video_vec   USING gin (tsv);
CREATE INDEX idx_meta_news_vec_tsv    ON meta_news_vec    USING gin (tsv);
CREATE INDEX idx_meta_blog_vec_tsv    ON meta_blog_vec    USING gin (tsv);
CREATE INDEX idx_dcat_dataset_vec_tsv ON dcat_dataset_vec USING gin (tsv);

-- ── C. 검증 ─────────────────────────────────────────────────────────────────
-- 1) 네 테이블에 컬럼 3종이 전부 생겼는가 (기대: 12행)
SELECT table_name, column_name, is_generated
FROM   information_schema.columns
WHERE  table_name IN ('meta_video_vec','meta_news_vec','meta_blog_vec','dcat_dataset_vec')
  AND  column_name IN ('token_text','tokenizer_ver','tsv')
ORDER  BY table_name, column_name;

-- 2) 생성 컬럼이 실제로 동작하는가 — 아직 token_text가 비어 있으므로 전부 빈 tsv
SELECT 'meta_video_vec' AS t, count(*) AS rows, count(*) FILTER (WHERE tsv <> '') AS indexed
FROM meta_video_vec
UNION ALL SELECT 'meta_news_vec',    count(*), count(*) FILTER (WHERE tsv <> '') FROM meta_news_vec
UNION ALL SELECT 'meta_blog_vec',    count(*), count(*) FILTER (WHERE tsv <> '') FROM meta_blog_vec
UNION ALL SELECT 'dcat_dataset_vec', count(*), count(*) FILTER (WHERE tsv <> '') FROM dcat_dataset_vec;

-- 3) GIN 인덱스 4개가 생겼는가 (기대: 4행)
SELECT indexname FROM pg_indexes
WHERE indexname LIKE 'idx_%_vec_tsv' ORDER BY indexname;

COMMIT;
