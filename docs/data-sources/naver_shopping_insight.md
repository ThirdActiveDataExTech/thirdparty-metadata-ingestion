# Naver Shopping Insight

> **Last Updated:** 2026-07-28
> **dataset_id:** `urn:naver:shopping_insight` (외 사용자 정의 데이터셋 추가 가능)
> **source_type:** `shopping_insight`
> **상태:** Collector 구현·검증 완료(§6.1), 실 API로 검증됨

---

## 개요

네이버 데이터랩 쇼핑인사이트 API를 통해 카테고리별 일간 검색량 지수를 수집한다.
수치는 절대값이 아닌 상대 지수(최대=100)이며, anchor 카테고리 기준으로 보정한다.
선언형 소스라 카테고리 목록은 등록 시점에 고정되고 Collector가 스스로 바꾸지 않는다
(`04_Collection_Pipeline_Operations.md` §4.2).

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://openapi.naver.com/v1/datalab/shopping/categories` |
| 인증 | Client ID / Client Secret (헤더) |
| 응답 | 상대 지수 (최대 100, 호출 배치 내에서만 유효) |
| 기간 제한 | 1회 최대 90일(사실상 무제한 — 넓은 범위도 한 번에 호출) |
| 카테고리 제한 | 1회 호출 최대 3개 — anchor를 모든 배치에 포함시켜 배치 간 정규화 |
| 필터 | 성별(female/male) × 연령(10s~60s, 6개) = 12조합 |

## 수집 로직

- **anchor 카테고리**: 등록 시 첫 번째로 지정한 카테고리가 자동 지정(§4.3) — 지금
  운영 중인 `urn:naver:shopping_insight`는 `50000148`(패션의류)
- **intra_scale**: 동일 수집 내 배치 간 M(최댓값) 차이 보정 — 첫 유효 배치를 기준으로
  median(ref_anchor/batch_anchor)
- **inter_scale**: 수집 구간 간 M 차이 보정 — DB 기존 anchor 값과 신규 anchor 값의
  겹치는 기간 median 비율
- **scale_factor** = intra_scale × inter_scale, **pseudo_volume** = raw_ratio × scale_factor
  (P01 연구 방법론과 동일 개념)
- **OVERLAP_DAYS=14**: 매 수집마다 "DB 마지막 저장 날짜-14일 ~ 어제"를 다시 가져옴
  (하루치만 가져오면 겹치는 날짜가 없어 inter_scale이 항상 1.0으로 죽는 버그가 있었음,
  2026-07-28 수정 — `04_Collection_Pipeline_Operations.md` §6.2 참조)
- **최초 수집 소급**: `dcat_dataset.temporal_start`를 등록 시 지정하면 그 날짜부터
  한 번에 소급 수집(레거시의 "1년치 2단계 백필"과 달리 단일 범위 호출로 단순화 —
  API 응답 안에서는 M값이 통일되니 더 일관됨), 첫 수집 성공 후 실제 관측된 최솟값으로
  자동 갱신
- API 호출 간 `time.sleep(1초)` rate limiting

## 수집 대상 카테고리 (실 DB 기준, 2026-07-28)

| category_id | category_name | anchor |
|---|---|---|
| `50000148` | 패션의류 | ✅ |
| `50001828` | 패션의류>남성의류 | |
| `50001421` | 패션의류>여성의류 | |
| `50000204` | 패션잡화 | |
| `50000167` | 스포츠/레저 | |

## 등록 방법

```bash
python scripts/register_dataset.py shopping_insight \
    --title "..." --description "..." \
    --categories "50000148:패션의류,50001828:패션의류>남성의류" \
    --temporal-start 2025-01-01   # 선택 — 최초 수집 소급 시작일
```

## 관련 파일

- 콜렉터: `src/collectors/naver_shopping_collector.py`(API 호출+배칭),
  `src/collectors/naver_datalab_scale.py`(intra/inter_scale 계산, persona와 공유)
- 파이프라인: `src/pipelines/naver_shopping_pipeline.py`
- DB: `src/database/meta_shopping_insight.py`
- DDL: `sql/meta_shopping_insight.sql`, `sql/active_meta_shopping_insight.sql`
- 레거시 원본(포팅 참고용): `3amd/naver_shopping_insight.py`
