# Naver Blog

> **Last Updated:** 2026-07-28
> **dataset_id:** `naver_blog_{주제}` (주제별로 별도 dataset_id)
> **source_type:** `blog`
> **상태:** Collector 구현·검증 완료(§6.1), SeaweedFS raw/JSON-LD 저장까지 통합 완료
>
> 이전까지 이 소스는 전용 문서가 없었다(Collector·파이프라인은 완성돼 있었는데
> 문서만 누락) — 2026-07-28 신규 작성.

---

## 개요

네이버 검색 API(블로그)를 통해 키워드 기반 게시물을 수집한다. 뉴스 콜렉터와 거의
동일한 원리(검색 API 페이지네이션, 삭제 감지 원칙)를 쓰고, 처음부터 뉴스에서 발견한
버그(아래 참조)를 피해서 만들어졌다.
현재 수집 대상: AI 관련 블로그 (`naver_blog_ai`, 실 DB 기준 게시물 1,283건 — 네이버
블로그 1,279건, 티스토리 4건)

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://openapi.naver.com/v1/search/blog.json` |
| 인증 | Client ID / Client Secret |
| 1회 최대 결과 | 100건, 페이지네이션 지원 |
| 반응 수(공감 등) | `blog.like.naver.com` 비공식 API로 `platform='naver'` 게시물만 수집 가능(ADR-006) — Referer 헤더만 있으면 세션/쿠키 불필요 |
| 댓글 수 / 조회수 | **수집 불가** — 댓글 수는 API가 정책적으로 차단, 조회수는 페이지에 노출 안 됨(ADR-006) |

## 플랫폼 다양성

네이버 블로그 검색 API는 이름과 달리 `blog.naver.com` 외에도 티스토리·브런치·
워드프레스·Blogger 등을 검색 결과에 함께 반환한다. 그래서 `meta_naver_blog.platform`
컬럼으로 호스팅 플랫폼을 구분한다(`naver`/`tistory`/`brunch`/`wordpress`/`blogger`/
`other`). 반응 수 수집·`blog_id`/`log_no` 파싱은 `platform='naver'`일 때만 해당.
실측(350건 샘플, ADR-006 조사 중): `blog.naver.com` 96%, `tistory.com` 3.4%,
커스텀 도메인 소수.

## 수집 로직 — 삭제 감지 원칙은 뉴스와 동일

블로그 검색도 `sort=date` 슬라이딩 윈도우라 "검색 결과 부재"만으로 삭제 판정하면
안 된다 — 뉴스 콜렉터 개발 중 발견한 버그(§`naver_news.md` 참조)를 블로그는 **처음부터**
피해서 만들었다: `check_post_still_exists()`로 URL을 직접 재확인(HEAD)해서 404/410
확정 시에만 삭제 처리(`04_Collection_Pipeline_Operations.md` §6.1). 같은 검색어에
여러 게시물이 매칭되는 중복 처리 방지, 본문 스크래핑 실패(`has_content=FALSE`) 시
title+description만 저장.

## SeaweedFS 저장

게시물 본문(`has_content=TRUE`인 것만)이 `raw/blog/{dataset_id}/{meta_id}.txt`에,
데이터셋 전체(게시물+반응수 시계열)가 `jsonld/blog/{dataset_id}/{dataset_id}.jsonld`
1개에 저장된다. 상세: [architecture/05_Object_Storage_Export.md](../architecture/05_Object_Storage_Export.md)

## 등록 방법

```bash
python scripts/register_dataset.py blog \
    --title "..." --description "..." --subjects "인공지능,반도체,HBM"
```

## 관련 파일

- 콜렉터: `src/collectors/naver_blog_collector.py`(플랫폼 판정, 본문 스크래핑, 반응수 API)
- 파이프라인: `src/pipelines/naver_blog_pipeline.py`
- DB: `src/database/meta_naver_blog.py`
- DDL: `sql/meta_naver_blog.sql`, `sql/active_meta_naver_blog.sql`
- 관련 ADR: [ADR-006](../adr/006_Naver_Blog_Metrics_Decision.md)(수집 가능 지표 결정)
