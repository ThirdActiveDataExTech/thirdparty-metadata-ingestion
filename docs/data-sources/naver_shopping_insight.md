# Naver Shopping Insight

> **Last Updated:** 2026-07-01
> **dataset_id:** `naver_shopping_insight`
> **source_type:** `shopping`

---

## 개요

네이버 데이터랩 쇼핑인사이트 API를 통해 카테고리별 일간 검색량 지수를 수집한다.
수치는 절대값이 아닌 상대 지수(최대=100)이며, anchor 카테고리 기준으로 보정한다.

---

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://openapi.naver.com/v1/datalab/shopping/categories` |
| 인증 | Client ID / Client Secret (헤더) |
| 응답 | 상대 지수 (최대 100) |
| 기간 제한 | 1회 최대 90일 |
| 필터 | 성별(female/male) × 연령(10s~50s) = 12조합 |

---

## 수집 로직

- **anchor 카테고리:** `50000148` (식품>음료) — 모든 카테고리의 기준점
- **intra_scale:** anchor를 기준으로 같은 수집 회차 내 보정
- **inter_scale:** 수집 회차 간 anchor 중앙값 비율로 보정
- **scale_factor:** intra_scale × inter_scale
- **2단계 초기 수집:** 1년치 소급 → 28일 overlap 검증

---

## 수집 대상 카테고리

`config.yaml` 참조 — anchor 포함 14개 카테고리

---

## 관련 파일

- 수집 코드: `3amd/naver_shopping_insight.py` (이전 버전) → `src/collectors/naver_shopping_insight.py` (예정)
- 설정: `configs/config.yaml`
- DDL: `sql/dcat_dataset.sql`, `sql/dcat_provenance.sql`
