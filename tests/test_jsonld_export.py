from datetime import date, datetime, timezone

from src.storage import jsonld_export


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        pass

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def test_base_jsonld_formats_dates_and_defaults():
    ctx = {
        "dataset_id": "ds1",
        "title": "t",
        "description": "d",
        "publisher": "Naver",
        "license": "lic",
        "accrual_periodicity": "P1D",
        "keywords": None,
        "temporal_start": date(2026, 1, 1),
        "temporal_end": None,
        "status": "active",
        "item_count": 3,
        "row_count": 30,
        "last_collected_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "next_collect_at": None,
    }
    doc = jsonld_export._base_jsonld(ctx)
    assert doc["@id"] == "mi:dataset/ds1"
    assert doc["dcat:keyword"] == []
    assert doc["mi:temporalStart"] == "2026-01-01"
    assert doc["mi:temporalEnd"] is None
    assert doc["mi:activeMetadata"]["itemCount"] == 3
    assert doc["mi:activeMetadata"]["lastCollectedAt"] == "2026-01-02T03:04:05+00:00"
    assert doc["mi:activeMetadata"]["nextCollectAt"] is None


def test_build_shopping_latest_snapshot_only_includes_max_period(monkeypatch):
    # meta_id=1, 카테고리 "A" (anchor): 2일치 × 2조합(gender/age 대신 단순화해 2행씩)
    rows = [
        (1, "cat_a", "A", True, date(2026, 1, 1), "m", "10", 50.0, 1.0, 50.0),
        (1, "cat_a", "A", True, date(2026, 1, 1), "f", "10", 40.0, 1.0, 40.0),
        (1, "cat_a", "A", True, date(2026, 1, 2), "m", "10", 55.0, 1.0, 55.0),
        (1, "cat_a", "A", True, date(2026, 1, 2), "f", "10", 45.0, 1.0, 45.0),
    ]
    monkeypatch.setattr(jsonld_export, "get_conn", lambda: _FakeConn(rows))
    captured_csv = {}
    monkeypatch.setattr(
        "src.storage.jsonld_export.raw_export.write_declarative_csv",
        lambda dataset_id, source_type, csv_rows: captured_csv.update(rows=csv_rows),
    )

    ctx = {
        "dataset_id": "ds1",
        "title": "t",
        "description": "d",
        "publisher": "Naver",
        "license": "lic",
        "accrual_periodicity": "P1D",
        "keywords": None,
        "temporal_start": None,
        "temporal_end": None,
        "status": "active",
        "item_count": 1,
        "row_count": 4,
        "last_collected_at": None,
        "next_collect_at": None,
    }
    doc = jsonld_export._build_shopping("ds1", ctx)

    assert len(doc["mi:items"]) == 1
    item = doc["mi:items"][0]
    assert item["mi:categoryId"] == "cat_a"
    assert item["mi:isAnchor"] is True
    assert item["mi:timeSeriesSummary"]["pointCount"] == 4
    assert item["mi:timeSeriesSummary"]["periodStart"] == "2026-01-01"
    assert item["mi:timeSeriesSummary"]["periodEnd"] == "2026-01-02"
    # latestSnapshot은 2026-01-02(최근 날짜)의 2개 조합만 포함, 2026-01-01분은 빠져야 함
    assert len(item["mi:latestSnapshot"]) == 2
    assert all(r["period"] == "2026-01-02" for r in item["mi:latestSnapshot"])
    assert len(captured_csv["rows"]) == 4
