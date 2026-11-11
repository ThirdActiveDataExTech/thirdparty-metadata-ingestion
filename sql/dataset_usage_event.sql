-- ═══════════════════════════════════════════════════════════════
-- dataset_usage_event : 데이터셋 활용 기록 (조회·내려받기 이벤트) [신규, 모비젠 전용]
--
-- NEXT_STEPS 결정 3(2026-11-05): 사용자 참여·활용 기록 중 **② 활용 기록만** 모비젠이 먼저 만든다.
-- 활용 현황·인기 데이터, C2 목표선(사용 이력 반영 추천)의 입력이다.
-- 계정·인증(①)과 사용자 참여(③ 주석·리뷰·피드백)는 케이웨어 과업 — 나중에 얹을 수 있게 둔다:
--   - user_id는 비워 둘 수 있다(비로그인). 계정 테이블이 생기면 그때 FK를 건다(§2-6과 같은 방식)
--   - event_type은 열린 값이다. 허용 목록은 API(src/api/usage.py)가 관리한다
--   - 대상은 데이터셋 공통 + 선택적 item_id(아이템 단위 이벤트용)
--
-- 개인정보: IP·User-Agent·검색어는 저장하지 않는다. 비로그인 방문은 브라우저 세션 식별자
-- (포털이 탭마다 만드는 임의값)의 해시만 남긴다 — 같은 방문의 중복 집계를 막는 용도.
-- 와이즈넛 적재 대상이 아니다(공용 테이블을 바꾸지 않는다, ADR-014).
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS dataset_usage_event CASCADE;

CREATE TABLE dataset_usage_event (

    id            BIGSERIAL PRIMARY KEY,

    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 발생 시각

    event_type    TEXT NOT NULL,
    -- 이벤트 유형 | view(상세 조회) · download(내려받기) — 열린 값, 허용 목록은 API

    dataset_id    TEXT NOT NULL REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    -- 대상 데이터셋 | 데이터셋을 지우면 기록도 지운다

    item_id       TEXT,
    -- 대상 아이템(선택) | 아이템 단위 이벤트용

    detail        TEXT,
    -- 세부 | download의 형식(package · jsonld) 등

    user_id       TEXT,
    -- 로그인 사용자 ID(시제품 로그인, ADR-021) | 비로그인은 NULL · 계정 테이블 생기면 FK

    session_hash  TEXT,
    -- 브라우저 세션 식별자의 SHA-256 앞 32자 | 원문은 저장하지 않는다 · 중복 집계 방지

    origin        TEXT NOT NULL DEFAULT 'portal'
    -- 기록 경로 | portal(화면이 보냄) · server(API가 직접 기록, 사람 식별됨) · api(로그인·세션 없는 API 직접 호출 — 중복 제거 없이 따로 집계)
);

CREATE INDEX idx_dataset_usage_event_dataset ON dataset_usage_event (dataset_id, occurred_at DESC);
CREATE INDEX idx_dataset_usage_event_time    ON dataset_usage_event (occurred_at DESC);

COMMENT ON TABLE dataset_usage_event IS
    '데이터셋 활용 기록(조회·내려받기). IP·UA·검색어 미저장, 비로그인은 세션 해시만. 결정 3(2026-11-05)';
