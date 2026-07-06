-- ═══════════════════════════════════════════════════════════════
-- meta_youtube_video : YouTube 영상 단위 메타데이터 (Schema.org VideoObject 기반)
-- dcat_dataset 1개에 N개의 영상 행이 연결됨
-- 같은 video_id라도 dataset_id가 다르면 별도 행으로 관리
-- (동일 영상을 여러 데이터셋에서 독립적으로 추적하기 위함)
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS meta_youtube_video CASCADE;

CREATE TABLE meta_youtube_video (

    -- ── 식별 ──────────────────────────────────────────────────
    id                      BIGSERIAL PRIMARY KEY,

    dataset_id              TEXT NOT NULL
                            REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    -- 어느 데이터셋 소속인지 (FK)

    video_id                TEXT NOT NULL,
    -- YouTube 영상 고유 ID (예: 'dQw4w9WgXcQ')

    UNIQUE (dataset_id, video_id),
    -- 동일 데이터셋 내 중복 방지

    -- ── 영상 기본 정보 (schema:VideoObject) ──────────────────
    title                   TEXT NOT NULL,
    -- schema:name | 영상 제목

    description             TEXT,
    -- schema:description | 영상 설명 (truncate 고려 — YouTube 최대 5000자)

    published_at            TIMESTAMPTZ,
    -- schema:uploadDate | 최초 공개 일시

    -- ── 채널 정보 (schema:author) ─────────────────────────────
    channel_id              TEXT,
    -- schema:author.identifier | YouTube 채널 ID

    channel_title           TEXT,
    -- schema:author.name | 채널명

    -- ── 분류 / 태그 ───────────────────────────────────────────
    tags                    JSONB,
    -- schema:keywords | 영상 태그 목록
    -- 예) ["반도체", "HBM", "삼성전자"]

    category_id             TEXT,
    -- YouTube 카테고리 ID (예: '28' = Science & Technology)

    topic_categories        JSONB,
    -- YouTube topicDetails.topicCategories — Wikipedia 카테고리 URL 배열
    -- 예) ["https://en.wikipedia.org/wiki/Technology"]

    -- ── 미디어 속성 ───────────────────────────────────────────
    duration                TEXT,
    -- schema:duration | ISO 8601 형식 (예: 'PT1H2M3S')

    duration_seconds        INTEGER,
    -- 필터링/정렬용 초 단위 변환값 (Shorts 제외: ≤60초)

    definition              TEXT,
    -- 화질 정보 — 'hd' 또는 'sd'

    default_language        TEXT,
    -- 영상 설명의 기본 언어 (예: 'ko', 'en')

    default_audio_language  TEXT,
    -- 음성 기본 언어 (예: 'ko', 'en')

    has_caption             BOOLEAN,
    -- schema:accessibilityFeature 중 자막 여부

    thumbnail_url           TEXT,
    -- schema:thumbnailUrl | 기본 썸네일 URL (maxres > high > medium > default 순)

    -- ── 초기 수집 시점 통계 스냅샷 ───────────────────────────
    -- active_meta_youtube 에서 시계열 추적하지만,
    -- 최초 수집값을 여기에 보관하여 delta 기준점으로 활용
    initial_view_count      BIGINT,
    initial_like_count      BIGINT,
    initial_comment_count   BIGINT,

    -- ── 관리 ──────────────────────────────────────────────────
    collected_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 이 행이 DB에 처음 삽입된 시각

    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
    -- 필드 갱신 시각 (일반적으로 변경 없음 — 영상 메타는 거의 불변)
);

-- 조회용 인덱스
CREATE INDEX idx_meta_yt_dataset    ON meta_youtube_video(dataset_id);
CREATE INDEX idx_meta_yt_video      ON meta_youtube_video(video_id);
CREATE INDEX idx_meta_yt_published  ON meta_youtube_video(published_at DESC);
CREATE INDEX idx_meta_yt_channel    ON meta_youtube_video(channel_id);
