# Naver News

> **Last Updated:** 2026-07-01
> **dataset_id:** `naver_news_{주제}` (주제별로 별도 dataset_id)
> **source_type:** `news`

---

## 개요

네이버 검색 API(뉴스)를 통해 키워드 기반 뉴스 기사를 수집한다.
현재 수집 대상: AI 관련 뉴스 (`naver_news_ai`)

---

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://openapi.naver.com/v1/search/news.json` |
| 인증 | Client ID / Client Secret |
| 일 호출 한도 | 25,000회 (초과 시 HTTP 429) |
| 1회 최대 결과 | 100건 |

---

## 수집 대상

| dataset_id | 키워드 |
|------------|--------|
| `naver_news_ai` | 인공지능, AI, 머신러닝, 딥러닝 |

---

## 주의 사항

- 뉴스 본문 스크래핑은 각 언론사 저작권 정책 별도 확인 필요
- API 429 오류 발생 이력 있음 (`dcat_provenance` 기록 확인)
- 일 호출 한도 도달 시 다음날 자동 재시도 (CronJob)

---

## 관련 파일

- 수집 코드: `src/collectors/naver_news.py` (예정)
