"""스펙(YAML)으로 동작하는 범용 REST/JSON 수집 어댑터 (A1).

엔드포인트·인증·페이징·필드 매핑을 **코드가 아니라 스펙**에서 읽는다.
신규 원천이 늘 때 파이썬 파일을 새로 쓰지 않고 YAML 한 장을 추가한다.

    from src.collectors.adapters.rest_json import RestJsonCollector
    c = RestJsonCollector.from_file("configs/sources/naver_news.yaml")
    for raw in c.fetch():
        print(c.normalize(raw))

---

## ⚠️ 인증값은 스펙에 쓰지 않는다

스펙에는 **환경변수 이름만** 적는다. 값이 들어가면 YAML이 저장소에 커밋되는
순간 자격증명이 평문으로 남는다(NEXT_STEPS §8.6 "자격증명은 환경변수·K8s
Secret만, 코드·문서 평문 금지").

    auth:
      headers:
        X-Naver-Client-Id: {env: NAVER_CLIENT_ID}   # 이름만. 값은 런타임에 읽는다

환경변수가 비어 있으면 **요청을 보내지 않고 바로 실패시킨다.** 빈 헤더로
요청하면 원천이 401을 주는데, 그게 "키가 없다"인지 "키가 틀렸다"인지 구분이 안 된다.

## 페이징

원천마다 방식이 다르다. 스펙의 `paging.mode`로 고른다.

| mode | 동작 | 예 |
|---|---|---|
| `offset` | 시작 위치를 더해 간다 | 네이버 검색 `start=1,101,201…` |
| `page` | 페이지 번호를 올린다 | `page=1,2,3…` |
| `cursor` | 응답의 토큰을 다음 요청에 넣는다 | YouTube `pageToken` |
| `none` | 한 번만 부른다 | 단건 조회 |

**멈추는 조건을 전부 건다** — 빈 결과, 요청한 것보다 적게 온 마지막 쪽,
`max_pages`, 원천이 정한 상한(`max_offset`). 하나라도 빠지면 무한 루프가 된다.

## POST 원천과 중첩 배열 (2026-11-11, 기존 수집기 이관용)

    method: post          # 기본 get
    body: {timeUnit: date, category: [...]}   # POST 본문(JSON). 질의(query)는 본문에 합친다
    explode: data         # 항목 안의 배열을 펼쳐 원소마다 한 항목으로(부모 필드는 `_parent.`로 접근)

네이버 데이터랩처럼 `results[].data[]` 모양이면 `items_path: results` + `explode: data`로
(카테고리 × 기간) 한 줄씩 흘려보낸다.
"""

import html
import logging
import re
import time
from typing import Any, Dict, Iterator, List, Optional

import requests
import yaml

from src.collectors.base import BaseCollector, CollectorError, RemovalPolicy
from src.common import config
from src.common.retry import RetryableError, with_retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 10


#: 검색 API는 질의어를 강조해 돌려주는 경우가 많다 — 네이버는 `<b>HBM</b>`,
#: 엔티티도 섞어 보낸다(`&quot;`). 그대로 저장하면 제목에 태그가 박히고,
#: 토큰화·임베딩·요약까지 오염된다. 2026-11-04에 실제로 28건이 그렇게 들어갔다.
_TAG = re.compile(r"<[^>]+>")


def clean_text(value: Any) -> Any:
    """문자열이면 태그를 벗기고 HTML 엔티티를 푼다. 아니면 그대로."""
    if not isinstance(value, str):
        return value
    return html.unescape(_TAG.sub("", value)).strip()


def dig(obj: Any, path: str) -> Any:
    """`a.b.c` 또는 `a.0.b`로 중첩 구조에서 값을 꺼낸다. 없으면 None.

    JSONPath를 쓰지 않는 이유 — 의존성이 하나 늘고, 스펙에서 필요한 것은
    "중첩 키 따라가기"뿐이라 기능 대부분이 쓰이지 않는다.
    """
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            if not part.isdigit() or int(part) >= len(cur):
                return None
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _resolve(value: Any, what: str) -> str:
    """`{env: NAME}`이면 환경변수에서 읽고, 문자열이면 그대로 쓴다."""
    if isinstance(value, dict) and "env" in value:
        name = value["env"]
        # os.getenv를 직접 쓰지 않는다 — config가 .env를 로드하는 지점이라
        # 건너뛰면 CLI에서는 되고 스크립트에서는 안 되는 차이가 생긴다
        got = config.get_env(name)
        if not got:
            # 빈 값으로 요청을 보내면 원천이 401을 주는데, 그게 "키 없음"인지
            # "키 틀림"인지 구분이 안 된다. 여기서 끊는 편이 진단이 빠르다.
            raise CollectorError(
                f"{what}: 환경변수 {name}가 비어 있다. .env 또는 K8s Secret을 확인하라."
            )
        return got
    return str(value)


class RestJsonCollector(BaseCollector):
    """스펙으로 동작하는 REST/JSON 수집기."""

    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.source = spec.get("source") or ""
        if not self.source:
            raise CollectorError("스펙에 source가 없다")
        self.endpoint = spec.get("endpoint")
        if not self.endpoint:
            raise CollectorError(f"{self.source}: 스펙에 endpoint가 없다")

        self.removal_policy = RemovalPolicy(
            spec.get("removal_policy", RemovalPolicy.UNSUPPORTED.value))
        self._fields: Dict[str, str] = spec.get("fields") or {}
        self._id_field: Optional[str] = spec.get("id_field")
        self._items_path: str = spec.get("items_path", "items")
        self._rate_limit: float = float(spec.get("rate_limit_sec", 0.2))
        # 기본으로 켠다. 검색 API의 강조 태그는 예외가 아니라 기본값에 가깝고,
        # 꺼야 하는 쪽(마크업이 의미를 갖는 원천)이 스펙에 명시하는 편이 안전하다
        self._clean_text: bool = bool(spec.get("clean_text", True))
        self._method: str = str(spec.get("method", "get")).lower()
        if self._method not in ("get", "post"):
            raise CollectorError(f"{self.source}: method는 get|post")
        self._explode: Optional[str] = spec.get("explode")

    # ── 생성 ────────────────────────────────────────────────────────
    @classmethod
    def from_file(cls, path: str) -> "RestJsonCollector":
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    # ── 요청 ────────────────────────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        auth = self.spec.get("auth") or {}
        return {k: _resolve(v, f"{self.source}.auth.headers.{k}")
                for k, v in (auth.get("headers") or {}).items()}

    def _base_params(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        auth = self.spec.get("auth") or {}
        params: Dict[str, Any] = {
            k: _resolve(v, f"{self.source}.auth.params.{k}")
            for k, v in (auth.get("params") or {}).items()
        }
        for k, v in (self.spec.get("params") or {}).items():
            params[k] = _resolve(v, f"{self.source}.params.{k}") if isinstance(v, dict) else v
        if overrides:
            params.update(overrides)
        return params

    def _get(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        def _execute():
            if self._method == "post":
                # POST: 스펙 body + 질의(params)를 JSON 본문으로. 인증 params는 주소에 둔다
                auth_params = {k: _resolve(v, f"{self.source}.auth.params.{k}")
                               for k, v in ((self.spec.get("auth") or {}).get("params") or {}).items()}
                body = {**(self.spec.get("body") or {}),
                        **{k: v for k, v in params.items() if k not in auth_params}}
                resp = requests.post(self.endpoint, headers=self._headers(), params=auth_params or None,
                                     json=body, timeout=DEFAULT_TIMEOUT)
            else:
                resp = requests.get(self.endpoint, headers=self._headers(),
                                    params=params, timeout=DEFAULT_TIMEOUT)
            if resp.status_code >= 500:
                # 5xx는 원천 쪽 일시 장애다 — 재시도 대상
                raise RetryableError(f"HTTP {resp.status_code}")
            if resp.status_code != 200:
                logger.warning("%s: HTTP %s — %s", self.source, resp.status_code,
                               resp.text[:200])
                return None
            return resp.json()

        return with_retry(_execute)

    # ── 페이징 ──────────────────────────────────────────────────────
    def fetch(self, cursor: Optional[Any] = None,
              query: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """스펙의 페이징 방식대로 항목을 흘려보낸다."""
        paging = self.spec.get("paging") or {}
        mode = paging.get("mode", "none")
        size = int(paging.get("size", DEFAULT_PAGE_SIZE))
        max_pages = int(paging.get("max_pages", DEFAULT_MAX_PAGES))
        size_param = paging.get("size_param")
        page_param = paging.get("page_param")
        start_at = int(paging.get("start_at", 1))
        max_offset = paging.get("max_offset")
        token_path = paging.get("token_path")
        token_param = paging.get("token_param")

        token = cursor if mode == "cursor" else None
        seen = 0

        for page in range(max_pages):
            extra: Dict[str, Any] = dict(query or {})
            if size_param:
                extra[size_param] = size

            if mode == "offset":
                offset = start_at + page * size
                if max_offset is not None and offset > int(max_offset):
                    break                       # 원천이 정한 상한
                extra[page_param] = offset
            elif mode == "page":
                extra[page_param] = start_at + page
            elif mode == "cursor":
                if page and not token:
                    break                       # 다음 토큰이 없으면 끝
                if token:
                    extra[token_param] = token

            data = self._get(self._base_params(extra))
            if not data:
                break
            items = dig(data, self._items_path) or []
            if not items:
                break
            for raw in items:
                for out in self._explode_item(raw):
                    seen += 1
                    yield out

            if len(items) < size:
                break                           # 마지막 쪽
            if mode == "cursor":
                token = dig(data, token_path) if token_path else None
                if not token:
                    break
            elif mode == "none":
                break
            time.sleep(self._rate_limit)

        logger.info("%s: %d건 수집", self.source, seen)

    def _explode_item(self, raw: Any) -> Iterator[Dict[str, Any]]:
        """`explode`가 있으면 항목 안의 배열을 원소마다 펼친다. 부모 필드는 `_parent`에 둔다."""
        if not self._explode or not isinstance(raw, dict):
            yield raw
            return
        children = raw.get(self._explode) or []
        parent = {k: v for k, v in raw.items() if k != self._explode}
        for child in children:
            if isinstance(child, dict):
                yield {**child, "_parent": parent}

    # ── 정규화 ──────────────────────────────────────────────────────
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """스펙의 `fields` 매핑대로 평평한 dict를 만든다.

        매핑이 비어 있으면 raw를 그대로 돌려준다 — 원천 구조를 아직 모를 때
        한 번 돌려보고 `fields`를 채우는 흐름을 위해서다.
        """
        if not self._fields:
            return dict(raw)
        out = {target: dig(raw, src) for target, src in self._fields.items()}
        if self._clean_text:
            out = {k: clean_text(v) for k, v in out.items()}
        if self._id_field and out.get("id") is None:
            out["id"] = dig(raw, self._id_field)
        return out

    def item_id(self, normalized: Dict[str, Any]) -> str:
        value = normalized.get("id")
        if value is None:
            raise CollectorError(
                f"{self.source}: 식별자가 비었다. 스펙의 id_field 또는 "
                f"fields.id를 확인하라."
            )
        return str(value)
