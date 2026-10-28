# Naver News

> **Last Updated:** 2026-07-28
> **dataset_id:** `naver_news_{주제}` (주제별로 별도 dataset_id)
> **source_type:** `news`
> **상태:** Collector 구현·검증 완료(§6.1), SeaweedFS raw/JSON-LD 저장까지 통합 완료

---

## 개요

네이버 검색 API(뉴스)를 통해 키워드 기반 뉴스 기사를 수집한다.
현재 수집 대상: AI 관련 뉴스 (`urn:naver:news_ai`, 실 DB 기준 기사 1,815건)

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://openapi.naver.com/v1/search/news.json` |
| 인증 | Client ID / Client Secret |
| 일 호출 한도 | 25,000회 (초과 시 HTTP 429) |
| 1회 최대 결과 | 100건, 최대 3페이지(300건)까지 페이지네이션 |
| 댓글 수 | 비공식 `cbox5` API로 `is_naver_hosted=TRUE` 기사만 수집 가능(ADR-005) |

## 수집 대상

| dataset_id | 키워드 |
|------------|--------|
| `urn:naver:news_ai` | 인공지능, AI, 반도체, HBM 등 |

## 수집 로직 — 삭제 감지가 다른 소스와 다름

뉴스 검색 API는 `sort=date` **슬라이딩 윈도우**라 "검색 결과에 없음"이 삭제를 뜻하지
않는다(몇 분 만에도 상위 N건 밖으로 밀려날 수 있음). 실측: 두 번 연속 실행 사이에
기존 기사 146건이 "검색 결과 부재"로 나왔는데 91건(62%)이 실제로는 살아있는 200
응답이었음. 그래서 검색 결과 부재는 "삭제 후보"로만 쓰고, `check_article_still_
exists()`로 URL을 직접 재확인(HEAD)해서 404/410 확정 시에만 삭제 처리한다
(`04_Collection_Pipeline_Operations.md` §6.1). 같은 검색어에 여러 기사가 매칭되는
중복 처리 방지, 본문 스크래핑 실패(`has_content=FALSE`) 시 title+description만 저장.

## SeaweedFS 저장

기사 본문(`has_content=TRUE`인 것만)이 `raw/news/{dataset_id}/{meta_id}.txt`에,
데이터셋 전체(기사+댓글수 시계열)가 `jsonld/news/{dataset_id}/{dataset_id}.jsonld`
1개에 저장된다. 상세: [architecture/05_Object_Storage_Export.md](../architecture/05_Object_Storage_Export.md)

## 등록 방법

```bash
python scripts/register_dataset.py news \
    --title "..." --description "..." --subjects "인공지능,반도체,HBM"
```

## 관련 파일

- 콜렉터: `src/collectors/naver_news_collector.py`
- 파이프라인: `src/pipelines/naver_news_pipeline.py`
- DB: `src/database/meta_news.py`
- DDL: `sql/meta_news.sql`, `sql/active_meta_news.sql`
- 관련 ADR: [ADR-005](../adr/005_Naver_News_Metrics_Decision.md)(수집 가능 지표 결정)
