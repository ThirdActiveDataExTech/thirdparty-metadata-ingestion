"""정기 수집 경로(`src/pipelines/*`)에 원천 스키마 드리프트 감지를 붙인다 (C4, 2026-11-11).

그 전에는 감지가 선언형 실행기(`pipeline_engine`, 수동 실행 1건)에만 있었고, 스케줄러가
돌리는 데이터셋 25건에는 없었다 → C4 완료 기준 "원천 스키마 변경 자동 감지·기록"이 실제
수집에서 미충족이었다(NEXT_STEPS C4).

흐름: 파이프라인이 수집 시작 때 `raw_sample.start()` → 수집기가 원본을 받을 때마다
`raw_sample.record()` → 레지스트리 갱신 뒤 `check()`가 표본으로 `drift.check()`를 부른다.
결과는 `data_registry.source_schema_*`에 남고(관리자 수집 현황 화면에 표시), 로그로도 남는다.

**수집을 실패시키지 않는다.** 감지는 관측이지 관문이 아니다 — 데이터는 이미 들어갔다.

`READS`는 각 수집기가 원본에서 **실제로 읽는 경로**다. 이 경로가 사라지면(breaking) 해당
컬럼이 오류 없이 NULL로 들어가는 고장이라 매번 확인한다. 수집기에서 읽는 필드를 바꾸면
여기도 같이 고친다(tests/test_pipelines_drift.py가 수집기 코드와 대조한다).
"""

import logging
from typing import Any, Dict, List, Optional

from src.collectors import raw_sample
from src.pipeline_engine import drift

logger = logging.getLogger(__name__)

#: 수집기가 원천 응답에서 읽는 경로(관측 표기 — 리스트 원소는 `[]`).
#: 선택 필드(없을 수 있는 것: YouTube likeCount·tags, 블로그 postdate 등)는 넣지 않는다 —
#: 원래 비어 올 수 있는 것을 "깨짐"으로 울리면 경보가 무뎌진다.
READS: Dict[str, List[str]] = {
    # naver_news_collector.normalize_article
    "news": ["link", "originallink", "pubDate", "title", "description"],
    # naver_blog_collector.normalize_post
    "blog": ["link", "title", "description", "bloggername", "bloggerlink"],
    # youtube_collector._normalize_video
    "video": ["id", "snippet.title", "snippet.publishedAt", "snippet.channelId",
              "snippet.channelTitle", "snippet.thumbnails", "contentDetails.duration",
              "contentDetails.definition", "contentDetails.caption"],
    # naver_shopping_collector.parse_response (응답 1건 = 표본 1건)
    "shopping_insight": ["results[].title", "results[].data[].period", "results[].data[].ratio"],
    # naver_persona_collector.parse_persona_response (응답 1건 = 표본 1건)
    "persona_insight": ["results[].data[].period", "results[].data[].group", "results[].data[].ratio"],
}


#: 원천별 최소 표본(기본은 drift.MIN_SAMPLE=5). 2026-11-11 실측으로 정했다.
#: - 데이터랩(쇼핑·페르소나)은 **응답 1건이 표본 1건**이고, 응답은 레코드별 선택 필드가 없는
#:   고정된 봉투 모양이다. 페르소나 데이터셋은 분류가 1~2개라 한 번 수집에 응답이 2~4건뿐이어서
#:   기본값이면 **영영 판정하지 않는다**
#: - 영상은 개별 지정 3건짜리 데이터셋이 있다. 매번 같은 영상이라 표본이 작아도 모양이 흔들리지 않는다
MIN_SAMPLE: Dict[str, int] = {"persona_insight": 2, "shopping_insight": 2, "video": 3}


def begin() -> None:
    """수집 시작 — 원본 표본 모으기를 켠다."""
    raw_sample.start()


def check(dataset_id: str, source_type: str) -> Optional[Dict[str, Any]]:
    """모은 표본으로 드리프트를 재고 기록한다. 어떤 실패도 밖으로 내보내지 않는다.

    호출 시점: 레지스트리 갱신(커밋) 뒤 — `drift.save()`가 커밋하므로, 커밋 전 쓰기가 남은
    자리에서 부르면 그 쓰기까지 함께 확정된다.
    """
    raws = raw_sample.stop()
    try:
        result = drift.check(dataset_id, raws, {"fields": {p: p for p in READS.get(source_type, [])}},
                             min_sample=MIN_SAMPLE.get(source_type, drift.MIN_SAMPLE))
    except Exception as e:                        # noqa: BLE001
        logger.warning("드리프트 감지 실패(수집은 유효) %s: %s", dataset_id, e)
        return None
    level = logging.WARNING if result.get("severity") not in (None, "none") else logging.INFO
    logger.log(level, "드리프트 %s: %s (표본 %d건, 심각도 %s)", dataset_id, result.get("status"),
               result.get("sample", 0), result.get("severity"))
    return result
