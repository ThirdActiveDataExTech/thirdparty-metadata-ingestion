from src.collectors.youtube_collector import (
    fetch_specific_videos,
    get_video_details,
    is_short,
    parse_duration_seconds,
)


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeVideosResource:
    def __init__(self, response):
        self._response = response

    def list(self, id, part):
        return _FakeRequest(self._response)


class _FakeService:
    def __init__(self, response):
        self._response = response

    def videos(self):
        return _FakeVideosResource(self._response)


def _video_item(video_id, duration):
    return {
        "id": video_id,
        "snippet": {"title": f"title-{video_id}", "thumbnails": {}},
        "statistics": {},
        "contentDetails": {"duration": duration},
        "topicDetails": {},
    }


def test_get_video_details_filters_shorts_by_default():
    response = {"items": [_video_item("short1", "PT30S"), _video_item("long1", "PT5M")]}
    service = _FakeService(response)
    videos = get_video_details(service, ["short1", "long1"])
    assert [v["video_id"] for v in videos] == ["long1"]


def test_get_video_details_keeps_shorts_when_filter_disabled():
    response = {"items": [_video_item("short1", "PT30S"), _video_item("long1", "PT5M")]}
    service = _FakeService(response)
    videos = get_video_details(service, ["short1", "long1"], filter_shorts=False)
    assert {v["video_id"] for v in videos} == {"short1", "long1"}


def test_fetch_specific_videos_does_not_filter_shorts():
    response = {"items": [_video_item("short1", "PT30S")]}
    service = _FakeService(response)
    videos = fetch_specific_videos(service, ["short1"])
    assert [v["video_id"] for v in videos] == ["short1"]


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
