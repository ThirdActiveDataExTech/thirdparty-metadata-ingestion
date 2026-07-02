-- ═══════════════════════════════════════════════════════════════
-- dcat_provenance : 데이터셋 수집 실행 이력 (PROV-O 기반)
-- 수집 스크립트 실행 1회 = 1행
-- dcat_dataset 의 dataset_id 를 FK 로 참조
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS dcat_provenance;

CREATE TABLE dcat_provenance (

    -- ── 식별 ──────────────────────────────────────────────────
    prov_id         BIGSERIAL PRIMARY KEY,
    -- 자동 증가 PK

    dataset_id      TEXT NOT NULL
                    REFERENCES dcat_dataset(dataset_id) ON DELETE CASCADE,
    -- 어느 데이터셋의 수집 이력인지 (FK)
    -- ON DELETE CASCADE: 데이터셋 삭제 시 수집 이력도 함께 삭제
    -- 예) 'naver_shopping_insight', 'youtube_samsung_official'

    -- ── 활동 유형 ─────────────────────────────────────────────
    activity_type   TEXT NOT NULL,
    -- prov:Activity 유형
    -- 'initial'   : 최초 수집 (DB 비어 있을 때 첫 실행)
    -- 'update'    : 정기 업데이트 (기존 데이터에 신규 기간 추가)
    -- 'backfill'  : 과거 데이터 소급 수집 (누락 기간 보완)
    -- 'reprocess' : 재처리 (데이터 변경 없이 파이프라인 재실행)

    agent           TEXT NOT NULL,
    -- prov:wasAssociatedWith | 수집 로직 모듈명 (오케스트레이터와 무관하게 고정)
    -- 수집 코드가 항상 설정해야 하는 값 — NOT NULL
    -- 예) 'naver_shopping_insight', 'youtube_collector', 'naver_news'

    triggered_by    TEXT,
    -- 실행을 트리거한 주체 (오케스트레이터 정보, 환경변수 TRIGGERED_BY 로 주입)
    -- 예) 'manual'                                  ← 로컬 직접 실행
    -- 예) 'K8s CronJob naver-shopping-cronjob'      ← Kubernetes CronJob
    -- 예) 'Airflow naver_shopping_dag / collect'    ← Airflow 도입 후

    -- ── 실행 시간 ─────────────────────────────────────────────
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- prov:startedAtTime | 수집 시작 시각

    ended_at        TIMESTAMPTZ,
    -- prov:endedAtTime | 수집 완료 시각 (실행 중이면 NULL)

    -- ── 실행 결과 ─────────────────────────────────────────────
    status          TEXT NOT NULL DEFAULT 'running',
    -- 실행 상태
    -- 'running' : 진행 중
    -- 'success' : 성공
    -- 'failure' : 실패

    rows_affected   INTEGER,
    -- 해당 수집에서 추가 또는 변경된 행 수
    -- 예) 364 (1년치 일간 × 13 카테고리 중 신규분)

    -- ── 파라미터 ──────────────────────────────────────────────
    params          JSONB,
    -- prov:used | 수집 시 사용한 파라미터
    -- 예) {"start_date": "2025-06-17", "end_date": "2026-06-16"}
    -- 예) {"channel_id": "UCWwgaK7x0_FR1goeSRDDOkg", "max_results": 50}
    -- 예) {"keywords": ["인공지능", "AI"], "display": 100}

    -- ── 오류 / 메모 ───────────────────────────────────────────
    error_message   TEXT,
    -- 실패 시 에러 메시지 또는 스택 트레이스 요약

    notes           TEXT
    -- 기타 메모 (triggered_by 로 표현 안 되는 추가 맥락)
    -- 예) '최초 실행 1단계: 1년치 소급 수집', '운영자 수동 재실행'
);

-- 검색용 인덱스
CREATE INDEX idx_dcat_prov_dataset  ON dcat_provenance(dataset_id);
CREATE INDEX idx_dcat_prov_started  ON dcat_provenance(started_at DESC);
CREATE INDEX idx_dcat_prov_status   ON dcat_provenance(status);
