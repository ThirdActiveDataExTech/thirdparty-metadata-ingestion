-- ═══════════════════════════════════════════════════════════════
-- meta_feature : 데이터셋·컬럼 단위 특징 메타 (B1 산출물)
--
-- 근거: 연구개발계획서 1차년도 "액티브 메타데이터 기반 데이터 특징 추출 및
--       분석 기술" / SW 모듈 "데이터 특징 추출 및 분석 모듈(모비젠)"
--
-- **왜 EAV인가.** 특징의 종류가 계속 늘어난다 — 지금은 키워드·길이분포·수집기간
-- 정도지만, 목표선에서 컬럼 카디널리티·결측률·상관·시계열 특성이 붙는다.
-- 종류마다 컬럼을 추가하면 그때마다 DDL과 마이그레이션이 필요하고, 비정형·정형이
-- 서로 다른 특징을 가지므로 절반이 늘 NULL인 wide 테이블이 된다.
-- 와이즈넛 `active_meta_dataset`가 지표를 EAV로 간 것과 같은 판단이다(§7.4).
--
-- **왜 value가 JSONB인가.** 특징의 값 모양이 제각각이다 —
--   item_count      → 1755                      (스칼라)
--   text_length     → {"mean":312,"p90":980}     (객체)
--   top_keywords    → [{"term":"반도체",...}]     (배열)
-- 하나의 타입으로 묶을 수 없고, 묶으면 호출부가 문자열을 파싱하게 된다.
--
-- **조회**: GIN 인덱스로 값 조건 필터가 가능하다(B1 완료 기준).
--   SELECT dataset_id FROM meta_feature
--   WHERE  feature_name = 'top_keywords' AND value @> '[{"term":"반도체"}]';
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS meta_feature CASCADE;

CREATE TABLE meta_feature (

    dataset_id   TEXT NOT NULL
                 REFERENCES dcat_dataset(dataset_id) ON UPDATE CASCADE ON DELETE CASCADE,
    -- ON UPDATE CASCADE: dataset_id는 URN이고 전환 이력이 있다(2026-10-28)
    -- ON DELETE CASCADE: 데이터셋이 사라지면 그 특징도 의미가 없다

    scope        TEXT NOT NULL
                 CHECK (scope IN ('dataset', 'column')),
    -- 'dataset' : 데이터셋 전체의 특징 (최소선은 전부 여기)
    -- 'column'  : 정형 데이터의 컬럼 단위 특징 (목표선, meta_datagokr_file 적재 후)

    target       TEXT NOT NULL DEFAULT '',
    -- scope='column'일 때 컬럼명. scope='dataset'이면 빈 문자열.
    -- NULL이 아니라 빈 문자열인 이유 — PK에 들어가는데 NULL은 PK에 못 쓴다

    feature_name TEXT NOT NULL,
    -- 특징 종류. 값은 src/analysis/features/ 의 상수로 관리한다.
    --   item_count · chunk_count · vocab_size · text_length
    --   content_rate · collected_period · top_keywords · representative_text

    value        JSONB NOT NULL,
    -- 특징 값. 모양은 feature_name마다 다르다(위 머리말 참조)

    method       TEXT,
    -- 어떻게 산출했는지. 예: 'tfidf/kiwi-0.24.1+model-0.24.0+pos1'
    -- ⚠️ 토크나이저가 바뀌면 키워드가 통째로 달라진다. 무엇으로 뽑은 값인지
    --    남겨 두지 않으면 재계산 대상을 고를 수 없다(ADR-010의 tokenizer_ver와 같은 이유)

    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (dataset_id, scope, target, feature_name)
    -- 같은 특징을 다시 계산하면 덮어쓴다(upsert). 이력은 남기지 않는다 —
    -- 특징은 "현재 데이터의 상태"이고, 이력이 필요하면 active_meta_* 쪽 일이다
);

CREATE INDEX idx_meta_feature_name  ON meta_feature (feature_name);
CREATE INDEX idx_meta_feature_value ON meta_feature USING gin (value jsonb_path_ops);
-- jsonb_path_ops: @> 포함 질의에 특화. 기본 연산자 클래스보다 인덱스가 작고 빠르다.
-- 키 존재 질의(?)는 못 쓰지만 특징 조회는 전부 "이 값을 포함하는가" 형태다
