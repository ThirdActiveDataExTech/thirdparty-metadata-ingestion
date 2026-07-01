# Naver Persona Insight

> **Last Updated:** 2026-07-01
> **dataset_id:** `naver_persona_insight`
> **source_type:** `shopping`

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
- **inter_scale:** anchor 카테고리 기준 수집 회차 간 보정
- 성별 2 × 연령 6 = 12조합 per 카테고리

---

## 관련 파일

- 수집 코드: `3amd/naver_persona.py` (이전 버전) → `src/collectors/naver_persona.py` (예정)
- 설정: `configs/config.yaml`
