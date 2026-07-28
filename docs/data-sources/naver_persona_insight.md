# Naver Persona Insight

> **Last Updated:** 2026-07-28
> **dataset_id:** `naver_persona_insight` (외 사용자 정의 데이터셋 추가 가능)
> **source_type:** `persona_insight`
> **상태:** Collector 구현·검증 완료(§6.1), 실 API로 검증됨

---

## 개요

네이버 쇼핑인사이트 성별/연령 API를 통해 카테고리별 페르소나 지수를 산출한다.
성별과 연령을 독립 가정하여 교차 추정(gender_pv × age_pv)하는 방식. shopping_insight와
달리 anchor 개념이 없고, 카테고리별로 독립 호출한다(§4.3).

## API

| 항목 | 값 |
|------|-----|
| Gender Endpoint | `https://openapi.naver.com/v1/datalab/shopping/category/gender` |
| Age Endpoint | `https://openapi.naver.com/v1/datalab/shopping/category/age` |
| 인증 | Client ID / Client Secret (헤더) |
| 주의 | `category` 파라미터는 문자열(string), 배열 형식 사용 불가 |
| 호출 구조 | 카테고리 1개당 2회 호출(성별 API + 연령 API) |

## 수집 로직

- **독립 가정**: P(gender, age) ≈ P(gender) × P(age)
- **persona_index**: gender_pv × age_pv (정규화 후 교차, 실측 교차분포 아님에 유의)
- **gender_scale/age_scale**: shopping_insight의 단일 scale_factor와 달리 성별/연령
  축을 분리해서 보정 — anchor 카테고리 비교가 아니라 전체 카테고리의 성별/연령 시리즈를
  stacking한 뒤 중앙값을 취해 계산(gender_scale은 남녀 시리즈 2N 포인트, age_scale은
  6개 연령 시리즈 6N 포인트 stacking). `naver_datalab_scale.py`의 `compute_inter_scale`을
  shopping_insight와 그대로 공유 재사용
- 성별 2 × 연령 6 = 12조합 per 카테고리
- **OVERLAP_DAYS=14** + **최초 수집 소급**(`temporal_start`) — shopping_insight와
  동일한 원리, 2026-07-28 수정. 상세: `04_Collection_Pipeline_Operations.md` §6.2
- API 호출 간 `time.sleep(1초)` rate limiting

## 수집 대상 (실 DB 기준, 2026-07-28)

`naver_persona_insight` 데이터셋에 카테고리 4개 등록됨(anchor 개념 없음 — 카테고리
목록은 `meta_naver_persona` 테이블 직접 조회, `SELECT category_id, category_name
FROM meta_naver_persona WHERE dataset_id='naver_persona_insight'`).

## 등록 방법

```bash
python scripts/register_dataset.py persona_insight \
    --title "..." --description "..." \
    --categories "50000148:패션의류,50001828:패션의류>남성의류" \
    --temporal-start 2025-01-01   # 선택 — 최초 수집 소급 시작일
```

## 관련 파일

- 콜렉터: `src/collectors/naver_persona_collector.py`(성별/연령 API 독립 호출),
  `src/collectors/naver_datalab_scale.py`(shopping_insight와 공유)
- 파이프라인: `src/pipelines/naver_persona_pipeline.py`
- DB: `src/database/meta_naver_persona.py`
- DDL: `sql/meta_naver_persona.sql`, `sql/active_meta_naver_persona.sql`
- 레거시 원본(포팅 참고용): `3amd/naver_persona.py`
