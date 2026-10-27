# ADR-006: Naver 블로그 수집 가능 지표 결정

> **Date:** 2026-07-24
> **Status:** Accepted
> **결론:** `active_meta_blog`에 **반응(공감 등) 수만** 수집. 댓글 수·조회수는 미수집.

---

## 배경

`active_meta_blog`는 ADR-005(뉴스 수집 가능 지표 결정)와 동일한 수준의 실제 API
검증을 거치지 않은 잠정 설계였다(`sql/active_meta_blog.sql` 헤더 주석 참조). 아래
3개 후보 지표를 실제 API 호출로 검증했다.

테스트 대상: 실제 Naver 블로그 검색 API(`openapi.naver.com/v1/search/blog.json`)로 가져온
공개 게시물 다수 (blog.naver.com 호스팅).

---

## 조사 결과

### 1. 조회수 — 수집 불가

게시물 페이지(`PostView.naver`) HTML 전체를 검사했으나 조회수 관련 필드
(`readCount`/`viewCount`/`hit_count`/"조회수" 텍스트 등)가 어디에도 노출되지 않는다.
블로그 주인만 볼 수 있는 비공개 통계로 추정된다. 뉴스가 2020년 이후 조회수를 완전히
비공개 처리한 것과 유사하게, 블로그도 애초에 공개 노출 대상이 아닌 것으로 보인다.

### 2. 댓글 수 — 수집 불가 (현 단계)

뉴스가 사용하는 `apis.naver.com/commentBox/cbox5` 계열 API로 여러 `ticket`/`objectId`
조합을 시도했다.

- `cbox5` 엔드포인트: `ticket=blog` 등 여러 값 시도 → `Wrong ticket` 또는 403
- 실제 페이지가 쓰는 `cbox9`: 같은 경로(`web_naver_list_jsonp.json`)가 "존재하지 않는
  API"라는 응답 반환 (cbox5와 경로 구조가 다름)
- 경로를 추정해 재시도 → `"서비스 정책에 의해 사용이 제한되었습니다"` (code 3300) —
  단순 파라미터 오류가 아니라 정책적으로 차단된 응답

댓글 수 표시 영역(`floating_bottom_commentCount`)도 뉴스의 "추천 반응"과 마찬가지로
정적 HTML엔 빈 값이고 JS 실행 후 채워지는 구조로 확인됐다. 세션/쿠키 기반 인증이나
실제 브라우저 자동화(Selenium/Playwright) 없이는 현재 방식으로 수집이 어렵다고 판단.

### 3. 공감 등 반응 수 — 수집 가능 (뉴스와 다른 결론)

뉴스의 "추천 반응"은 ADR-005에서 브라우저 자동화가 필요하다고 결론났지만, 블로그는
**다른 백엔드 서비스를 쓰고 있어 순수 HTTP 요청만으로 수집 가능**함을 확인했다.

```python
import requests

headers = {
    "User-Agent": "Mozilla/5.0 ...",
    "Referer": f"https://blog.naver.com/{blog_id}/{log_no}",
}
q = f"BLOG[{blog_id}_{log_no}]"
resp = requests.get(
    "https://blog.like.naver.com/v1/search/contents",
    headers=headers, params={"q": q},
)
# resp.json()["contents"][0]["reactions"]
# 예: [{"reactionType": "like", "count": 32}, {"reactionType": "impressive", "count": 1}]
```

- `q` 파라미터의 `contentsId`는 게시물 페이지의 `data-likeContentsId` 속성값과 동일
  (`{blogId}_{logNo}`, "blog" 접두사 없음)
- 실제 게시물 10건 중 9건에서 `like`(공감) 5~32건, 1건은 `impressive`(칭찬해요) 1건도
  함께 반환 — API가 정상 작동하며 세션/쿠키 불필요, `Referer` 헤더만 있으면 충분
- 반응 타입은 6종(`thanks`/`haha`/`like`/`sad`/`impressive`/`wow`) — Facebook류 리액션
  구조. 게시물마다 등장하는 타입이 다름(대부분 `like`만, 드물게 다른 타입도 함께)

---

## 결정

| 지표 | 결정 | 이유 |
|------|------|------|
| 조회수 | ❌ 미수집 | 공개 페이지 어디에도 노출 안 됨 (owner-only 추정) |
| 댓글 수 | ❌ 미수집 (보류) | 브라우저 자동화 또는 세션 인증 필요, 현 단계 오버스펙 |
| 반응 수 (공감 등) | ✅ 수집 | `blog.like.naver.com`으로 순수 HTTP 수집 가능, 타입별 세부 포함 |

`active_meta_blog`는 `meta_blog.platform='naver'`인 게시물만 대상으로 하며
(뉴스의 `is_naver_hosted`와 동일 제약), 반응 수만 수집하도록 스키마를 확정한다
(`sql/active_meta_blog.sql` 갱신).

---

## 향후 검토

댓글 수 수집이 필요하다고 판단될 경우, 실제 브라우저 요청을 캡처해 정확한 cbox9
엔드포인트 경로와 인증 방식(세션 쿠키 등)을 확인하거나 Playwright 기반 수집 코드를
별도로 개발한다. 이 경우 `active_meta_blog`에 `comment_count`/`expose_count`/
`reply_count` 컬럼을 추가하는 방향으로 확장한다 (ADR-005가 뉴스 추천 반응에 대해 취한
것과 동일한 접근).
