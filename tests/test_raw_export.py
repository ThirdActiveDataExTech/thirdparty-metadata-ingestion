from src.storage import raw_export


def test_write_video_transcript_key_and_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.storage.raw_export.s3_client.upload_json",
        lambda key, obj: captured.update(key=key, obj=obj),
    )
    key = raw_export.write_video_transcript(
        "ds1", "vid1", [{"start": 0.0, "end": 1.0, "text": "hi"}], "hi", "ko"
    )
    assert key == "raw/video/ds1/vid1.json"
    assert captured["key"] == key
    assert captured["obj"] == {
        "video_id": "vid1",
        "language": "ko",
        "segments": [{"start": 0.0, "end": 1.0, "text": "hi"}],
        "full_text": "hi",
    }


def test_write_article_content_key_by_source_type(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.storage.raw_export.s3_client.upload_text",
        lambda key, text: captured.update(key=key, text=text),
    )
    key = raw_export.write_article_content("ds1", "news", 42, "본문")
    assert key == "raw/news/ds1/42.txt"
    assert captured["text"] == "본문"

    key2 = raw_export.write_article_content("ds1", "blog", 7, "게시물 본문")
    assert key2 == "raw/blog/ds1/7.txt"


def test_write_declarative_csv_header_and_rows(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.storage.raw_export.s3_client.upload_text",
        lambda key, text: captured.update(key=key, text=text),
    )
    rows = [
        {"category_id": "1", "period": "2026-01-01", "pseudo_volume": 10.5},
        {"category_id": "1", "period": "2026-01-02", "pseudo_volume": 11.0},
    ]
    key = raw_export.write_declarative_csv("ds1", "shopping_insight", rows)
    assert key == "raw/shopping_insight/ds1/ds1.csv"
    lines = captured["text"].strip().splitlines()
    assert lines[0] == "category_id,period,pseudo_volume"
    assert lines[1] == "1,2026-01-01,10.5"
    assert len(lines) == 3


def test_write_declarative_csv_empty_rows_writes_empty_body(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.storage.raw_export.s3_client.upload_text",
        lambda key, text: captured.update(key=key, text=text),
    )
    raw_export.write_declarative_csv("ds1", "persona_insight", [])
    assert captured["text"] == ""
