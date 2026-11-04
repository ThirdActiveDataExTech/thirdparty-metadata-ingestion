-- ═══════════════════════════════════════════════════════════════
-- meta_video_ai : 영상 1건당 AI 생성 메타데이터 (A2 최소선)
--
-- 근거: 연구개발계획서 1·2차년도 "비정형 액티브 메타데이터 **처리**"
--       (현재 STT만 구현, NLP·VLM 미구현)
--
-- ⚠️ **생성 요약이 아니라 추출 요약이다.** [ADR-013](../docs/adr/013_No_External_LLM_API.md)이
--    외부 LLM을 금지했고 원칙은 "LLM이 없어도 기능이 성립해야 한다"였다.
--    원문에서 문장을 **고르기만** 하므로 hallucination이 없고, 뽑힌 문장이
--    원문 어디서 왔는지 추적된다. 그 자체가 과제 산출물의 근거가 된다.
--
-- B1(meta_feature)과의 차이 — **단위가 다르다.**
--   B1  데이터셋 단위. IDF 코퍼스 = 데이터셋 25개 → 해상도가 거칠다
--   A2  아이템 단위.   IDF 코퍼스 = 그 데이터셋의 영상 수백~수천 건
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS meta_video_ai CASCADE;

CREATE TABLE meta_video_ai (

    meta_id       BIGINT PRIMARY KEY
                  REFERENCES meta_video(id) ON DELETE CASCADE,
    -- 영상 1건 = 1행. 원본이 사라지면 AI 메타도 의미가 없다

    ai_summary    TEXT,
    -- 추출 요약. 원문에서 고른 문장을 **원래 순서대로** 이은 것.
    -- 순서를 섞으면 사람이 읽을 수 없다 — B1의 representative_text는
    -- 임베딩 입력이라 순서가 무의미했지만 이쪽은 사람이 읽는다

    ai_keywords   TEXT[],
    -- TF-IDF 상위어. 코퍼스는 **같은 데이터셋의 다른 영상들**이다

    source_chars  INTEGER,
    -- 요약의 입력이 된 원문 길이. 품질을 해석하는 데 필요하다 —
    -- 100자짜리 설명에서 뽑은 요약과 2,000자 자막에서 뽑은 요약은 다른 물건이다

    has_transcript BOOLEAN NOT NULL DEFAULT FALSE,
    -- 자막이 입력에 포함됐는가. 2026-11-04 기준 1,554건 중 14건뿐이고
    -- 백필(ADR-015)이 돌면 늘어난다. 늘어난 뒤 재생성 대상을 고르는 기준

    method        TEXT NOT NULL,
    -- 어떻게 만들었는지. 예: 'extractive/tfidf/kiwi-0.24.1+model-0.24.0+pos1'
    -- 토크나이저가 바뀌면 키워드가 통째로 달라진다(ADR-010의 tokenizer_ver와 같은 이유).
    -- 나중에 로컬 sLLM 생성 요약으로 바꾸면 여기가 달라져 재생성 대상이 구분된다

    status        TEXT NOT NULL DEFAULT 'ok'
                  CHECK (status IN ('ok', 'skipped', 'failed')),
    -- 'skipped' : 입력 텍스트가 너무 짧아 만들 수 없었다(실패가 아니다)
    -- 'failed'  : 처리 중 오류. **파이프라인을 멈추지 않고 여기 기록한다**
    --             (로드맵 A2: "완전 실패로 파이프라인 중단 금지")

    error         TEXT,
    -- status='failed'일 때 사유

    generated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_meta_video_ai_status ON meta_video_ai (status);
CREATE INDEX idx_meta_video_ai_method ON meta_video_ai (method);
-- 키워드로 영상을 찾는 경로. GIN이라 배열 포함 질의(@>)가 인덱스를 탄다
CREATE INDEX idx_meta_video_ai_keywords ON meta_video_ai USING gin (ai_keywords);
