# Naver Persona Insight

> **Last Updated:** 2026-07-10
> **dataset_id:** `naver_persona_insight`
> **source_type:** `persona_insight`

---

## 개요

네이버 쇼핑인사이트 성별/연령 API를 통해 카테고리별 페르소나 지수를 산출한다.
성별과 연령을 독립 가정하여 교차 추정(gender_pv × age_pv)하는 방식.

---

## API

| 항목 | 값 |
|------|-----|
| Gender Endpoint | `https://openapi.naver.com/v1/datalab/shopping/category/gender` |
| Age Endpoint | `https://openapi.naver.com/v1/datalab/shopping/category/age` |
| 인증 | Client ID / Client Secret (헤더) |
| 주의 | `category` 파라미터는 문자열(string), 배열 형식 사용 불가 |

---

## 수집 로직

- **독립 가정:** P(gender, age) ≈ P(gender) × P(age)
- **persona_index:** gender_pv × age_pv (정규화 후 교차)
- **inter_scale:** shopping_insight와 달리 anchor 카테고리 비교가 아니라, 전체 카테고리의
  성별/연령 시리즈를 stacking한 뒤 중앙값을 취해 계산한다 (gender_scale은 남녀 시리즈
  2N 포인트, age_scale은 6개 연령 시리즈 6N 포인트 stacking). `anchor_category` 설정값은
  다른 카테고리와 동일하게 수집 대상에는 포함되지만 scale 계산에서 특별히 취급되지 않는다.
- 성별 2 × 연령 6 = 12조합 per 카테고리

---

## 관련 파일

- 수집 코드: `3amd/naver_persona.py` (이전 버전) → `src/collectors/naver_persona.py` (예정)
- 설정: `configs/config.yaml`
