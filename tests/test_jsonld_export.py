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
        "external_ids": ["youtube:UCabc", "naver:news"],
        "temporal_start": date(2026, 1, 1),
        "temporal_end": None,
        "status": "active",
        "item_count": 3,
        "row_count": 30,
        "last_collected_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "next_collect_at": None,
    }
    doc = jsonld_export._base_jsonld(ctx)
    # dataset_id 자체가 URN이라 그대로 @id가 된다(2026-10-28 전환).
    # 이전 형식은 mi:dataset/{slug} CURIE였다.
    assert doc["@id"] == "ds1"
    assert doc["dct:identifier"] == "ds1"
    assert doc["dcat:keyword"] == []
    assert doc["adms:identifier"] == ["youtube:UCabc", "naver:news"]
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
        "external_ids": None,
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


class TestContextContract:
    """`_fetch_dataset_context`가 넘기는 키와 `_base_jsonld`가 읽는 키를 맞춰 둔다.

    2026-10-28 와이즈넛 정렬에서 `external_ids` 컬럼이 늘었을 때, 쿼리와
    `_base_jsonld`는 고쳐졌으나 이 파일의 픽스처가 따라가지 못해 두 테스트가
    `KeyError`로 죽은 채 커밋됐다. 눈으로는 둘이 떨어져 있어 안 보인다.

    여기서는 **컬럼이 늘거나 줄면 바로 드러나게** 양쪽을 직접 대조한다.
    """

    @staticmethod
    def _query_keys():
        """SELECT 절에서 돌려주는 컬럼 이름 — 코드에서 직접 읽는다."""
        import inspect
        import re

        src = inspect.getsource(jsonld_export._fetch_dataset_context)
        select = re.search(r"SELECT(.*?)FROM", src, re.S).group(1)
        return {c.strip().split(".")[-1] for c in select.split(",") if c.strip()}

    @staticmethod
    def _consumed_keys():
        """`_base_jsonld`가 ctx[...]로 꺼내 쓰는 키."""
        import inspect
        import re

        src = inspect.getsource(jsonld_export._base_jsonld)
        return set(re.findall(r'ctx\["([a-z_]+)"\]', src))

    def test_읽는_키는_전부_쿼리가_넘긴다(self):
        missing = self._consumed_keys() - self._query_keys()
        assert not missing, f"쿼리가 안 넘기는 키를 읽는다: {sorted(missing)}"

    def test_픽스처가_쿼리_컬럼을_전부_담는다(self):
        # 픽스처가 뒤처지면 이 테스트가 먼저 알려준다 — KeyError로 죽기 전에
        import inspect
        import re

        src = inspect.getsource(test_base_jsonld_formats_dates_and_defaults)
        fixture = set(re.findall(r'"([a-z_]+)":', src))
        missing = self._consumed_keys() - fixture
        assert not missing, f"픽스처에 빠진 키: {sorted(missing)}"
