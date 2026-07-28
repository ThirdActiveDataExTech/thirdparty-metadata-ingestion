from src.pipelines import youtube_pipeline


def _video(video_id):
    return {"video_id": video_id}


def test_fetch_remote_videos_merges_channels_and_individual_videos(monkeypatch):
    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_channel_videos",
        lambda service, channel_id: [_video(f"{channel_id}-a"), _video(f"{channel_id}-b")],
    )
    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_specific_videos",
        lambda service, video_ids: [_video(v) for v in video_ids],
    )

    result = youtube_pipeline._fetch_remote_videos(None, ["chA"], ["v1", "v2"])

    assert [v["video_id"] for v in result] == ["chA-a", "chA-b", "v1", "v2"]


def test_fetch_remote_videos_dedupes_overlap_between_channel_and_individual(monkeypatch):
    # chA의 영상 목록에 이미 "v1"이 있는데, 관리자가 --videos로도 v1을 또 지정한 경우
    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_channel_videos",
        lambda service, channel_id: [_video("v1"), _video("chA-b")],
    )
    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_specific_videos",
        lambda service, video_ids: [_video(v) for v in video_ids],
    )

    result = youtube_pipeline._fetch_remote_videos(None, ["chA"], ["v1"])

    video_ids = [v["video_id"] for v in result]
    assert video_ids == ["v1", "chA-b"]  # v1은 채널 쪽에서만 1번 유지, 중복 없음


def test_fetch_remote_videos_no_individual_videos_skips_specific_call(monkeypatch):
    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_channel_videos",
        lambda service, channel_id: [_video("chA-a")],
    )

    def _fail(*args, **kwargs):
        raise AssertionError("videos가 비어있으면 fetch_specific_videos를 호출하면 안 됨")

    monkeypatch.setattr(
        "src.pipelines.youtube_pipeline.youtube_collector.fetch_specific_videos", _fail
    )

    result = youtube_pipeline._fetch_remote_videos(None, ["chA"], [])

    assert [v["video_id"] for v in result] == ["chA-a"]
