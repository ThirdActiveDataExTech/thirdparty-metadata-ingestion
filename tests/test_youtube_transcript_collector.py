from types import SimpleNamespace

from src.collectors import youtube_transcript_collector


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


def test_transcribe_builds_segments_and_full_text(monkeypatch):
    fake_segments = [
        _FakeSegment(0.0, 4.2, " 안녕하세요 "),
        _FakeSegment(4.2, 9.8, "반갑습니다"),
        _FakeSegment(9.8, 10.0, "  "),  # 공백만 있는 세그먼트는 full_text에서 제외돼야 함
    ]
    fake_info = SimpleNamespace(language="ko")
    fake_model = SimpleNamespace(transcribe=lambda audio_path: (iter(fake_segments), fake_info))
    monkeypatch.setattr(youtube_transcript_collector, "_get_model", lambda: fake_model)

    segments, full_text, language = youtube_transcript_collector.transcribe("/tmp/fake.mp3")

    assert segments == [
        {"start": 0.0, "end": 4.2, "text": "안녕하세요"},
        {"start": 4.2, "end": 9.8, "text": "반갑습니다"},
        {"start": 9.8, "end": 10.0, "text": ""},
    ]
    assert full_text == "안녕하세요 반갑습니다"
    assert language == "ko"


def test_fetch_transcript_returns_none_when_download_fails(monkeypatch):
    monkeypatch.setattr(youtube_transcript_collector, "download_audio", lambda video_id, tmp_dir: None)
    assert youtube_transcript_collector.fetch_transcript("missing_video") is None


def test_fetch_transcript_swallows_exceptions(monkeypatch):
    def _boom(video_id, tmp_dir):
        raise RuntimeError("network error")

    monkeypatch.setattr(youtube_transcript_collector, "download_audio", _boom)
    assert youtube_transcript_collector.fetch_transcript("video_x") is None
