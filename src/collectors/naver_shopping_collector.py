"""Naver DataLab Shopping Insight API — 순수 API 호출만, DB 접근 없음.

레거시(3amd/naver_shopping_insight.py)의 fetch_insight/parse_response를 그대로
포팅했다. anchor 카테고리를 매 호출에 포함시켜 호출당 최대 3카테고리 제약을
맞추는 배칭은 pipelines 레이어(호출하는 쪽)에서 담당한다 — 이 모듈은 "1회
API 호출"의 요청/응답만 다룬다.
"""

from typing import Dict, List, Optional, Tuple

import requests

from src.common.retry import RetryableError, with_retry

API_URL = "https://openapi.naver.com/v1/datalab/shopping/categories"


def fetch_insight(
    client_id: str,
    client_secret: str,
    start_date: str,
    end_date: str,
    time_unit: str,
    categories: List[Tuple[str, str]],
    gender: str,
    age: str,
) -> Optional[dict]:
    """categories: [(category_id, category_name), ...] — anchor 포함해서 최대 3개."""
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "category": [{"name": name, "param": [cid]} for cid, name in categories],
        "gender": gender,
        "ages": [str(age)],
    }

    def _execute():
        resp = requests.post(API_URL, headers=headers, json=body, timeout=30)
        if resp.status_code >= 500:
            raise RetryableError(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            return None  # 4xx는 재시도 무의미 — 이 배치만 스킵
        return resp.json()

    return with_retry(_execute)


def parse_response(data: dict) -> Dict[str, Dict[str, float]]:
    """API 응답 → {category_name: {period: ratio}}."""
    result: Dict[str, Dict[str, float]] = {}
    for r in data.get("results", []):
        title = r.get("title", "")
        result[title] = {p["period"]: p["ratio"] for p in r.get("data", [])}
    return result
