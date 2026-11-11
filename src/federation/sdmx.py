"""SDMX 통계 포털 메타데이터 수집 — 연합 탐색 (C6 · 3차년도).

연구계획서 3차년도: "SDMX(Statistical Data and Metadata eXchange) 통계작성기구 간의 다양한 형태의
통계자료를 탐색할 수 있는 통합 탐색 기술". CKAN(`ckan.py`)과 같은 원칙이다 —
**메타데이터만** 들여와 우리 카탈로그·검색에 합치고, 데이터는 원천의 SDMX 데이터 질의 주소로 가리킨다.

## SDMX에서 무엇을 가져오나

SDMX 2.1 REST의 **데이터플로(dataflow)** = 하나의 통계표(예: 분기 국민계정). 기관마다
`{base}/dataflow/{agency}/all/latest`로 목록을 준다. 응답 형식이 기관마다 달라 둘 다 읽는다.

| 형식 | 예 |
|---|---|
| SDMX-JSON 1.0 구조(`application/vnd.sdmx.structure+json`) | OECD |
| SDMX-ML 2.1 구조(XML) | Eurostat(JSON 구조를 주지 않는다 — 406) |

XML은 **defusedxml**로 읽는다 — 외부 서버가 준 XML이라 엔티티 확장 공격을 막는다.

## 표시

    source_type    = 'external_catalog'    dataset_origin = 'external'    party = '3rd'
    source         = 'SDMX:<포털>'           external_ids   = ['sdmx:<기관>:<id>:<버전>']
    access_url     = SDMX 데이터 질의 주소    landing_page   = 포털 탐색 화면

라이선스는 포털 이용 약관 이름만 적는다. **확인되지 않은 라이선스라 외부 반출(결정 7)은 거부된다** —
허용 목록에 넣으려면 약관을 사람이 확인해야 한다.
"""

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

import requests
from defusedxml import ElementTree as SafeET

from src.collectors.adapters.rest_json import clean_text
from src.common.retry import RetryableError, with_retry

logger = logging.getLogger(__name__)

TIMEOUT = 60
URN_PREFIX = "urn:sdmx"
JSON_ACCEPT = "application/vnd.sdmx.structure+json;version=1.0"
XML_ACCEPT = "application/vnd.sdmx.structure+xml;version=2.1"

#: 알려진 SDMX 포털. 새 포털은 여기 한 줄 — 코드 수정 없이 `--endpoint`로도 된다
PRESETS: Dict[str, Dict[str, str]] = {
    "oecd": {"base": "https://sdmx.oecd.org/public/rest", "agency": "all", "publisher": "OECD",
             "license": "OECD Terms and Conditions",
             "explorer": "https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]={id}&df[ag]={agency}"},
    "eurostat": {"base": "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1", "agency": "ESTAT",
                 "publisher": "Eurostat", "license": "Eurostat copyright and re-use policy",
                 "explorer": "https://ec.europa.eu/eurostat/databrowser/view/{id}/default/table"},
    "ecb": {"base": "https://data-api.ecb.europa.eu/service", "agency": "ECB", "publisher": "European Central Bank",
            "license": "ECB statistics re-use terms", "explorer": "https://data.ecb.europa.eu/data/datasets/{id}"},
}

_NS = {"str": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
       "com": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"}
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_SAFE_ID = re.compile(r"[^A-Za-z0-9._@-]+")


def _pick(texts: Dict[str, str], fallback: Optional[str], langs=("en", "fr", "de")) -> str:
    """여러 언어 표기 중 영어 → 프랑스어 → 독일어 → 기본값 → 아무거나 순으로 고른다."""
    for lang in langs:
        if texts.get(lang):
            return texts[lang]
    if fallback:
        return fallback
    return next((v for v in texts.values() if v), "")


def parse_json(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SDMX-JSON 1.0 구조 응답 → 데이터플로 목록."""
    out = []
    for f in (doc.get("data") or {}).get("dataflows") or []:
        out.append({"id": f.get("id"), "agency": f.get("agencyID"), "version": f.get("version"),
                    "name": _pick(f.get("names") or {}, f.get("name")),
                    "description": _pick(f.get("descriptions") or {}, f.get("description"))})
    return out


def parse_xml(text: bytes) -> List[Dict[str, Any]]:
    """SDMX-ML 2.1 구조 응답 → 데이터플로 목록. 외부 XML이라 defusedxml로 읽는다."""
    root = SafeET.fromstring(text)
    out = []
    for f in root.iter(f"{{{_NS['str']}}}Dataflow"):
        names = {n.get(_XML_LANG, ""): (n.text or "").strip() for n in f.findall("com:Name", _NS)}
        descs = {n.get(_XML_LANG, ""): (n.text or "").strip() for n in f.findall("com:Description", _NS)}
        out.append({"id": f.get("id"), "agency": f.get("agencyID"), "version": f.get("version"),
                    "name": _pick(names, None), "description": _pick(descs, None)})
    return out


def fetch_dataflows(base: str, agency: str = "all") -> List[Dict[str, Any]]:
    """포털의 데이터플로 목록. JSON을 먼저 청하고, 주지 않으면 XML로 다시 청한다."""
    url = f"{base.rstrip('/')}/dataflow/{agency}/all/latest"

    def _get(accept: str):
        def _execute():
            r = requests.get(url, headers={"Accept": accept}, timeout=TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise RetryableError(f"HTTP {r.status_code}")
            return r
        return with_retry(_execute, max_attempts=4, base_delay=3.0)

    r = _get(JSON_ACCEPT)
    if r.status_code == 200 and "json" in r.headers.get("Content-Type", ""):
        flows = parse_json(r.json())
    else:
        r = _get(XML_ACCEPT)
        if r.status_code != 200:
            raise RuntimeError(f"SDMX 목록을 받지 못했습니다: HTTP {r.status_code}")
        flows = parse_xml(r.content)
    logger.info("SDMX %s: 데이터플로 %d개", base, len(flows))
    return flows


def select(flows: Iterable[Dict[str, Any]], query: str = "", max_records: int = 50) -> List[Dict[str, Any]]:
    """검색어(공백으로 나눈 낱말 **모두** 포함)로 고르고 상한을 둔다.

    포털에는 수천 개가 있다 — 전부 들이면 우리 카탈로그가 남의 것으로 덮인다(CKAN과 같은 원칙).
    ⚠️ OECD는 공개 데이터플로 **전부**(1,553/1,553)에 `NonProductionDataflow=true` 주석을 붙인다 —
    그 주석으로 거르면 0건이 된다(2026-11-11 실측). 주석으로 거르지 않는다.
    """
    terms = [t.lower() for t in query.split() if t]
    out = []
    for f in flows:
        if not f.get("id") or not f.get("name"):
            continue
        hay = f"{f['name']} {f.get('description') or ''}".lower()
        if all(t in hay for t in terms):
            out.append(f)
        if len(out) >= max_records:
            break
    return out


def _plain(text: str) -> str:
    """HTML 태그·엔티티를 벗기고 공백을 하나로."""
    return re.sub(r"\s+", " ", clean_text(text or "")).strip()


def to_dcat(flow: Dict[str, Any], portal: str, base: str, preset: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """데이터플로 → `dcat_dataset` 모양(ckan.store가 받는 형식)."""
    p = preset or {}
    agency, fid, ver = flow.get("agency") or "", flow["id"], flow.get("version") or "latest"
    safe = _SAFE_ID.sub("-", f"{agency}:{fid}")
    name = _plain(flow["name"])
    # 설명에 HTML이 섞여 온다(OECD) — 그대로 두면 검색·임베딩 텍스트에 태그가 낀다
    desc = _plain(flow.get("description") or "")
    if desc == name:
        desc = ""                                  # 제목 반복은 설명이 아니다
    explorer = p.get("explorer", "")
    return {
        "dataset_id": f"{URN_PREFIX}:{portal}:{safe}",
        "title": name[:500],
        "description": desc[:2000],
        "publisher": (p.get("publisher") or agency or portal)[:200],
        "source_type": "external_catalog",
        "source": f"SDMX:{portal}",
        "dataset_origin": "external",
        "party": "3rd",
        "keywords": ["SDMX", "통계"] + ([agency] if agency else []),
        "license": p.get("license"),
        "landing_page": explorer.format(id=fid, agency=agency) if explorer else None,
        "access_url": f"{base.rstrip('/')}/data/{agency},{fid},{ver}",
        "external_ids": [f"sdmx:{agency}:{fid}:{ver}"],
        "accrual_periodicity": None,
        "language": "en",
        "spatial": None,
    }


def harvest(portal: str = "oecd", query: str = "", max_records: int = 30,
            base: Optional[str] = None, agency: Optional[str] = None) -> List[Dict[str, Any]]:
    """포털에서 골라 DCAT 모양으로 바꾼 목록. DB는 건드리지 않는다."""
    preset = PRESETS.get(portal, {})
    base = base or preset.get("base")
    if not base:
        raise ValueError(f"모르는 SDMX 포털 {portal!r} — --endpoint로 주소를 주세요 (알려진 것: {sorted(PRESETS)})")
    flows = select(fetch_dataflows(base, agency or preset.get("agency", "all")), query, max_records)
    return [to_dcat(f, portal, base, preset) for f in flows]

