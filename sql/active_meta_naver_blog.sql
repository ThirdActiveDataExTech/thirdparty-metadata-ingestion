-- ═══════════════════════════════════════════════════════════════
-- active_meta_naver_blog : Naver 블로그 게시물 시계열 통계 스냅샷
-- ⚠️ 잠정(PROVISIONAL) 설계 — ADR-005(뉴스 수집 가능 지표 결정)와 동일한 수준의
-- 실제 API 검증을 아직 거치지 않았다. 아래 컬럼은 뉴스와 같은 댓글 시스템
-- (apis.naver.com/commentBox/cbox)을 블로그도 공유할 것이라는 가정 하의
-- 설계이며, 실제 objectId/ticket 파라미터로 호출해 값이 오는지 확인 후
-- ADR-006으로 확정할 것. 확정 전까지 이 테이블은 생성만 해두고 수집 코드에서
-- 사용하지 않는다.
--
-- [조사 필요 항목 — ADR-006 후보]
-- 댓글 수 : news와 같은 cbox 계열 API로 수집 가능할 것으로 추정되나 미검증
--           (ticket=blog 등 블로그 전용 파라미터 확인 필요)
-- 공감 수 : 페이지에 표시되나 JS 실행 후 로드되는 구조로 추정
--           (news의 "추천 반응"과 동일한 문제일 가능성 — 브라우저 자동화 필요할 수 있음)
-- 조회수  : 블로그 주인만 볼 수 있는 통계일 가능성이 높고, 게시물 페이지에
--           공개 표시되는지 여부부터 확인 필요 (news는 2020년 이후 완전 비공개)
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS active_meta_naver_blog;

CREATE TABLE active_meta_naver_blog (

    -- ── 식별 ──────────────────────────────────────────────────
    id              BIGSERIAL PRIMARY KEY,

    meta_id         BIGINT NOT NULL
                    REFERENCES meta_naver_blog(id) ON DELETE CASCADE,
    -- meta_naver_blog.id FK (dataset+게시물 조합)
    -- blog_id/log_no 파싱 성공한 게시물만 행 존재 예정 (news의 is_naver_hosted와 유사한 제약)

    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (meta_id, collected_at),

    -- ── 댓글 통계 스냅샷 (미검증 — 위 헤더 주석 참조) ────────────
    comment_count   INTEGER,
    -- 전체 댓글 수 (삭제 포함) — cbox 계열 API 가정, 실제 필드 키는 검증 후 확정

    expose_count    INTEGER,
    -- 실제 노출 중인 댓글 수 (삭제·숨김 제외)

    reply_count     INTEGER,
    -- 답글 수

    -- ── 공감 수 (미검증) ──────────────────────────────────────
    sympathy_count  INTEGER,
    -- "공감" 수. 수집 가능 여부 자체가 미확인 — 컬럼만 선점

    -- ── 전 회차 대비 증감 ─────────────────────────────────────
    -- NULL = 이 meta_id의 첫 번째 수집 (기준값 없음)
    delta_comments  INTEGER
);

-- 조회용 인덱스
CREATE INDEX idx_active_blog_meta      ON active_meta_naver_blog(meta_id);
CREATE INDEX idx_active_blog_collected ON active_meta_naver_blog(collected_at DESC);
