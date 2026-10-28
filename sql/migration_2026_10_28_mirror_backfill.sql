-- ============================================================================
-- dcat_dataset 미러 컬럼 백필 (item_count · temporal_start)
--
-- 배경 : sql/dcat_dataset.sql과 sql/data_registry.sql의 주석은 두 테이블의
--        item_count·temporal_start/end가 "수집 후 자동 갱신되며 동기화된다"고
--        적어 두었다. **그런데 동기화하는 코드가 없었다.**
--        파이프라인 5종이 전부 update_data_registry만 부르고 dcat_dataset은
--        손대지 않았다(shopping/persona만 첫 수집 때 temporal_start를 한 번).
--
--        2026-10-28 실측: 18건 중 14건 불일치.
--          urn:naver:blog_ai            dcat 3     / registry 2,192
--          urn:youtube:biondwi          dcat NULL  / registry 17,932
--
--        dcat_dataset은 와이즈넛과 공용하는 카탈로그다. 여기 값이 틀리면
--        상대가 읽는 카탈로그가 데이터셋 규모를 틀리게 말한다.
--
-- 코드 수정(같은 커밋):
--   - dcat.update_data_registry가 미러 컬럼을 같은 트랜잭션에서 함께 갱신한다.
--     호출부가 잊어버릴 수 있는 구조였으므로 한 곳에서 보장한다.
--   - youtube/news/blog 파이프라인에 _current_temporal_start()를 추가했다.
--     세 파이프라인은 temporal_start를 계산조차 하지 않고 있었다.
--
-- temporal_end는 백필하지 않는다 — NULL이 "현재 진행 중(open-ended)"을 뜻한다
-- (sql/dcat_dataset.sql temporal_end 주석).
--
-- 트랜잭션 안에서 실행하고 §B 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A-1. item_count — data_registry(원본)에서 가져온다 ──────────────────────
UPDATE dcat_dataset d
   SET item_count = r.item_count,
       updated_at = now()
  FROM data_registry r
 WHERE d.dataset_id = r.dataset_id
   AND d.item_count IS DISTINCT FROM r.item_count;


-- ── A-2. temporal_start — youtube·news·blog만 ──────────────────────────────
-- ⚠️ shopping_insight·persona_insight는 건드리지 않는다.
--    이 둘은 temporal_start를 **소급 수집 시작일로도 읽는다**
--    (naver_shopping_pipeline.py:93 `desired_start = dataset.get("temporal_start")`).
--    최초 수집 때 이 값까지 거슬러 올라가 모으고, 그 뒤 실제 수집된 가장 이른
--    날짜로 갱신하는 설계다. 여기서 실데이터 MIN으로 덮으면 "어디까지 모으려
--    했는가"가 사라진다.
--
--    실제로 둘 다 의도와 실데이터가 어긋나 있다 — 소급 수집이 완료되지 않았다.
--      urn:naver:shopping_insight  의도 2025-06-17 / 실데이터 2026-06-30
--      urn:naver:persona_insight   의도 2025-06-18 / 실데이터 2026-06-30
--    별도 판단이 필요한 사안이라 이 마이그레이션의 범위 밖에 둔다.
--
-- youtube·news·blog는 temporal_start를 읽는 곳이 없어 순수 기술(記述) 컬럼이다.
-- 파이프라인 헬퍼 _current_temporal_start()와 같은 식을 쓴다.
WITH actual AS (
    SELECT dataset_id, MIN(published_at)::date AS ts FROM meta_video GROUP BY 1
    UNION ALL
    SELECT dataset_id, MIN(published_at)::date FROM meta_news GROUP BY 1
    UNION ALL
    SELECT dataset_id, MIN(published_at)::date FROM meta_blog GROUP BY 1
)
UPDATE data_registry r
   SET temporal_start = a.ts,
       updated_at     = now()
  FROM actual a
 WHERE r.dataset_id = a.dataset_id
   AND a.ts IS NOT NULL
   AND r.temporal_start IS DISTINCT FROM a.ts;

WITH actual AS (
    SELECT dataset_id, MIN(published_at)::date AS ts FROM meta_video GROUP BY 1
    UNION ALL
    SELECT dataset_id, MIN(published_at)::date FROM meta_news GROUP BY 1
    UNION ALL
    SELECT dataset_id, MIN(published_at)::date FROM meta_blog GROUP BY 1
)
UPDATE dcat_dataset d
   SET temporal_start = a.ts,
       updated_at     = now()
  FROM actual a
 WHERE d.dataset_id = a.dataset_id
   AND a.ts IS NOT NULL
   AND d.temporal_start IS DISTINCT FROM a.ts;


-- ── B. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE txt TEXT; n INT;
BEGIN
    -- B-1. item_count가 두 테이블에서 같은가
    SELECT string_agg(d.dataset_id || ' (dcat ' || COALESCE(d.item_count::text,'NULL')
                      || ' / registry ' || COALESCE(r.item_count::text,'NULL') || ')', ', ')
      INTO txt
      FROM dcat_dataset d JOIN data_registry r USING (dataset_id)
     WHERE d.item_count IS DISTINCT FROM r.item_count;
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-1 실패: item_count 불일치 — %', txt; END IF;

    -- B-2. temporal_start가 두 테이블에서 같은가
    SELECT string_agg(dataset_id, ', ') INTO txt
      FROM dcat_dataset d JOIN data_registry r USING (dataset_id)
     WHERE d.temporal_start IS DISTINCT FROM r.temporal_start;
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-2 실패: temporal_start 불일치 — %', txt; END IF;

    -- B-2b. youtube/news/blog는 실데이터 MIN과 같아야 한다
    SELECT string_agg(d.dataset_id, ', ') INTO txt
      FROM dcat_dataset d
      JOIN (SELECT dataset_id, MIN(published_at)::date AS ts FROM meta_video GROUP BY 1
            UNION ALL SELECT dataset_id, MIN(published_at)::date FROM meta_news GROUP BY 1
            UNION ALL SELECT dataset_id, MIN(published_at)::date FROM meta_blog GROUP BY 1) a
        ON a.dataset_id = d.dataset_id
     WHERE a.ts IS NOT NULL AND d.temporal_start IS DISTINCT FROM a.ts;
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-2b 실패: 실데이터와 불일치 — %', txt; END IF;

    -- B-3. 데이터가 있는데 item_count가 NULL인 데이터셋이 없는가
    SELECT string_agg(dataset_id, ', ') INTO txt
      FROM data_registry WHERE item_count IS NULL AND status <> 'pending';
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-3 실패: item_count NULL — %', txt; END IF;

    -- B-4. temporal_end를 건드리지 않았는가 (open-ended 의미 보존)
    SELECT count(*) INTO n FROM dcat_dataset WHERE temporal_end IS NOT NULL;
    RAISE NOTICE '검증 B-1~B-3 통과 (temporal_end 설정된 데이터셋 %건 — 변경 없음)', n;
END $$;
