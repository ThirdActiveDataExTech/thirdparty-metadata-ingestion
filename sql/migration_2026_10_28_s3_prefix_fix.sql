-- ============================================================================
-- data_registry.s3_*_prefix 정정
--
-- 배경 : URN 전환 검증 중 레지스트리 경로가 코드가 실제로 쓰는 경로와 다른 것을
--        발견했다. URN 전환과는 무관한 기존 문제다.
--
-- 코드가 만드는 경로 (src/storage/jsonld_export.export_dataset,
--                    src/storage/raw_export.*):
--     raw/{source_type}/{storage_key(dataset_id)}/
--     jsonld/{source_type}/{storage_key(dataset_id)}/
--
-- 불일치 14건이 두 가지 성격으로 갈린다.
--
-- (1) source_type 조각이 틀린 3건 — shopping/persona
--     레지스트리: raw/shopping/naver_shopping_insight/
--     코드      : raw/shopping_insight/naver_shopping_insight/
--     seeds.sql의 샘플값이 'shopping'으로 적혀 있던 것이 DB에 들어왔다.
--     source_type은 'shopping_insight'/'persona_insight'이므로 레지스트리가 틀렸다.
--     이 3건은 S3 객체가 0개라 실제 피해는 없었다.
--
-- (2) 값이 빈 문자열인 11건 — youtube
--     수집은 했지만(meta_video 29,026행) JSON-LD·raw 내보내기를 한 적이 없어
--     경로가 만들어지지 않았다. '아직 없음'이 맞는 상태다.
--     다만 ''와 NULL이 섞여 있어(hbm_video_collection만 NULL) NULL로 통일한다.
--     **경로를 미리 채우지 않는다** — 객체가 없는데 경로가 있다고 적으면
--     레지스트리가 거짓말을 하게 된다. 첫 내보내기 때 코드가 채운다.
--
-- 트랜잭션 안에서 실행하고 §C 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. source_type 조각 정정 (3건) ──────────────────────────────────────────
-- 문자열 치환이 아니라 dcat_dataset.source_type에서 다시 조립한다.
-- 같은 실수가 반복되지 않도록 원본(source_type)을 근거로 쓴다.
--
-- ⚠️ ltrim(dataset_id, 'urn:')을 쓰면 안 된다. ltrim의 두 번째 인자는 접두사가
--    아니라 **문자 집합**이라 u·r·n·: 를 왼쪽에서 계속 깎는다.
--      ltrim('urn:naver:news_ai', 'urn:') = 'aver:news_ai'   ← n까지 먹힌다
--    regexp_replace로 접두사만 제거한다. 이 식은 s3_client.storage_key()의
--    파이썬 구현과 같은 결과를 내야 한다.
UPDATE data_registry r
   SET s3_raw_prefix    = 'raw/'    || d.source_type || '/' ||
                          replace(regexp_replace(d.dataset_id, '^urn:', ''), ':', '_') || '/',
       s3_jsonld_prefix = 'jsonld/' || d.source_type || '/' ||
                          replace(regexp_replace(d.dataset_id, '^urn:', ''), ':', '_') || '/'
  FROM dcat_dataset d
 WHERE r.dataset_id = d.dataset_id
   AND r.s3_raw_prefix IS NOT NULL
   AND r.s3_raw_prefix <> ''
   AND r.s3_raw_prefix <> 'raw/' || d.source_type || '/' ||
                          replace(regexp_replace(d.dataset_id, '^urn:', ''), ':', '_') || '/';


-- ── B. 빈 문자열을 NULL로 통일 (11건) ───────────────────────────────────────
UPDATE data_registry
   SET s3_raw_prefix    = NULLIF(s3_raw_prefix, ''),
       s3_jsonld_prefix = NULLIF(s3_jsonld_prefix, '')
 WHERE s3_raw_prefix = '' OR s3_jsonld_prefix = '';


-- ── C. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- C-1. 값이 있는 행은 전부 코드가 만드는 경로와 같은가
    SELECT string_agg(r.dataset_id || ' = ' || r.s3_raw_prefix, E'\n       ')
      INTO txt
      FROM data_registry r JOIN dcat_dataset d USING (dataset_id)
     WHERE r.s3_raw_prefix IS NOT NULL
       AND r.s3_raw_prefix <> 'raw/' || d.source_type || '/' ||
                              replace(regexp_replace(d.dataset_id, '^urn:', ''), ':', '_') || '/';
    IF txt IS NOT NULL THEN
        RAISE EXCEPTION 'C-1 실패: raw 경로 불일치 —%s', E'\n       ' || txt;
    END IF;

    SELECT string_agg(r.dataset_id, ', ') INTO txt
      FROM data_registry r JOIN dcat_dataset d USING (dataset_id)
     WHERE r.s3_jsonld_prefix IS NOT NULL
       AND r.s3_jsonld_prefix <> 'jsonld/' || d.source_type || '/' ||
                                 replace(regexp_replace(d.dataset_id, '^urn:', ''), ':', '_') || '/';
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'C-1 실패: jsonld 경로 불일치 — %', txt; END IF;

    -- C-2. 빈 문자열이 남아 있지 않은가
    SELECT count(*) INTO n FROM data_registry
     WHERE s3_raw_prefix = '' OR s3_jsonld_prefix = '';
    IF n > 0 THEN RAISE EXCEPTION 'C-2 실패: 빈 문자열 %건', n; END IF;

    -- C-3. raw와 jsonld가 같이 있거나 같이 없는가
    SELECT count(*) INTO n FROM data_registry
     WHERE (s3_raw_prefix IS NULL) <> (s3_jsonld_prefix IS NULL);
    IF n > 0 THEN RAISE EXCEPTION 'C-3 실패: raw/jsonld 한쪽만 설정된 행 %건', n; END IF;

    RAISE NOTICE '검증 C-1~C-3 전부 통과';
END $$;
