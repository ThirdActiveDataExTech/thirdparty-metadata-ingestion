"""외부 CKAN 포털 메타데이터 수집 — 연합 검색 (C6 최소선).

연구개발계획서 3차년도 "탐색 확장·통합 구성". 외부 포털의 데이터셋을
**우리 카탈로그와 같은 모양**으로 들여와 한 번의 검색으로 함께 나오게 한다.

## 원본은 가져오지 않는다 — 메타데이터만

데이터 파일을 복제하지 않는다. `landing_page`로 원천을 가리킬 뿐이다.
복제하면 라이선스·최신성·용량이 전부 우리 문제가 되고, 연합 검색의 목적은
"어디에 무엇이 있는지 아는 것"이지 "다 가져오는 것"이 아니다.

## 우리가 수집한 것과 섞이지 않게 표시한다

    dataset_origin = 'external'    수집 파이프라인이 건드리지 않는다
    source         = 'CKAN:<포털>'  어느 포털에서 왔는지
    external_ids   = ['<포털>:<id>'] 원천 식별자 (와이즈넛 합의 형식)

**`data_registry`에 넣지 않는다.** 그 테이블은 "다음에 언제 수집할 것인가"를
담는데, 외부 데이터셋은 우리가 수집하지 않는다. 넣으면 스케줄러가 수집하려
들고 실패를 쌓는다.
"""

import logging
import re
import time
from typing import Any, Dict, Iterator, List, Optional

import requests

from src.common.retry import RetryableError, with_retry

logger = logging.getLogger(__name__)

TIMEOUT = 20
PAGE_SIZE = 50

#: 쪽 사이 대기. 공개 포털은 속도 제한을 걸고, 넘기면 429를 돌려준다.
#: 남의 서버를 쓰는 쪽이 맞춰야 한다.
RATE_LIMIT_SEC = 1.5

#: dataset_id로 쓸 URN. 우리 것과 구분되고, 같은 포털의 같은 id면 항상 같다.
#: (형식은 ADR-017 비정형 식별자 규약을 따른다)
URN_PREFIX = "urn:ckan"

_SLUG = re.compile(r"[^a-z0-9]+")


def _portal_slug(portal: str) -> str:
    """포털 호스트를 식별자 조각으로. `open.canada.ca` → `open-canada-ca`."""
    host = re.sub(r"^https?://", "", portal).split("/")[0]
    return _SLUG.sub("-", host.lower()).strip("-")


def search(portal: str, query: str = "*:*", rows: int = PAGE_SIZE,
           max_records: int = 100) -> Iterator[Dict[str, Any]]:
    """CKAN `package_search`로 데이터셋 메타를 흘려보낸다.

    **상한을 둔다.** 포털에는 수만 건이 있고, 전부 들여오면 우리 카탈로그가
    남의 것으로 덮인다. 연합 검색의 최소선은 "경로가 열려 있다"는 증명이다.
    """
    base = portal.rstrip("/")
    fetched = 0
    while fetched < max_records:
        take = min(rows, max_records - fetched)

        def _execute():
            r = requests.get(f"{base}/api/3/action/package_search",
                             params={"q": query, "rows": take, "start": fetched},
                             timeout=TIMEOUT)
            # 429는 "지금은 말고 나중에"다. 하드 실패로 처리하면 가져올 수 있는
            # 데이터를 버린다 — 5xx와 같이 재시도 대상으로 둔다
            if r.status_code == 429 or r.status_code >= 500:
                raise RetryableError(f"HTTP {r.status_code}")
            if r.status_code != 200:
                logger.warning("CKAN %s: HTTP %s", base, r.status_code)
                return None
            return r.json()

        # 공개 포털의 429는 몇 초 단위로 풀린다. 기본 3회·1초로는 짧다
        data = with_retry(_execute, max_attempts=5, base_delay=3.0)
        if not data or not data.get("success"):
            break
        results = (data.get("result") or {}).get("results") or []
        if not results:
            break
        for pkg in results:
            yield pkg
        fetched += len(results)
        if len(results) < take:
            break
        time.sleep(RATE_LIMIT_SEC)
    logger.info("CKAN %s: %d건 조회", base, fetched)


#: 포털이 언어를 주지 않을 때 쓸 값.
#:
#: ⚠️ `dcat_dataset.language`는 NOT NULL에 **기본값이 `'ko'`**이고 `spatial`은
#: `'KR'`이다. 우리가 수집하는 국내 데이터를 위한 값이라, 그냥 두면 캐나다
#: 데이터셋이 **한국어·한국 소재로 기록된다.** 외부 포털에서는 반드시 덮어쓴다.
DEFAULT_LANGUAGE = "en"


def to_dcat(pkg: Dict[str, Any], portal: str,
            default_language: str = DEFAULT_LANGUAGE) -> Optional[Dict[str, Any]]:
    """CKAN 패키지를 우리 `dcat_dataset` 모양으로 바꾼다.

    제목이 없으면 버린다 — 카탈로그에 이름 없는 행이 쌓이면 검색 결과가 망가진다.
    """
    pkg_id = pkg.get("id") or pkg.get("name")
    title = (pkg.get("title") or "").strip()
    if not pkg_id or not title:
        return None

    slug = _portal_slug(portal)
    tags = [t.get("display_name") or t.get("name") for t in (pkg.get("tags") or [])]
    keywords = [k for k in tags if k][:20]
    org = (pkg.get("organization") or {}).get("title") or pkg.get("author")

    # CKAN의 notes는 마크다운이 섞여 있다. 그대로 두면 검색 텍스트에 기호가 낀다
    notes = re.sub(r"[#*_`>\[\]()]", " ", pkg.get("notes") or "")
    notes = re.sub(r"\s+", " ", notes).strip()

    return {
        "dataset_id": f"{URN_PREFIX}:{slug}:{pkg_id}",
        "title": title[:500],
        "description": notes[:2000] or None,
        "publisher": (org or slug)[:200],
        "source_type": "external_catalog",
        "source": f"CKAN:{slug}",
        "dataset_origin": "external",
        "keywords": keywords,
        "license": pkg.get("license_title") or pkg.get("license_id"),
        "landing_page": f"{portal.rstrip('/')}/dataset/{pkg.get('name') or pkg_id}",
        "external_ids": [f"{slug}:{pkg_id}"],
        "accrual_periodicity": pkg.get("frequency") or pkg.get("issuance_frequency"),
        "language": _language(pkg) or default_language,
        # 소재를 추측하지 않는다. 모르면 NULL이 맞다 — 기본값 'KR'이 붙으면
        # 캐나다 데이터가 한국 소재로 기록된다
        "spatial": None,
    }


def _language(pkg: Dict[str, Any]) -> Optional[str]:
    """CKAN의 language는 문자열일 수도 목록일 수도 있다."""
    v = pkg.get("language")
    if isinstance(v, list):
        return next((x for x in v if x), None)
    return v or None


def harvest(portal: str, query: str = "*:*", max_records: int = 100) -> List[Dict[str, Any]]:
    """포털에서 가져와 DCAT 모양으로 바꾼 목록. DB는 건드리지 않는다."""
    out = []
    for pkg in search(portal, query, max_records=max_records):
        row = to_dcat(pkg, portal)
        if row:
            out.append(row)
    logger.info("DCAT 변환 %d건", len(out))
    return out


def store(rows: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, int]:
    """DCAT 행을 `dcat_dataset`에 upsert한다.

    ⚠️ **`data_registry`에는 넣지 않는다.** 그 테이블은 수집 스케줄을 담는데
    외부 데이터셋은 우리가 수집하지 않는다. 넣으면 스케줄러가 수집하려 들고
    실패만 쌓인다(§머리말).

    같은 포털의 같은 id는 같은 `dataset_id`가 되므로 다시 들여오면 갱신된다.
    """
    import json

    from psycopg2.extras import execute_values

    from src.database.db import get_conn

    if not rows:
        return {"fetched": 0, "stored": 0}
    if dry_run:
        logger.info("dry-run — %d건을 쓰지 않는다", len(rows))
        return {"fetched": len(rows), "stored": 0}

    conn = get_conn()
    cur = conn.cursor()
    payload = [
        (r["dataset_id"], r["title"], r["description"], r["publisher"],
         r["source_type"], r["source"], r["dataset_origin"],
         json.dumps(r["keywords"], ensure_ascii=False),
         r["license"], r["landing_page"],
         json.dumps(r["external_ids"], ensure_ascii=False),
         r["accrual_periodicity"], r["language"], r["spatial"], "ORG")
        for r in rows
    ]
    execute_values(
        cur,
        "INSERT INTO dcat_dataset (dataset_id, title, description, publisher, "
        "  source_type, source, dataset_origin, keywords, license, landing_page, "
        "  external_ids, accrual_periodicity, language, spatial, visibility) VALUES %s "
        "ON CONFLICT (dataset_id) DO UPDATE SET "
        "  title = EXCLUDED.title, description = EXCLUDED.description, "
        "  publisher = EXCLUDED.publisher, keywords = EXCLUDED.keywords, "
        "  license = EXCLUDED.license, landing_page = EXCLUDED.landing_page, "
        "  updated_at = now()",
        payload, page_size=200, fetch=False)
    conn.commit()
    logger.info("dcat_dataset에 %d건 적재(origin=external)", len(rows))
    return {"fetched": len(rows), "stored": len(rows)}
