-- ============================================================================
-- external_ids에 수집 조건 집합 해시 추가 (video 외 전부)
--
-- 배경 : migration_2026_10_28_external_ids.sql에서는 video만 채우고 news·blog·
--        shopping·persona는 비워뒀다. 검색어·카테고리를 개별 값으로 넣으면
--        조건 하나만 겹쳐도 중복으로 오판되기 때문이었다.
--        그 대가로 **검색어가 완전히 같은 데이터셋도 탐지되지 않았다.**
--        집합 전체를 해시하면 둘 다 해결된다.
--
--          naver:news:3c639c929baf
--
--        완전히 같을 때만 겹치고, 하나라도 다르면 안 겹친다.
--
-- 정규화: 공백 제거 → 소문자 → 중복 제거 → 코드포인트 정렬 → '|' 결합
--        순서는 영향이 없다. 원문은 subjects 컬럼에 그대로 남아 있어 해시는
--        언제든 다시 만들 수 있다.
--
-- ⚠️ 정렬에 COLLATE "C"가 반드시 필요하다. DB 기본 콜레이션은 한글을 영문보다
--    앞에 두어 파이썬 sorted()와 결과가 달라진다.
--      SQL 기본      : 딥러닝|머신러닝|인공지능|ai
--      SQL COLLATE C : ai|딥러닝|머신러닝|인공지능   ← 파이썬과 같음
--    이 식은 register_dataset.subject_set_hash()와 같은 값을 내야 한다.
--
-- ⚠️ sha1이 아니라 sha256을 쓴다. PostgreSQL에 sha256()이 내장돼 있어 SQL에서도
--    같은 값을 만들 수 있다(sha1은 내장이 아니다). 앞 12자리만 쓴다.
--
-- ⚠️ 기간(temporal_start/end)은 해시에 넣지 않는다. 같은 검색어를 기간만 나눠
--    두 번 등록하면 해시가 같아진다 — 의도적이다. 같은 대상을 보고 있다는
--    사실이 드러나야 하고, 기간 차이는 temporal_* 컬럼이 이미 말해준다.
--
-- 트랜잭션 안에서 실행하고 §B 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. 수집 조건 집합 해시 추가 ─────────────────────────────────────────────
WITH norm AS (
    SELECT d.dataset_id,
           lower(d.source)  AS ns,          -- 'Naver' → 'naver'
           d.source_type,
           string_agg(DISTINCT lower(btrim(e.value)) COLLATE "C", '|'
                      ORDER BY lower(btrim(e.value)) COLLATE "C") AS norm_key
      FROM dcat_dataset d,
           jsonb_array_elements_text(d.subjects) AS e(value)
     WHERE d.source_type <> 'video'          -- video는 채널 ID를 이미 넣었다
       AND jsonb_typeof(d.subjects) = 'array'
       AND btrim(e.value) <> ''
     GROUP BY d.dataset_id, d.source, d.source_type
)
UPDATE dcat_dataset d
   SET external_ids = jsonb_build_array(
           n.ns || ':' || n.source_type || ':' ||
           substring(encode(sha256(convert_to(n.norm_key, 'UTF8')), 'hex') from 1 for 12)
       ) || d.external_ids              -- 원천 키를 앞, legacy를 뒤에
  FROM norm n
 WHERE d.dataset_id = n.dataset_id
   -- 재실행해도 중복으로 쌓이지 않게 한다
   AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                    WHERE x LIKE n.ns || ':' || n.source_type || ':%');


-- ── B. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- B-1. video가 아닌데 subjects가 있으면 해시를 갖는가
    SELECT string_agg(dataset_id, ', ') INTO txt
      FROM dcat_dataset d
     WHERE d.source_type <> 'video'
       AND jsonb_array_length(COALESCE(d.subjects, '[]'::jsonb)) > 0
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE lower(d.source) || ':' || d.source_type || ':%');
    IF txt IS NOT NULL THEN RAISE EXCEPTION 'B-1 실패: 해시 없는 데이터셋 — %', txt; END IF;

    -- B-2. legacy slug 보존
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'legacy:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-2 실패: legacy slug 유실 %건', n; END IF;

    -- B-3. video의 채널 키가 그대로인가
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE d.source_type = 'video'
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'youtube:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-3 실패: youtube 키 유실 %건', n; END IF;

    -- B-4. 해시가 12자리 16진수인가
    SELECT count(*) INTO n FROM dcat_dataset d,
           jsonb_array_elements_text(d.external_ids) AS x
     WHERE x LIKE lower(d.source) || ':' || d.source_type || ':%'
       AND x !~ (':[0-9a-f]{12}$');
    IF n > 0 THEN RAISE EXCEPTION 'B-4 실패: 해시 형식 위반 %건', n; END IF;

    -- B-5. shopping_insight와 shopping_insight_advertiser는 카테고리 50000148을
    --      공유하지만 집합이 달라 해시가 달라야 한다 (오탐 방지가 실제로 되는지)
    SELECT count(*) INTO n
      FROM dcat_dataset a, jsonb_array_elements_text(a.external_ids) ax,
           dcat_dataset b, jsonb_array_elements_text(b.external_ids) bx
     WHERE a.dataset_id = 'urn:naver:shopping_insight'
       AND b.dataset_id = 'urn:naver:shopping_insight_advertiser'
       AND ax = bx AND ax NOT LIKE 'legacy:%';
    IF n > 0 THEN RAISE EXCEPTION 'B-5 실패: 부분 겹침이 중복으로 판정됨 %건', n; END IF;

    RAISE NOTICE '검증 B-1~B-5 전부 통과';
END $$;
