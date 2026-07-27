from src.collectors.youtube_collector import is_short, parse_duration_seconds


def test_parse_duration_seconds_hours_minutes_seconds():
    assert parse_duration_seconds("PT1H2M3S") == 3723


def test_parse_duration_seconds_minutes_only():
    assert parse_duration_seconds("PT5M") == 300


def test_parse_duration_seconds_seconds_only():
    assert parse_duration_seconds("PT45S") == 45


def test_parse_duration_seconds_zero():
    assert parse_duration_seconds("PT0S") == 0


def test_is_short_true_for_60_seconds_or_less():
    assert is_short("PT60S") is True
    assert is_short("PT59S") is True
    assert is_short("PT0S") is True


def test_is_short_false_for_over_60_seconds():
    assert is_short("PT1M1S") is False
    assert is_short("PT10M") is False
