-- ═══════════════════════════════════════════════════════════════
-- dcat_dataset_relation : 데이터셋 간 관계 (쌍+유형당 1행)
--
-- 와이즈넛 「백엔드 설계 초안」 v2 별첨 테이블정의서 기준. [신규]
-- 데이터셋 쌍의 관계를 보관하는 "승인 상태의 정본". 재생성 시 대체한다.
--
-- 이 테이블이 과제 산출물 "AI 기반 데이터 관계 생성·분석 SW"의 저장 계층이다
-- (development/04_Implementation_Methods.md §3 B2·B3·B4).
--
-- 규칙 (별첨 [5. 관계 유형 표준값] 시트 공통 규칙):
--   - 유형 추가: relation_type을 문자열 값으로 저장하므로 유형이 늘어도 스키마를 고치지 않는다.
--     단 relation_type_registry에 FK로 묶여 있어 등록되지 않은 유형은 INSERT 불가
--   - 판정 근거: evidence(jsonb)에 매칭 컬럼·겹친 값 수·유사도·LLM 사유를 남긴다
--   - 확정 상태: status로 자동 확정(APPROVED)과 검토 대기(PENDING)를 구분한다
--   - 쌍 단위: (출발, 도착, 유형) 조합당 1행. 재생성 시 대체한다
--
-- 주의: 현재 UNIQUE가 (출발, 도착, 유형)이라 "규칙 기반 엣지와 모델 기반 엣지를
--       같은 유형으로 동시 보관"이 불가능하다. method는 UNIQUE에 없어 구분자가 되지 못하고,
--       재생성 시 먼저 들어간 행을 덮어쓴다.
--       → UNIQUE에 method를 포함하는 변경을 와이즈넛에 제안한다 (파일 하단 참조).
-- ═══════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS dcat_dataset_relation CASCADE;

CREATE TABLE dcat_dataset_relation (

    id                  BIGSERIAL PRIMARY KEY,
    -- 관계 ID

    source_dataset_id   TEXT NOT NULL
                        REFERENCES dcat_dataset(dataset_id)
                        ON UPDATE CASCADE ON DELETE CASCADE,
    -- 출발 데이터셋

    target_dataset_id   TEXT NOT NULL
                        REFERENCES dcat_dataset(dataset_id)
                        ON UPDATE CASCADE ON DELETE CASCADE,
    -- 도착 데이터셋

    relation_type       TEXT NOT NULL
                        REFERENCES relation_type_registry(relation_type) ON UPDATE CASCADE,
    -- 관계 유형 | 값으로 기록 · relation_type_registry 참조
    -- 2026-10-27 기준 비정형에 적용 가능한 유형은 2종
    --   SEMANTICALLY_RELATED (제목·설명 임베딩 코사인 유사도)
    --   KEYWORD_OVERLAP      (키워드 집합 자카드 계수)

    relation_label      TEXT,
    -- 관계 표시명 | 화면 표기용 보조 명칭
    -- (별첨 v2 이후 추가된 컬럼 — 원천 문서에는 없음)

    score               REAL NOT NULL,
    -- 관계 점수 | 0~1

    method              TEXT NOT NULL,
    -- 생성 방법 | rule / embedding / llm

    status              TEXT NOT NULL,
    -- 검토 상태 | PENDING / APPROVED / REJECTED

    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 판정 근거 | 매칭 컬럼, 겹친 값 수, 유사도, LLM 사유

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 생성 시각

    UNIQUE (source_dataset_id, target_dataset_id, relation_type)
    -- 쌍+유형당 1행
);

CREATE INDEX idx_dcat_dataset_relation_type   ON dcat_dataset_relation (relation_type);
CREATE INDEX idx_dcat_dataset_relation_status ON dcat_dataset_relation (status);
CREATE INDEX idx_dcat_dataset_relation_target ON dcat_dataset_relation (target_dataset_id);

-- ═══════════════════════════════════════════════════════════════
-- 모비젠 변경 제안 (2026-10-27) — 와이즈넛 합의 후 적용
--
-- 목적: 같은 쌍·같은 관계 유형에 대해 규칙 산출 엣지와 모델 산출 엣지를 동시에 보관한다.
--      규칙만으로 만든 그래프와 규칙+모델 그래프를 각각 산출해 비교할 수 있고,
--      그 차이(커뮤니티 변화·modularity 변화)가 외부 모델 기여의 정량 증거가 된다.
--      relation_type을 늘리지 않으므로 표준값 체계가 그대로 유지된다.
--
-- ALTER TABLE dcat_dataset_relation
--     DROP CONSTRAINT dcat_dataset_relation_source_dataset_id_target_dataset_id_r_key;
-- ALTER TABLE dcat_dataset_relation
--     ADD CONSTRAINT uq_dcat_dataset_relation
--     UNIQUE (source_dataset_id, target_dataset_id, relation_type, method);
--
-- ALTER TABLE dcat_dataset_relation
--     ADD CONSTRAINT chk_dcat_dataset_relation_method
--     CHECK (method IN ('rule','embedding','llm','gnn'));
--
-- 함께 합의해야 할 3가지
--   ① UPSERT 충돌 대상 변경
--      기존 코드가 ON CONFLICT (source_dataset_id, target_dataset_id, relation_type)로
--      작성돼 있다면 method를 포함하도록 고쳐야 한다. 양측 적재 코드 동시 반영 필요.
--
--   ② "승인 상태의 정본" 우선순위 규칙
--      한 쌍·한 유형에 여러 행이 생기므로, 소비 측이 "A와 B는 관련 있는가"를 물을 때
--      어느 행을 답으로 삼을지 정해야 한다.
--      제안: status='APPROVED' 우선 → 동률이면 score 최대 → 그래도 동률이면 created_at 최신.
--      조회용 뷰(v_dataset_relation_effective)로 고정해 소비 측이 규칙을 몰라도 되게 한다.
--
--   ③ method 값 통제
--      자유 문자열이면 오타 하나가 중복 행을 만든다. 위 CHECK 제약으로 값을 고정하거나,
--      늘어날 가능성이 크면 method_registry를 두는 편이 안전하다.
--
-- 대안(미채택): relation_type에 '_MODEL' 접미를 붙여 유형을 분리하는 방법.
--   스키마 변경이 없다는 장점이 있으나 표준 유형 수가 두 배로 늘고,
--   유형 추가 때마다 모델용 짝을 같이 만들어야 해서 레지스트리가 지저분해진다.
