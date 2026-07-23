-- ═══════════════════════════════════════════════════════════════
-- dcat_dataset : 데이터셋 전반 기술 (dcat:Dataset)
-- 모든 데이터 소스(YouTube, Naver, 뉴스 등)가 공통으로 사용
-- 1회 수집 코드 실행 = 1행 생성
-- ═══════════════════════════════════════════════════════════════

-- 부모 테이블이므로 CASCADE 로 자식 테이블(dcat_provenance, data_registry,
-- dcat_dataset_vec)까지 함께 삭제됨. 재구성 시 자식 DDL을 이후에 순서대로 실행.
DROP TABLE IF EXISTS dcat_dataset CASCADE;

CREATE TABLE dcat_dataset (

    -- ── 식별 ──────────────────────────────────────────────────
    dataset_id          TEXT PRIMARY KEY,
    -- dct:identifier | 전체 시스템에서 유일한 데이터셋 식별자
    -- 예) 'naver_shopping_insight', 'youtube_samsung_ch', 'naver_news_ai'

    title               TEXT NOT NULL,
    -- dct:title | 데이터셋 이름
    -- 예) '네이버 쇼핑 인사이트 카테고리 수집'

    description         TEXT NOT NULL,
    -- dct:description | 수집 목적, 수집 방식, 특이사항 등 상세 설명
    -- title과 함께 핵심 속성으로 취급 (P02 DCAT 커버리지 목표: 핵심 속성 95%+)

    -- ── 출처 ──────────────────────────────────────────────────
    publisher           TEXT NOT NULL,
    -- dct:publisher | 데이터 원천 플랫폼명
    -- 예) 'Naver', 'YouTube', '연합뉴스'

    source_type         TEXT NOT NULL,
    -- (확장) 출처 유형 분류 — data_registry.pg_meta_table 라우팅과
    -- "1 dataset = 1 source_type" 불변 규칙이 이 값의 존재를 전제로 함
    -- 예) 'shopping', 'video', 'news', 'blog', 'sns', 'government'

    landing_page        TEXT,
    -- dcat:landingPage | 플랫폼 공식 소개 페이지 (사람이 읽는 페이지)
    -- 예) 'https://datalab.naver.com/shopping/'

    access_url          TEXT,
    -- dcat:accessURL | API 엔드포인트 (기계가 호출하는 URL)
    -- 예) 'https://openapi.naver.com/v1/datalab/shopping/categories'

    subjects            JSONB,
    -- dct:subject | 실제 수집 대상 목록 (JSON 배열)
    -- 예) ["50001421","50000204"]          ← Naver 카테고리 ID
    -- 예) ["UCQrLs7LGqlcfrKDM0MXWFCQ"]    ← YouTube 채널 ID
    -- 예) ["인공지능","반도체"]             ← 뉴스 검색 키워드

    -- ── 언어 / 지역 ───────────────────────────────────────────
    language            TEXT DEFAULT 'ko',
    -- dct:language | ISO 639-1 언어 코드
    -- 예) 'ko', 'en'

    spatial             TEXT DEFAULT 'KR',
    -- dct:spatial | ISO 3166-1 국가 코드
    -- 예) 'KR', 'US'

    -- ── 시간 커버리지 ─────────────────────────────────────────
    temporal_start      DATE,
    -- dct:temporal 시작일 | 수집 후 자동 갱신
    -- 예) '2025-06-17'

    temporal_end        DATE,
    -- dct:temporal 종료일 | NULL = 현재 진행 중(open-ended)
    -- 예) '2026-06-16', NULL

    temporal_resolution TEXT,
    -- dcat:temporalResolution | 데이터 1건의 시간 단위 (ISO 8601)
    -- 예) 'P1D'(일간), 'P7D'(주간), NULL(시점 없음 - 영상 메타 등)

    accrual_periodicity TEXT,
    -- dct:accrualPeriodicity | 수집(갱신) 주기 (ISO 8601)
    -- 예) 'P1D'(매일), 'P7D'(매주), 'irregular'(비정기)

    -- ── 데이터 규모 ───────────────────────────────────────────
    item_count          BIGINT,
    -- (확장) DCAT/DCT에 대응 표준 용어 없음 — source_type과 같은 자체 확장 필드
    -- 이 데이터셋을 구성하는 고유 아이템 수 | temporal_start/end와 동일하게
    -- 수집 후 자동 갱신되며 data_registry.item_count와 동기화된다
    -- 예) YouTube 영상 수, 뉴스 기사 수, 블로그 게시물 수, 쇼핑/Persona 카테고리 수
    -- (data_registry.item_count가 운영 중 실시간으로 갱신되는 원본이고,
    --  여기 값은 dcat_dataset 조회만으로 데이터셋 규모를 바로 알 수 있도록 둔 미러)

    -- ── 태그 ──────────────────────────────────────────────────
    keywords            JSONB,
    -- dcat:keyword | 검색·분류용 키워드 (JSON 배열)
    -- 예) ["쇼핑","검색량","카테고리","네이버"]

    -- ── 이용 조건 ─────────────────────────────────────────────
    license             TEXT,
    -- dct:license | 데이터 이용 라이선스 식별자 또는 URI
    -- 예) "https://developers.naver.com/notice/terms"          ← Naver API 이용약관
    -- 예) "https://developers.google.com/youtube/terms/api-services-tos" ← YouTube API ToS
    -- 예) "https://www.kogl.or.kr/info/license.do#01-tab"     ← 공공누리 제1유형
    -- 예) "https://creativecommons.org/licenses/by/4.0/"      ← CC BY 4.0

    rights              TEXT,
    -- dct:rights | 라이선스 URI로 표현하기 어려운 세부 이용 조건 (자유 텍스트)
    -- 예) "네이버 API 이용약관 준수. 외부 배포 및 상업적 재판매 금지."
    -- 예) "YouTube API ToS 준수. 제3자 제공 시 Google 사전 승인 필요."
    -- 예) "출처 표시 조건 하에 자유로운 이용 가능. 상업적 이용 및 변경 허용."

    -- ── 생성 주체 ─────────────────────────────────────────────
    dataset_origin      TEXT NOT NULL DEFAULT 'admin',
    -- 데이터셋 생성 주체
    -- 'admin' : 관리자가 생성 (채널 1개, 검색어 1개 등 단일 대상 자동 수집)
    -- 'user'  : 사용자가 UI에서 직접 생성 (동일 소스 타입 내 복수 채널·영상·검색어 자유 조합)
    --           예) YouTube 데이터셋: 채널 여러 개 + 개별 영상 선택
    --           주의: source_type이 다른 항목(YouTube+뉴스 혼합 등)은 지원하지 않음

    owner_id             TEXT,
    -- 데이터셋을 생성한 사용자 식별자. 플랫폼 계정 테이블(같은 datagokr DB 안에
    -- 별도 스키마로 생성 예정, 다른 팀 작업 — 2026-07-23 기준 테이블 스펙 미정)의
    -- PK를 참조할 예정이나, 아직 그 테이블이 없어 지금은 FK 제약 없이 값만 저장한다.
    -- 계정 테이블 생성 후 실제 PK 컬럼명/타입 확인하여 ALTER TABLE로 FK 추가 필요
    -- (architecture/04_Collection_Pipeline_Operations.md §10, NEXT_STEPS.md 2-6 참조)
    -- dataset_origin='admin'이면 특정 사용자 소유가 아니므로 NULL 허용

    -- ── 관리 ──────────────────────────────────────────────────
    version             TEXT NOT NULL DEFAULT '1.0',
    -- owl:versionInfo | 수집 방식 변경 시 버전 올림

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- dct:issued | 데이터셋 최초 등록 일시

    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    -- dct:modified | 마지막 수집 또는 메타데이터 수정 일시
);

-- 검색용 인덱스
CREATE INDEX idx_dcat_dataset_source_type ON dcat_dataset(source_type);
CREATE INDEX idx_dcat_dataset_publisher   ON dcat_dataset(publisher);
CREATE INDEX idx_dcat_dataset_updated     ON dcat_dataset(updated_at DESC);
CREATE INDEX idx_dcat_dataset_owner       ON dcat_dataset(owner_id);
