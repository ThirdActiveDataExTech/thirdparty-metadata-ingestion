"""SDMX 연합 탐색 (C6 · 3차년도, 2026-11-11) — 실제 응답 모양에서 출발한다.

JSON은 OECD, XML은 Eurostat 응답을 줄인 것이다.
"""

import pytest
from defusedxml import EntitiesForbidden

from src.federation import ckan, sdmx

OECD_JSON = {"data": {"dataflows": [
    {"id": "DSD_REG_ECO@DF_INC", "version": "2.4", "agencyID": "OECD.CFE.EDS", "name": "Income - Regions",
     "names": {"en": "Income - Regions"}, "description": "<p>Disposable&nbsp;income</p>",
     "descriptions": {"en": "<p>Disposable&nbsp;income in <b>regions</b></p>"},
     "annotations": [{"type": "NonProductionDataflow", "text": "true"}]},
    {"id": "AIR", "version": "1.0", "agencyID": "ESTAT", "name": "Air Emissions", "names": {"en": "Air Emissions"},
     "description": "Air Emissions", "descriptions": {"en": "Air Emissions"}},
    {"id": "", "name": "이름만"},
]}}

ESTAT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<m:Structure xmlns:m="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
  xmlns:s="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure"
  xmlns:c="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common">
 <m:Structures><s:Dataflows>
  <s:Dataflow id="UNE_RT_M" agencyID="ESTAT" version="1.0">
   <c:Name xml:lang="de">Arbeitslosigkeit</c:Name>
   <c:Name xml:lang="en">Unemployment by sex and age - monthly data</c:Name>
  </s:Dataflow>
  <s:Dataflow id="NAMA_10_GDP" agencyID="ESTAT" version="1.0">
   <c:Name xml:lang="fr">PIB et principaux composants</c:Name>
   <c:Description xml:lang="fr">Comptes nationaux</c:Description>
  </s:Dataflow>
 </s:Dataflows></m:Structures>
</m:Structure>"""


class TestParse:
    def test_JSON_구조_응답(self):
        flows = sdmx.parse_json(OECD_JSON)
        assert flows[0]["id"] == "DSD_REG_ECO@DF_INC" and flows[0]["agency"] == "OECD.CFE.EDS"
        assert flows[0]["description"].startswith("<p>Disposable")

    def test_XML_구조_응답_언어는_영어부터(self):
        flows = sdmx.parse_xml(ESTAT_XML)
        assert flows[0]["name"] == "Unemployment by sex and age - monthly data"
        assert flows[1]["name"] == "PIB et principaux composants"       # 영어가 없으면 프랑스어
        assert flows[1]["description"] == "Comptes nationaux"

    def test_엔티티_확장_XML은_거부한다(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><x>&b;</x>'
        with pytest.raises(EntitiesForbidden):
            sdmx.parse_xml(bomb)


class TestSelect:
    def test_낱말을_모두_포함한_것만_상한까지(self):
        flows = sdmx.parse_json(OECD_JSON)
        assert [f["id"] for f in sdmx.select(flows, "income regions")] == ["DSD_REG_ECO@DF_INC"]
        assert sdmx.select(flows, "income air") == []
        assert len(sdmx.select(flows, "", max_records=1)) == 1

    def test_OECD_NonProduction_주석으로_거르지_않는다(self):
        # OECD는 공개 데이터플로 전부에 이 주석을 붙인다 — 거르면 0건(2026-11-11 실측)
        assert sdmx.select(sdmx.parse_json(OECD_JSON), "income")

    def test_식별자나_이름이_없으면_뺀다(self):
        assert all(f["id"] for f in sdmx.select(sdmx.parse_json(OECD_JSON), ""))


class TestToDcat:
    def row(self):
        f = sdmx.parse_json(OECD_JSON)[0]
        return sdmx.to_dcat(f, "oecd", sdmx.PRESETS["oecd"]["base"], sdmx.PRESETS["oecd"])

    def test_외부_통계로_표시하고_원천을_가리킨다(self):
        r = self.row()
        assert r["dataset_id"] == "urn:sdmx:oecd:OECD.CFE.EDS-DSD_REG_ECO@DF_INC"
        assert (r["source_type"], r["dataset_origin"], r["party"], r["source"]) == \
            ("external_catalog", "external", "3rd", "SDMX:oecd")
        assert r["access_url"] == "https://sdmx.oecd.org/public/rest/data/OECD.CFE.EDS,DSD_REG_ECO@DF_INC,2.4"
        assert "df[id]=DSD_REG_ECO@DF_INC" in r["landing_page"]
        assert r["external_ids"] == ["sdmx:OECD.CFE.EDS:DSD_REG_ECO@DF_INC:2.4"]

    def test_HTML을_걷어낸다(self):
        assert self.row()["description"] == "Disposable income in regions"

    def test_제목을_반복한_설명은_비운다(self):
        f = sdmx.parse_json(OECD_JSON)[1]
        assert sdmx.to_dcat(f, "oecd", "https://x")["description"] == ""

    def test_한국어_한국_소재로_두지_않는다(self):
        r = self.row()
        assert r["language"] == "en" and r["spatial"] is None

    def test_라이선스는_반출_허용_목록에_없다(self):
        from src.export import policy
        assert policy.eligibility("external_catalog", "PUBLIC", self.row()["license"]).allowed is False


class FakeResp:
    def __init__(self, status, ctype, body):
        self.status_code, self.headers, self._body = status, {"Content-Type": ctype}, body
        self.content = body if isinstance(body, bytes) else b""

    def json(self):
        return self._body


def test_JSON을_주지_않으면_XML로_다시_청한다(monkeypatch):
    seen = []

    def get(url, headers, timeout):
        seen.append(headers["Accept"])
        if "json" in headers["Accept"]:
            return FakeResp(406, "text/html", b"Not Acceptable")
        return FakeResp(200, "application/xml", ESTAT_XML)
    monkeypatch.setattr(sdmx.requests, "get", get)
    flows = sdmx.fetch_dataflows("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1", "ESTAT")
    assert len(flows) == 2 and seen == [sdmx.JSON_ACCEPT, sdmx.XML_ACCEPT]


def test_모르는_포털은_주소를_요구한다():
    with pytest.raises(ValueError, match="--endpoint"):
        sdmx.harvest("unknown")


def test_적재는_새_행에만_공개_범위를_주고_잘못된_값은_거부한다():
    import inspect
    with pytest.raises(ValueError):
        ckan.store([{"x": 1}], visibility="EVERYONE")
    src = inspect.getsource(ckan.store)
    assert "visibility = EXCLUDED" not in src           # 이미 있는 행의 공개 범위는 사람이 정한 값
    assert "access_url = COALESCE(EXCLUDED.access_url" in src
