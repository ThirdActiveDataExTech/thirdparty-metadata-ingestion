# ADR-005: Naver 뉴스 수집 가능 지표 결정

> **Date:** 2026-07-06
> **Status:** Accepted
> **결론:** `active_meta_naver_news` 에 **댓글 수(comment_count, expose_count, reply_count)만** 수집

---

## 배경

`active_meta_naver_news` 설계 시 YouTube의 조회수·좋아요처럼 시계열로 추적할 수 있는
뉴스 기사 지표가 무엇인지 조사했다.

---

## 조사 결과

### 1. 조회수 — 수집 불가

네이버가 2020년 이후 뉴스 기사의 조회수를 공개 페이지 및 API 모두에서 제거했다.
현재 어떤 방법으로도 조회수 데이터를 얻을 수 없다.

### 2. "이 기사를 추천합니다" 반응 — 수집 불가 (현 단계)

5가지 반응 타입(쏠쏠정보, 흥미진진, 공감백배, 분석탁월, 후속강추)이 네이버 뉴스 기사에 존재하며
실제로 사용자들이 반응을 남긴다는 것을 확인했다 (스크린샷 기준: 공감백배 11, 후속강추 11 등).

그러나 이 데이터는 기술적으로 수집이 어렵다:

- **정적 HTML**: 초기 렌더링에는 항상 0으로 표시됨
- **JS 동적 로딩**: 페이지 로드 후 `reaction.min.js`가 실행되며 `news.like.naver.com` API를 호출해 실제 값으로 교체
- **직접 API 호출**: `news.like.naver.com/v1/search/contents` 를 직접 호출하면 항상 빈 배열 반환 (브라우저 세션 또는 쿠키 필요로 추정)
- **결론**: Selenium/Playwright 같은 실제 브라우저 자동화 없이는 수집 불가

현 단계에서 브라우저 자동화 도입은 오버스펙으로 판단해 보류.

### 3. 댓글 수 — 수집 가능 (단, 조건 있음)

비공식 API(`apis.naver.com/commentBox/cbox5`)를 통해 댓글 수 수집이 가능함을 확인했다.

```python
api = (f"https://apis.naver.com/commentBox/cbox5/web_naver_list_jsonp.json"
       f"?ticket=news&templateId=default&pool=cbox5&lang=ko"
       f"&objectId=news{oid}%2C{aid}&pageSize=1&listType=OBJECT")
```

수집 가능한 필드:
| 필드 | API 키 | 설명 |
|------|--------|------|
| `comment_count` | `result.count.comment` | 전체 댓글 수 (삭제 포함) |
| `expose_count` | `result.count.exposeCount` | 실제 노출 댓글 수 (삭제·숨김 제외) |
| `reply_count` | `result.count.reply` | 답글 수 |

**제약 조건**: `news.naver.com/article/{oid}/{aid}` 형식으로 접근 가능한
**Naver 호스팅 기사만** 수집 가능.
언론사 자체 서버에 있는 외부 기사(`is_naver_hosted=FALSE`)는 이 API를 사용할 수 없다.

---

## 결정

| 지표 | 결정 | 이유 |
|------|------|------|
| 조회수 | ❌ 미수집 | 네이버 2020년 이후 폐지 |
| 추천 반응 | ❌ 미수집 (보류) | 브라우저 자동화 필요, 현 단계 오버스펙 |
| 댓글 수 | ✅ 수집 | 비공식 API로 안정적 수집 가능 |

외부 기사(`is_naver_hosted=FALSE`)는 `active_meta_naver_news` 행을 생성하지 않으며,
뷰(`v_meta_naver_news_latest`)에서 댓글 컬럼이 NULL로 표시된다.

---

## 향후 검토

추천 반응 수집이 필요하다고 판단될 경우 Playwright 기반 수집 코드를 별도로 개발한다.
이 경우 `active_meta_naver_news`에 `reaction_useful`, `reaction_wow`, `reaction_touched`,
`reaction_analytical`, `reaction_recommend` 컬럼을 추가하는 방향으로 확장한다.
