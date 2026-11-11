-- ============================================================================
-- 벡터 채널 HNSW 색인 (콘텐츠 검색 지연 해소) — ✅ **2026-11-11 적용**
--
-- 적용 기록 (2026-11-11, 사용자 승인):
--   · 먼저 DB 파드 자원 상향(512Mi·0.5코어 → 3Gi·2코어, shared_buffers 128MB → 512MB, /dev/shm 1Gi,
--     k8s/deployments/postgres174-statefulset.yaml). 기존 512Mi로는 아래 2GB 설정에서 OOM 위험.
--   · **CONCURRENTLY 없이** 만들었다 — API 연결이 트랜잭션을 연 채 쉬고 있어(idle in transaction)
--     CONCURRENTLY는 그 트랜잭션을 기다리며 멈출 수 있다. 수집 CronJob이 정지 중이라 쓰기 잠금은 무해.
--   · maintenance_work_mem 1536MB, max_parallel_maintenance_workers 0.
--   · 결과: news 3분 07초(312MB) · blog 12분 39초(966MB) · video 22초(53MB), 모두 indisvalid=t.
--   · 콘텐츠 검색(포털 경유): blog 18~31초 → 0.2~0.4초, news 6~12초 → 0.1~0.3초 (첫 질의는 디스크 읽기로 수 초).
--   · 평가셋 회귀(video): hybrid_idf recall@1 0.9667 / mrr 0.9778 / ndcg@10 0.9833 — ADR-010 기준선과 동일.
--   · ⚠️ 색인을 만든 뒤 **API를 재시작해야** 기존 트랜잭션이 새 색인을 쓴다(배포 console-api 재시작함).
--
-- 배경 : 2026-11-10 콘텐츠 검색(/v1/console/search/items, q=반도체, limit 30) 실측
--          blog 31.5초 · news 11.7초 · video 4.3초
--        거의 전부가 하이브리드 검색의 **벡터 채널**이었다. *_vec 테이블에 벡터 색인이
--        없어 질의마다 모든 청크의 거리를 계산한다(blog 25.3만 청크). vector(768)은
--        3KB라 TOAST로 빠져 있어, 한 번에 TOAST 약 1.1GB를 읽는다
--        (EXPLAIN: shared hit 884,162 / read 139,867, 실행 25.2초).
--        병렬 워커를 2→6으로 올려도 24.6초 → 22.4초 — I/O가 병목이라 SQL만으로는 못 줄인다.
--
--        src/search/hybrid.py는 이 색인을 **쓸 수 있는 모양으로 이미 바뀌었다**
--        (청크를 `ORDER BY embedding <=> q LIMIT n`으로 먼저 받고 원본별 MAX).
--        색인이 없는 지금은 정확 검색 그대로 동작하고, 이 파일을 적용하면 바로 색인을 탄다.
--
-- 효과 : 로컬 재현(같은 벡터 25.3만/9.0만/1.9만 행을 pgvector 0.8.7 컨테이너에 복사,
--        shared_buffers 128MB 동일, 질의 10건) — 벡터 채널 1회
--          blog  정확 검색 ≈ 20~25초(원격 실측) → HNSW 중앙 50ms / 최대 73ms (버퍼 약 2.1만 블록)
--          news  정확 검색 ≈ 7~10초(원격 실측)  → HNSW 중앙 16ms / 최대 24ms
--          video 1.9만 행 — 플래너가 순차 스캔을 고른다(정확 검색 유지, 결과 영향 없음)
--        ⚠️ 원격 서버의 디스크·메모리는 로컬과 다르다. shared_buffers(현 128MB)가 색인
--           (blog ≈ 1GB)보다 작아 첫 질의는 디스크를 읽는다. 적용 후 실측 필요.
--
-- 순위 영향(⚠️ 있다) : HNSW는 근사 검색이라 정확 검색과 결과가 조금 다르다.
--        같은 질의 10건, 키워드 채널은 원격 실값 그대로, 벡터 채널만 정확/HNSW로 바꿔
--        RRF 최종 상위 30건을 비교했다(ef_search 200, iterative_scan relaxed_order, 청크 1,000개).
--
--          blog  색인 파라미터            벡터 recall@30  @200   최종 상위30 일치  상위10 완전동일  로컬 빌드
--                m=16, ef_construction=64     0.980      0.957   0.970 (최저 0.90)    6/10        45초
--                m=16, ef_construction=200    0.997      0.982   0.983 (최저 0.90)    8/10       167초  ← 채택
--                m=32, ef_construction=200    1.000      0.983   0.983 (최저 0.90)    9/10       491초
--          news  m=16, ef_construction=64     0.993      0.990   0.990 (최저 0.967)  (상위10 일치 최저 0.9)
--
--        blog는 원본 1건당 청크가 평균 59개라(문구 중복이 많다) 그래프 품질의 영향이 크다.
--        ef_construction 64 → 200이 빌드 3.7배로 recall@30을 0.98 → 0.997로 올린다.
--        평가셋(eval/search) 회귀를 적용 직후 다시 돌릴 것(scripts/eval_search.py).
--
-- 비용 : 색인 크기 ≈ 4KB/행(문서 §7.1과 같음) — blog ≈ 1GB, news ≈ 310MB, video ≈ 55MB.
--        빌드 시간 — 서버 실측 484행/초(m=16, ef_construction=64, maintenance_work_mem 1GB,
--        docs/database/vec_schema_unification_proposal.md §7.4)에 로컬 배율 3.7배를 곱한 **추정**:
--          blog ≈ 30분, news ≈ 12분, video ≈ 3분 (확인 필요). CONCURRENTLY라 읽기·쓰기를 막지 않는다.
--        쓰기(임베딩 백필) 비용이 늘어난다 — 행당 그래프 삽입.
--
-- 실행 : ⚠️ CREATE INDEX CONCURRENTLY는 **트랜잭션 블록 안에서 실행할 수 없다.**
--        BEGIN 없이 psql로 한 문장씩 실행한다(psql -f 기본 동작이 그렇다).
--        ⚠️ 병렬 빌드는 maintenance_work_mem만큼 공유 메모리(/dev/shm)를 잡는다.
--           컨테이너(기본 shm 64MB)에서 돌면 "could not resize shared memory segment …
--           No space left on device"로 실패한다(로컬 재현에서 실제로 났다).
--           shm을 늘리거나 max_parallel_maintenance_workers = 0으로 둔다.
--        서버 RAM이 maintenance_work_mem 2GB를 감당하는지 먼저 확인할 것(확인 필요).
--
-- 되돌리기 : DROP INDEX CONCURRENTLY idx_meta_*_vec_hnsw; (코드는 그대로 둬도 된다 —
--            색인이 없으면 정확 검색으로 돌아간다)
--
-- 적용 후 : ADR-014에 따라 정본 DDL(sql/meta_{video,news,blog}_vec.sql)의 주석 처리된
--           `CREATE INDEX … USING hnsw` 줄을 이 정의로 바꾼다.
-- ============================================================================

SET maintenance_work_mem = '2GB';            -- blog 그래프(≈1GB)가 메모리에 들어가야 한다(문서 §7.4)
SET max_parallel_maintenance_workers = 2;    -- 컨테이너면 0 (위 shm 주의)

-- ── A. 색인 (큰 것부터 — 효과가 큰 순서) ────────────────────────────────────

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meta_blog_vec_hnsw
    ON meta_blog_vec USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meta_news_vec_hnsw
    ON meta_news_vec USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- video는 1.9만 행이라 지금은 플래너가 순차 스캔을 고른다. 행이 늘면 자동으로 쓰인다.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meta_video_vec_hnsw
    ON meta_video_vec USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- dcat_dataset_vec(213행)는 색인이 필요 없다.

-- ── B. 통계 갱신 ────────────────────────────────────────────────────────────
-- 마지막 수동 ANALYZE 기록이 없다(autoanalyze만). 색인 생성 직후 플래너가
-- 새 색인 비용을 제대로 보도록 갱신한다.
ANALYZE meta_blog_vec;
ANALYZE meta_news_vec;
ANALYZE meta_video_vec;

-- ── C. 검증 ─────────────────────────────────────────────────────────────────
-- C-1. 색인이 유효한가 (CONCURRENTLY가 중간에 실패하면 INVALID로 남는다 → DROP 후 재시도)
SELECT c.relname, i.indisvalid, pg_size_pretty(pg_relation_size(c.oid)) AS size
FROM   pg_index i JOIN pg_class c ON c.oid = i.indexrelid
WHERE  c.relname LIKE 'idx_meta_%_vec_hnsw';

-- C-2. 검색 SQL이 색인을 타는가 — 'Index Scan using idx_meta_blog_vec_hnsw'가 보여야 한다
--      (질의 벡터 자리에 아무 행의 embedding을 넣어 확인)
-- BEGIN;
-- SET LOCAL hnsw.ef_search = 200; SET LOCAL hnsw.iterative_scan = relaxed_order;
-- EXPLAIN SELECT meta_id FROM meta_blog_vec
--   ORDER BY embedding <=> (SELECT embedding FROM meta_blog_vec LIMIT 1) LIMIT 1000;
-- ROLLBACK;

-- ── D. (권장, DDL 아님 · 재기동 필요) ────────────────────────────────────────
-- shared_buffers = 128MB(기본값)는 색인(blog ≈ 1GB)보다 작다. 서버 RAM을 확인한 뒤
-- RAM의 25% 안팎으로 올리는 것을 검토한다. 시연 직전 워밍(검색 몇 번)도 효과가 있다.
