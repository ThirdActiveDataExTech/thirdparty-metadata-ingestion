"""영상 임베딩에 자막을 싣는 경로 (P0-2).

이 연결이 끊어져도 **아무 오류가 나지 않는다.** 자막 없는 영상과 똑같이
동작하고, 검색 결과가 조금 나빠질 뿐이라 눈으로는 안 보인다.
실제로 그 상태로 오래 있었다 — 1,554건 중 14건만 자막이 있는데 그 14건조차
S3에만 있고 임베딩은 제목·설명·태그만 쓰고 있었다.
"""

import pytest

from src.embedding import sync


class TestTextVideo:
    def test_자막이_있으면_텍스트에_들어간다(self):
        row = {"title": "제목", "description": "설명", "tags": None,
               "transcript": "옆으로 눕거나 쪼그리고 앉은 자세를 취합니다"}
        assert "쪼그리고" in sync._text_video(row)

    def test_자막이_없으면_예전과_같다(self):
        row = {"title": "제목", "description": "설명", "tags": ["태그1"]}
        assert sync._text_video(row) == "제목. 설명. 태그: 태그1"

    def test_자막이_빈_문자열이면_붙이지_않는다(self):
        row = {"title": "제목", "description": "설명", "tags": None, "transcript": ""}
        assert sync._text_video(row) == "제목. 설명"

    def test_자막은_2000자에서_자른다(self):
        # 뉴스·블로그 본문과 같은 상한. 청크 25개 안팎이 된다
        row = {"title": "t", "description": "", "tags": None, "transcript": "가" * 5000}
        assert sync._text_video(row).count("가") == 2000

    def test_자막이_제목_뒤에_온다(self):
        # 제목이 앞 청크에 오는 편이 짧은 질의에 유리하다
        row = {"title": "제목", "description": "", "tags": None, "transcript": "자막내용"}
        t = sync._text_video(row)
        assert t.index("제목") < t.index("자막내용")


class _FakeS3:
    def __init__(self, docs):
        self.docs = docs
        self.reads = []

    def storage_key(self, dataset_id):
        return dataset_id.replace(":", "_")

    def read_json(self, key):
        self.reads.append(key)
        return self.docs.get(key)


@pytest.fixture
def fake_s3(monkeypatch):
    def _apply(docs):
        fake = _FakeS3(docs)
        import src.storage.s3_client as real
        monkeypatch.setattr(real, "read_json", fake.read_json)
        monkeypatch.setattr(real, "storage_key", fake.storage_key)
        return fake
    return _apply


class TestAttachTranscripts:
    def test_플래그가_켜진_행만_읽는다(self, fake_s3):
        # 1,554건 중 14건만 자막이 있다. 전부 읽으면 1,540번의 헛된 왕복이다
        fake = fake_s3({"raw/video/ds1/v1.json": {"full_text": "자막"}})
        rows = [
            {"dataset_id": "ds1", "video_id": "v1", "has_transcript": True},
            {"dataset_id": "ds1", "video_id": "v2", "has_transcript": False},
            {"dataset_id": "ds1", "video_id": "v3", "has_transcript": None},
        ]
        assert sync._attach_transcripts(rows) == 1
        assert len(fake.reads) == 1
        assert rows[0]["transcript"] == "자막"
        assert "transcript" not in rows[1] and "transcript" not in rows[2]

    def test_대상이_없으면_S3를_건드리지_않는다(self, fake_s3):
        fake = fake_s3({})
        assert sync._attach_transcripts([{"has_transcript": False}]) == 0
        assert fake.reads == []

    def test_S3에_없으면_조용히_건너뛴다(self, fake_s3):
        # 플래그와 실제 파일이 어긋날 수 있다. 임베딩 전체를 멈출 이유가 없다
        fake_s3({})
        rows = [{"dataset_id": "ds1", "video_id": "v1", "has_transcript": True}]
        assert sync._attach_transcripts(rows) == 0
        assert "transcript" not in rows[0]

    def test_full_text가_비면_붙이지_않는다(self, fake_s3):
        fake_s3({"raw/video/ds1/v1.json": {"full_text": ""}})
        rows = [{"dataset_id": "ds1", "video_id": "v1", "has_transcript": True}]
        assert sync._attach_transcripts(rows) == 0

    def test_video_id가_없으면_건너뛴다(self, fake_s3):
        fake = fake_s3({})
        assert sync._attach_transcripts([{"dataset_id": "ds1", "has_transcript": True}]) == 0
        assert fake.reads == []


class TestSpec:
    def test_meta_video_조회에_자막_컬럼이_있다(self):
        # 컬럼이 빠지면 _attach_transcripts가 대상을 하나도 못 찾는다 —
        # 오류 없이 자막이 통째로 누락된다
        cols = sync._SPECS["meta_video"][4]
        for c in ("video_id", "has_transcript", "dataset_id"):
            assert c in cols, f"{c}가 조회 컬럼에 없다"
