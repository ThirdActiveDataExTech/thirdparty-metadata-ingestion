-- ============================================================================
-- dataset_id URN 전환 — slug → urn:{소스}:{수집단위키}
--
-- 배경 : 와이즈넛 「백엔드 설계 초안」 v2 별첨은 dataset_id를 URN으로 규정한다.
--        2026-10-28 비정형 적용 방안(원천 객체 키 대신 수집 단위 키 사용)을
--        와이즈넛이 승인했다.
-- 근거 : docs/database/dataset_id_urn_migration.md
--        docs/adr/014_Schema_Ownership_And_Change_Control.md
--
-- ⚠️ 와이즈넛 정형 데이터 적재 개시 전에 수행해야 한다. 적재 후에는 §A의
--    ALTER TABLE이 양측 합의 사항이 되고, 전환 범위에 상대 데이터가 들어간다.
--
-- 실행 전제 (2026-10-28 실측):
--   - dcat_dataset 18건, 전부 external_ids에 legacy:<slug> 보존 완료
--   - dcat_provenance 끊어진 참조 0건
--   - 코드·설정에 dataset_id 하드코딩 없음 (configs/ 비어 있음)
--   - 케이웨어 연계 없음 → 외부 통보 불필요
--
-- S3 경로는 바꾸지 않는다. 경로가 식별자와 일치할 필요가 없고, S3에는 rename이
-- 없어 복사 후 삭제 비용이 크다. data_registry.s3_*_prefix도 그대로 둔다.
-- 결과적으로 S3 경로에 legacy slug가 남아 external_ids와 이중으로 추적된다.
--
-- 반드시 트랜잭션 안에서 실행하고, §D 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. 우리 FK 8개에 ON UPDATE CASCADE 부여 ─────────────────────────────────
-- 와이즈넛이 만든 테이블(dcat_dataset_attr, active_meta_dataset,
-- dcat_dataset_relation ×2, meta_datagokr_file)은 이미 CASCADE라 건드리지 않는다.
-- 여기 8개만 NO ACTION이어서 §B의 UPDATE가 전파되지 않는다.
-- ON DELETE는 기존 CASCADE를 그대로 유지한다.

ALTER TABLE data_registry
    DROP CONSTRAINT data_registry_dataset_id_fkey,
    ADD  CONSTRAINT data_registry_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE dataset_credentials
    DROP CONSTRAINT dataset_credentials_dataset_id_fkey,
    ADD  CONSTRAINT dataset_credentials_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE dcat_dataset_vec
    DROP CONSTRAINT dcat_dataset_vec_dataset_id_fkey,
    ADD  CONSTRAINT dcat_dataset_vec_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE meta_video
    DROP CONSTRAINT meta_video_dataset_id_fkey,
    ADD  CONSTRAINT meta_video_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE meta_news
    DROP CONSTRAINT meta_news_dataset_id_fkey,
    ADD  CONSTRAINT meta_news_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE meta_blog
    DROP CONSTRAINT meta_blog_dataset_id_fkey,
    ADD  CONSTRAINT meta_blog_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE meta_shopping_insight
    DROP CONSTRAINT meta_shopping_insight_dataset_id_fkey,
    ADD  CONSTRAINT meta_shopping_insight_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE meta_persona_insight
    DROP CONSTRAINT meta_persona_insight_dataset_id_fkey,
    ADD  CONSTRAINT meta_persona_insight_dataset_id_fkey
         FOREIGN KEY (dataset_id) REFERENCES dcat_dataset(dataset_id)
         ON UPDATE CASCADE ON DELETE CASCADE;


-- ── B. 매핑표 ────────────────────────────────────────────────────────────────
-- 규칙: urn:{소스}:{수집단위키}
--   - naver_*   → urn:naver:*     (naver_ 접두 제거)
--   - youtube_* → urn:youtube:*   (youtube_ 접두 제거)
--   - user_*    → urn:youtube:*   (user_ 접두 제거 — 사용자 큐레이션 여부는
--                                  dataset_origin 컬럼이 이미 구분한다)
-- 문자열 치환이 아니라 명시적 매핑으로 둔다. 18건뿐이고, 감사 가능해야 한다.

CREATE TEMP TABLE urn_map (old_id TEXT PRIMARY KEY, new_id TEXT NOT NULL UNIQUE)
    ON COMMIT DROP;

INSERT INTO urn_map (old_id, new_id) VALUES
    ('naver_blog_ai',                     'urn:naver:blog_ai'),
    ('naver_news_ai',                     'urn:naver:news_ai'),
    ('naver_persona_insight',             'urn:naver:persona_insight'),
    ('naver_shopping_insight',            'urn:naver:shopping_insight'),
    ('naver_shopping_insight_advertiser', 'urn:naver:shopping_insight_advertiser'),
    ('user_hbm_video_collection',         'urn:youtube:hbm_video_collection'),
    ('youtube_asan_medical_center',       'urn:youtube:asan_medical_center'),
    ('youtube_biondwi',                   'urn:youtube:biondwi'),
    ('youtube_daehang',                   'urn:youtube:daehang'),
    ('youtube_ncc_koreacancerinfo',       'urn:youtube:ncc_koreacancerinfo'),
    ('youtube_ohseheon',                  'urn:youtube:ohseheon'),
    ('youtube_samsung_medical_center',    'urn:youtube:samsung_medical_center'),
    ('youtube_samsung_official',          'urn:youtube:samsung_official'),
    ('youtube_seoul_st_marys',            'urn:youtube:seoul_st_marys'),
    ('youtube_severance',                 'urn:youtube:severance'),
    ('youtube_sk_hynix_official',         'urn:youtube:sk_hynix_official'),
    ('youtube_snuh',                      'urn:youtube:snuh'),
    ('youtube_songseng',                  'urn:youtube:songseng');

-- 매핑표가 현재 DB와 1:1로 맞는지 먼저 확인한다. 어긋나면 여기서 중단된다.
DO $$
DECLARE missing INT; extra INT;
BEGIN
    SELECT count(*) INTO missing
      FROM dcat_dataset d LEFT JOIN urn_map m ON d.dataset_id = m.old_id
     WHERE m.old_id IS NULL;
    SELECT count(*) INTO extra
      FROM urn_map m LEFT JOIN dcat_dataset d ON d.dataset_id = m.old_id
     WHERE d.dataset_id IS NULL;
    IF missing > 0 OR extra > 0 THEN
        RAISE EXCEPTION '매핑표 불일치 — 매핑 없는 데이터셋 %건, 대상 없는 매핑 %건',
                        missing, extra;
    END IF;
END $$;


-- ── C. 전환 ─────────────────────────────────────────────────────────────────
-- C-1. dcat_provenance를 먼저 바꾼다.
--      이 테이블은 FK가 없다(2026-10-27, 데이터셋 폐기 후에도 이력을 보존하기
--      위해 제거). 전파가 안 되므로 명시적 UPDATE가 필요하고, 빠뜨리면 조용히
--      끊어진 참조가 남는다. §D-3에서 확인한다.
UPDATE dcat_provenance p
   SET dataset_id = m.new_id
  FROM urn_map m
 WHERE p.dataset_id = m.old_id;

-- C-2. dcat_dataset UPDATE → FK 13개가 전부 CASCADE이므로 자식이 따라온다.
--      신·구 값이 'urn:' 접두로 완전히 분리돼 있어 PK 충돌은 발생하지 않는다.
UPDATE dcat_dataset d
   SET dataset_id = m.new_id
  FROM urn_map m
 WHERE d.dataset_id = m.old_id;


-- ── D. 검증 — 하나라도 실패하면 EXCEPTION, 롤백하고 원인을 찾을 것 ───────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- D-1. 전부 URN 형식인가
    SELECT count(*) INTO n FROM dcat_dataset WHERE dataset_id !~ '^urn:[a-z0-9]+:';
    IF n > 0 THEN RAISE EXCEPTION 'D-1 실패: URN 형식이 아닌 dataset_id %건', n; END IF;

    -- D-2. 건수 보존
    SELECT count(*) INTO n FROM dcat_dataset;
    IF n <> 18 THEN RAISE EXCEPTION 'D-2 실패: dcat_dataset %건 (기대 18건)', n; END IF;

    -- D-3. dcat_provenance 끊어진 참조 (FK가 없어 DB가 막아주지 않는다)
    SELECT count(*) INTO n FROM dcat_provenance p
      LEFT JOIN dcat_dataset d USING (dataset_id) WHERE d.dataset_id IS NULL;
    IF n > 0 THEN RAISE EXCEPTION 'D-3 실패: dcat_provenance 끊어진 참조 %건', n; END IF;

    -- D-4. 자식 테이블에 구 slug 잔존 여부 (CASCADE가 실제로 돌았는지)
    SELECT string_agg(t || '=' || c, ', ') INTO txt FROM (
        SELECT 'meta_video' t, count(*) c FROM meta_video WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'meta_news', count(*) FROM meta_news WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'meta_blog', count(*) FROM meta_blog WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'meta_shopping_insight', count(*) FROM meta_shopping_insight WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'meta_persona_insight', count(*) FROM meta_persona_insight WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'data_registry', count(*) FROM data_registry WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'dcat_dataset_vec', count(*) FROM dcat_dataset_vec WHERE dataset_id !~ '^urn:'
        UNION ALL SELECT 'dcat_provenance', count(*) FROM dcat_provenance WHERE dataset_id !~ '^urn:'
    ) s WHERE c > 0;
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'D-4 실패: 구 slug 잔존 — %', txt; END IF;

    -- D-5. legacy slug가 external_ids에 보존돼 있는가 (롤백·추적의 유일한 근거)
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) e
                        WHERE e LIKE 'legacy:%');
    IF n > 0 THEN RAISE EXCEPTION 'D-5 실패: legacy slug 미보존 %건', n; END IF;

    -- D-6. 스펙 상한 100자
    SELECT max(length(dataset_id)) INTO n FROM dcat_dataset;
    IF n > 100 THEN RAISE EXCEPTION 'D-6 실패: dataset_id 최대 길이 %자 (상한 100)', n; END IF;

    RAISE NOTICE '검증 D-1~D-6 전부 통과 (최대 길이 %자)', n;
END $$;
