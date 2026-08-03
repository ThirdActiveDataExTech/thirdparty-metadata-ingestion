-- ═══════════════════════════════════════════════════════════════
-- views.sql : 편의 조회용 뷰 모음
-- DDL 적용 이후에 실행
-- ═══════════════════════════════════════════════════════════════

-- ── v_meta_youtube_latest ─────────────────────────────────────
-- meta_youtube_video + active_meta_youtube 최신 row 결합
-- 영상별 현재 통계(최신 수집값 + 전회차 대비 증감)를 한 번에 조회
CREATE OR REPLACE VIEW v_meta_youtube_latest AS
SELECT
    m.id,
    m.dataset_id,
    m.video_id,
    m.title,
    m.description,
    m.published_at,
    m.channel_id,
    m.channel_title,
    m.tags,
    m.category_id,
    m.topic_categories,
    m.duration,
    m.duration_seconds,
    m.definition,
    m.default_language,
    m.default_audio_language,
    m.has_caption,
    m.thumbnail_url,
    m.initial_view_count,
    m.initial_like_count,
    m.initial_comment_count,
    m.collected_at,
    a.collected_at  AS latest_collected_at,
    a.view_count    AS latest_view_count,
    a.like_count    AS latest_like_count,
    a.comment_count AS latest_comment_count,
    a.delta_views,
    a.delta_likes,
    a.delta_comments
FROM meta_youtube_video m
LEFT JOIN LATERAL (
    SELECT *
    FROM active_meta_youtube
    WHERE meta_id = m.id
    ORDER BY collected_at DESC
    LIMIT 1
) a ON true;

-- ── v_meta_naver_news_latest ──────────────────────────────────
-- meta_naver_news + active_meta_naver_news 최신 row 결합
-- 기사별 현재 댓글 통계(최신 수집값 + 전회차 대비 증감)를 한 번에 조회
-- is_naver_hosted=FALSE 인 외부 기사는 댓글 컬럼 모두 NULL
CREATE OR REPLACE VIEW v_meta_naver_news_latest AS
SELECT
    m.id,
    m.dataset_id,
    m.article_url,
    m.title,
    m.description,
    m.content,
    m.has_content,
    m.publisher,
    m.naver_url,
    m.is_naver_hosted,
    m.naver_oid,
    m.naver_aid,
    m.published_at,
    m.search_keyword,
    m.collected_at,
    a.collected_at   AS latest_collected_at,
    a.comment_count  AS latest_comment_count,
    a.expose_count   AS latest_expose_count,
    a.reply_count    AS latest_reply_count,
    a.delta_comments
FROM meta_naver_news m
LEFT JOIN LATERAL (
    SELECT *
    FROM active_meta_naver_news
    WHERE meta_id = m.id
    ORDER BY collected_at DESC
    LIMIT 1
) a ON true;

-- ── v_meta_naver_blog_latest ──────────────────────────────────
-- meta_naver_blog + active_meta_naver_blog 최신 row 결합
-- 게시물별 현재 반응(공감 등) 통계(최신 수집값 + 전회차 대비 증감)를 한 번에 조회
-- platform!='naver' 게시물은 반응 수집 대상이 아니라 active 행이 없어 반응 컬럼 NULL (ADR-006)
CREATE OR REPLACE VIEW v_meta_naver_blog_latest AS
SELECT
    m.id,
    m.dataset_id,
    m.post_url,
    m.title,
    m.description,
    m.content,
    m.has_content,
    m.blogger_name,
    m.blogger_link,
    m.platform,
    m.blog_id,
    m.log_no,
    m.published_at,
    m.search_keyword,
    m.collected_at,
    a.collected_at       AS latest_collected_at,
    a.reaction_count     AS latest_reaction_count,
    a.reaction_breakdown AS latest_reaction_breakdown,
    a.delta_reactions
FROM meta_naver_blog m
LEFT JOIN LATERAL (
    SELECT *
    FROM active_meta_naver_blog
    WHERE meta_id = m.id
    ORDER BY collected_at DESC
    LIMIT 1
) a ON true;
