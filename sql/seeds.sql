-- ═══════════════════════════════════════════════════════════════
-- seeds.sql : 샘플 데이터 (개발/테스트용)
-- 실행 전 DDL 4개가 먼저 적용돼 있어야 함
-- 실행 순서: dcat_dataset → dcat_provenance → data_registry → dcat_dataset_vec
-- ═══════════════════════════════════════════════════════════════

-- ── dcat_dataset ──────────────────────────────────────────────

INSERT INTO dcat_dataset (
    dataset_id, title, description,
    publisher, source_type, landing_page, access_url, subjects,
    language, spatial, temporal_start, temporal_end,
    temporal_resolution, accrual_periodicity,
    keywords, license, rights
) VALUES
(
    'naver_shopping_insight',
    '네이버 쇼핑 인사이트 카테고리 수집',
    '성별×연령(12조합) 필터로 수집한 카테고리별 일간 검색량 지수. anchor 보정(intra_scale) 및 inter_scale 적용.',
    'Naver', 'shopping',
    'https://datalab.naver.com/shopping/',
    'https://openapi.naver.com/v1/datalab/shopping/categories',
    '["50000148","50001828","50001421","50000204","50000167"]',
    'ko', 'KR', '2025-06-17', '2026-06-16', 'P1D', 'P1D',
    '["쇼핑","검색량","카테고리","성별","연령","네이버"]',
    'https://developers.naver.com/notice/terms',
    '네이버 API 이용약관 준수. 수집 데이터의 외부 배포 및 상업적 재판매 금지.'
),
(
    'naver_persona_insight',
    '네이버 쇼핑 인사이트 페르소나 분석',
    '카테고리별 성별·연령 독립 가정 기반 persona_index 산출. gender_pv × age_pv 교차 추정.',
    'Naver', 'shopping',
    'https://datalab.naver.com/shopping/',
    'https://openapi.naver.com/v1/datalab/shopping/category/gender,age',
    '["50000148","50001828","50001421","50000204"]',
    'ko', 'KR', '2025-06-18', '2026-06-17', 'P1D', 'P1D',
    '["쇼핑","페르소나","성별","연령","카테고리"]',
    'https://developers.naver.com/notice/terms',
    '네이버 API 이용약관 준수. 수집 데이터의 외부 배포 및 상업적 재판매 금지.'
),
(
    'youtube_samsung_official',
    '삼성전자 공식 유튜브 채널',
    '삼성전자 공식 YouTube 채널(@Samsung) 전체 영상 메타데이터 수집. 주간 단위 업데이트.',
    'YouTube', 'video',
    'https://www.youtube.com/@Samsung',
    'https://www.googleapis.com/youtube/v3/videos',
    '["UCWwgaK7x0_FR1goeSRDDOkg"]',
    'ko', 'KR', '2024-01-01', NULL, NULL, 'P7D',
    '["유튜브","삼성전자","테크","채널"]',
    'https://developers.google.com/youtube/terms/api-services-tos',
    'YouTube API Services Terms of Service 준수. 수집 데이터의 제3자 제공 시 Google 사전 승인 필요.'
),
(
    'naver_news_ai',
    '네이버 뉴스 AI 관련 기사 수집',
    '네이버 뉴스 API를 통해 인공지능 관련 키워드로 수집한 뉴스 기사. 본문 스크래핑 포함.',
    'Naver', 'news',
    'https://news.naver.com',
    'https://openapi.naver.com/v1/search/news.json',
    '["인공지능","AI","머신러닝","딥러닝"]',
    'ko', 'KR', '2026-01-01', NULL, NULL, 'P1D',
    '["뉴스","AI","인공지능","네이버"]',
    'https://developers.naver.com/notice/terms',
    '네이버 API 이용약관 준수. 뉴스 본문 스크래핑은 각 언론사 저작권 정책 별도 확인 필요.'
);

-- ── dcat_provenance ───────────────────────────────────────────

INSERT INTO dcat_provenance (
    dataset_id, activity_type, agent, triggered_by,
    started_at, ended_at, status, rows_affected, params, error_message, notes
) VALUES
(
    'naver_shopping_insight', 'initial', 'naver_shopping_insight', 'manual',
    '2025-06-18 02:00:00+09', '2025-06-18 02:04:31+09', 'success', 4732,
    '{"phase":"1/2","start_date":"2024-06-18","end_date":"2025-06-17"}',
    NULL, '최초 실행 1단계: 1년치 소급 수집'
),
(
    'naver_shopping_insight', 'initial', 'naver_shopping_insight', 'manual',
    '2025-06-18 02:04:31+09', '2025-06-18 02:05:58+09', 'success', 364,
    '{"phase":"2/2","start_date":"2025-05-21","end_date":"2025-06-17"}',
    NULL, '최초 실행 2단계: 28일 overlap 수집'
),
(
    'naver_shopping_insight', 'update', 'naver_shopping_insight',
    'K8s CronJob naver-shopping-cronjob',
    '2025-06-25 02:00:00+09', '2025-06-25 02:01:12+09', 'success', 91,
    '{"start_date":"2025-05-28","end_date":"2025-06-24","overlap_days":28}',
    NULL, NULL
),
(
    'naver_shopping_insight', 'update', 'naver_shopping_insight',
    'K8s CronJob naver-shopping-cronjob',
    '2026-06-30 02:00:00+09', '2026-06-30 02:01:09+09', 'success', 91,
    '{"start_date":"2026-06-02","end_date":"2026-06-29","overlap_days":28}',
    NULL, NULL
),
(
    'naver_persona_insight', 'initial', 'naver_persona', 'manual',
    '2025-06-18 03:00:00+09', '2025-06-18 03:12:44+09', 'success', 56784,
    '{"start_date":"2025-06-18","end_date":"2026-06-17"}',
    NULL, '최초 실행: gender×age 12조합 전체'
),
(
    'naver_persona_insight', 'update', 'naver_persona',
    'K8s CronJob naver-persona-cronjob',
    '2026-06-30 03:00:00+09', '2026-06-30 03:02:31+09', 'success', 1092,
    '{"start_date":"2026-06-23","end_date":"2026-06-29","overlap_days":28}',
    NULL, NULL
),
(
    'youtube_samsung_official', 'initial', 'youtube_collector', 'manual',
    '2026-06-30 04:00:00+09', '2026-06-30 04:03:21+09', 'success', 342,
    '{"channel_id":"UCWwgaK7x0_FR1goeSRDDOkg","max_results":500}',
    NULL, '채널 전체 영상 최초 수집'
),
(
    'naver_news_ai', 'initial', 'naver_news', 'manual',
    '2026-01-01 06:00:00+09', '2026-01-01 06:00:47+09', 'success', 1200,
    '{"keywords":["인공지능","AI","머신러닝"],"display":100}',
    NULL, '최초 수집'
),
(
    'naver_news_ai', 'update', 'naver_news',
    'K8s CronJob naver-news-cronjob',
    '2026-06-30 06:00:00+09', '2026-06-30 06:00:12+09', 'failure', 0,
    '{"keywords":["인공지능","AI"],"display":100}',
    'HTTP 429 Too Many Requests: API 일일 호출 한도 초과', NULL
);

-- ── data_registry ─────────────────────────────────────────────

INSERT INTO data_registry (
    dataset_id,
    minio_raw_prefix, minio_jsonld_prefix,
    pg_meta_table, pg_active_table, vec_collection,
    status, last_collected_at, next_collect_at, last_error,
    row_count, temporal_start, temporal_end
) VALUES
(
    'naver_shopping_insight',
    'raw/shopping/naver_shopping_insight/', 'jsonld/shopping/naver_shopping_insight/',
    'meta_naver_shopping', 'active_naver_shopping', 'dcat_dataset_vec',
    'active', '2026-06-30 02:01:09+09', '2026-07-01 02:00:00+09', NULL,
    5278, '2025-06-17', '2026-06-16'
),
(
    'naver_persona_insight',
    'raw/shopping/naver_persona_insight/', 'jsonld/shopping/naver_persona_insight/',
    'meta_naver_persona', 'active_naver_persona', 'dcat_dataset_vec',
    'active', '2026-06-30 03:02:31+09', '2026-07-01 03:00:00+09', NULL,
    57876, '2025-06-18', '2026-06-17'
),
(
    'youtube_samsung_official',
    'raw/video/youtube_samsung_official/', 'jsonld/video/youtube_samsung_official/',
    'meta_youtube_video', 'active_youtube_video', 'dcat_dataset_vec',
    'active', '2026-06-30 04:03:21+09', '2026-07-07 04:00:00+09', NULL,
    342, '2024-01-01', NULL
),
(
    'naver_news_ai',
    'raw/news/naver_news_ai/', 'jsonld/news/naver_news_ai/',
    'meta_naver_news', 'active_naver_news', 'dcat_dataset_vec',
    'error', '2026-01-01 06:00:47+09', '2026-07-01 06:00:00+09',
    'HTTP 429 Too Many Requests: API 일일 호출 한도 초과',
    1200, '2026-01-01', NULL
);

-- ── dcat_dataset_vec ──────────────────────────────────────────
-- 임베딩은 scripts/embed_datasets.py 로 생성
-- seeds.sql 실행 후 아래 명령어로 임베딩 삽입:
--   python scripts/embed_datasets.py
