-- ============================================================================
-- external_ids에 원천 객체 키 보강
--
-- 배경 : 2026-10-28 와이즈넛에 "dataset_id는 수집 단위 키를 쓰고, 원천 객체
--        키는 external_ids에 보존한다"고 회신했다. 현재는 legacy slug만 들어
--        있어 그 약속이 지켜지지 않은 상태다.
--
-- 형식 : 와이즈넛 정의대로 '네임스페이스:값' 문자열 배열.
--        객체({"key": ...})가 아니다.
--
-- 용도 : 같은 데이터셋이 다른 경로로 두 번 수집되면 이 값이 겹쳐 중복을
--        탐지할 수 있게 한다(와이즈넛 중복 병합 판정 근거).
--
-- ⚠️ video(YouTube)만 채운다.
--    채널 ID는 원천이 발급한 진짜 객체 키라 중복 판정 근거로 쓸 수 있다.
--    news·blog의 검색어와 shopping/persona의 카테고리 ID는 **원천 객체가 아니라
--    우리가 정한 수집 조건**이다. 이걸 넣으면 카테고리 하나만 겹쳐도 서로 다른
--    데이터셋이 중복으로 판정돼 오탐이 난다. 실제로 shopping_insight와
--    shopping_insight_advertiser는 카테고리 50000148을 공유한다.
--    → 비정형 중 video 외에는 legacy slug만 유지한다.
--
-- 반대로 채널 겹침은 **참(true) 양성**이다. urn:youtube:hbm_video_collection은
-- samsung_official·sk_hynix_official과 같은 채널을 수집 중이고, 그 사실이
-- 드러나는 것이 이 컬럼의 목적이다.
--
-- 트랜잭션 안에서 실행하고 §B 검증을 통과한 뒤 COMMIT 한다.
-- ============================================================================

-- ── A. video 데이터셋: subjects의 채널 ID를 youtube: 네임스페이스로 추가 ──────
-- subjects는 두 형태가 공존한다(2026-07-28 확장):
--   발견형 단일      : ["UCxxxx"]
--   채널+영상 혼합형 : {"channels": ["UCxxxx", ...], "videos": [...]}
-- 아래 CTE가 둘 다 처리한다. videos(개별 영상 ID)는 넣지 않는다 — 영상은
-- 데이터셋의 원천 객체가 아니라 그 안의 항목이고, meta_video가 이미 들고 있다.

WITH channels AS (
    SELECT d.dataset_id,
           CASE jsonb_typeof(d.subjects)
                WHEN 'array'  THEN d.subjects
                WHEN 'object' THEN COALESCE(d.subjects -> 'channels', '[]'::jsonb)
                ELSE '[]'::jsonb
           END AS ch
      FROM dcat_dataset d
     WHERE d.source_type = 'video'
),
new_ids AS (
    SELECT c.dataset_id,
           jsonb_agg(DISTINCT 'youtube:' || e.value) AS ids
      FROM channels c, jsonb_array_elements_text(c.ch) AS e(value)
     GROUP BY c.dataset_id
)
UPDATE dcat_dataset d
   SET external_ids = n.ids || d.external_ids   -- 원천 키를 앞, legacy를 뒤에
  FROM new_ids n
 WHERE d.dataset_id = n.dataset_id
   -- 재실행해도 중복으로 쌓이지 않게 한다
   AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                    WHERE x LIKE 'youtube:%');


-- ── B. 검증 ─────────────────────────────────────────────────────────────────
DO $$
DECLARE n INT; txt TEXT;
BEGIN
    -- B-1. video 전부 youtube: 키를 갖는가
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE d.source_type = 'video'
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'youtube:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-1 실패: youtube 키 없는 video 데이터셋 %건', n; END IF;

    -- B-2. legacy slug가 그대로 남아 있는가 (덮어쓰지 않았는지)
    SELECT count(*) INTO n FROM dcat_dataset d
     WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                        WHERE x LIKE 'legacy:%');
    IF n > 0 THEN RAISE EXCEPTION 'B-2 실패: legacy slug 유실 %건', n; END IF;

    -- B-3. 전부 '네임스페이스:값' 문자열 배열인가
    SELECT count(*) INTO n FROM dcat_dataset d,
           jsonb_array_elements(d.external_ids) AS e
     WHERE jsonb_typeof(e) <> 'string' OR (e #>> '{}') NOT LIKE '%:%';
    IF n > 0 THEN RAISE EXCEPTION 'B-3 실패: 형식 위반 원소 %건', n; END IF;

    -- B-4. video 외에는 legacy만 있는가 (오탐 방지 결정이 지켜졌는지)
    SELECT string_agg(dataset_id, ', ') INTO txt FROM dcat_dataset d
     WHERE d.source_type <> 'video'
       AND EXISTS (SELECT 1 FROM jsonb_array_elements_text(d.external_ids) x
                    WHERE x NOT LIKE 'legacy:%');
    IF txt IS NOT NULL THEN
        RAISE EXCEPTION 'B-4 실패: video가 아닌데 legacy 외 키가 있음 — %', txt;
    END IF;

    RAISE NOTICE '검증 B-1~B-4 전부 통과';
END $$;
