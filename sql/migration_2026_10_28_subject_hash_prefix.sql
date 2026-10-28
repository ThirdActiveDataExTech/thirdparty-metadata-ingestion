-- ============================================================================
-- external_ids 해시 값에 'sha256-' 접두 추가
--
-- 배경 : migration_2026_10_28_subject_hash.sql이 넣은 값이
--          naver:news:3c639c929baf
--        인데, 이게 네이버가 발급한 ID처럼 보인다.
--
--        external_ids의 와이즈넛 정의는 adms:identifier —
--        "원천 포털이 데이터셋에 붙여 둔 고유번호"다. 우리 해시는 어떤 기관도
--        발급한 적이 없는 합성값이라 의미가 다르다. 동등성 비교라는 기능은
--        같지만 원천에 조회되지 않는다.
--
--        값 자체가 합성값임을 드러내도록 접두를 붙인다.
--          naver:news:sha256-3c639c929baf
--
--        네임스페이스는 'naver'로 유지되므로 youtube:UC... 와 구조는 같다.
--
-- 영향 : 비정형 5건(news·blog·shopping_insight·persona_insight). video는
--        채널 ID라 접두가 붙지 않는다 — 그쪽은 진짜 원천 발급 키다.
--
-- 트랜잭션 안에서 실행하고 §B 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. 접두 추가 ────────────────────────────────────────────────────────────
-- 이미 sha256-가 붙은 값은 건드리지 않는다(재실행 안전).
UPDATE dcat_dataset d
   SET external_ids = (
        SELECT jsonb_agg(
                 CASE WHEN x ~ ('^' || lower(d.source) || ':' || d.source_type || ':[0-9a-f]{12}$')
                      THEN regexp_replace(x, ':([0-9a-f]{12})$', ':sha256-\1')
                      ELSE x
                 END ORDER BY ord)
          FROM jsonb_array_elements_text(d.external_ids) WITH ORDINALITY AS t(x, ord))
 WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) y
                WHERE y ~ ('^' || lower(d.source) || ':' || d.source_type || ':[0-9a-f]{12}$'));


-- ── B. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- B-1. 접두 없는 해시가 남아 있지 않은가
    SELECT string_agg(d.dataset_id || ' → ' || x, ', ') INTO txt
      FROM dcat_dataset d, jsonb_array_elements_text(d.external_ids) AS x
     WHERE x ~ ('^' || lower(d.source) || ':' || d.source_type || ':[0-9a-f]{12}$');
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-1 실패: 접두 없는 해시 — %', txt; END IF;

    -- B-2. video가 아닌데 subjects가 있으면 sha256- 해시를 갖는가
    SELECT string_agg(dataset_id, ', ') INTO txt
      FROM dcat_dataset d
     WHERE d.source_type <> 'video'
       AND jsonb_array_length(COALESCE(d.subjects, '[]'::jsonb)) > 0
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE lower(d.source) || ':' || d.source_type || ':sha256-%');
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-2 실패: 해시 없는 데이터셋 — %', txt; END IF;

    -- B-3. legacy slug와 youtube 채널 키가 그대로인가 (jsonb_agg 재조립 중 유실 확인)
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'legacy:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-3 실패: legacy slug 유실 %건', n; END IF;

    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE d.source_type = 'video'
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'youtube:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-3 실패: youtube 채널 키 유실 %건', n; END IF;

    -- B-4. video에는 sha256- 가 붙지 않았는가 (채널 ID는 진짜 원천 키다)
    SELECT string_agg(dataset_id, ', ') INTO txt FROM dcat_dataset d
     WHERE d.source_type = 'video'
       AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                    WHERE x LIKE '%sha256-%');
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-4 실패: video에 해시가 붙음 — %', txt; END IF;

    RAISE NOTICE '검증 B-1~B-4 전부 통과';
END $$;
