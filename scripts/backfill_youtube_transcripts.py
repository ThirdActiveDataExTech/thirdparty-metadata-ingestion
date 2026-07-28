"""기존 YouTube 영상 트랜스크립트 소급 처리 (1회성 백로그 스크립트).

architecture/05_Object_Storage_Export.md §4.4 — 이 기능(자체 STT) 배포 이전에 이미
수집된 영상은 트랜스크립트가 없다. 정기 수집(`run()`)은 신규 발견 영상만 처리하므로
이 기존 백로그는 별도로 훑어야 한다. `meta_youtube_video.has_transcript=FALSE`인
영상을 대상으로 하며, 재실행해도 이미 처리된 영상은 건너뛴다(멱등).

사용 예:
  # 기본 10개만 (실측 처리 속도 확인용 파일럿)
  python scripts/backfill_youtube_transcripts.py --limit 10

  # 특정 데이터셋만
  python scripts/backfill_youtube_transcripts.py --dataset-id youtube_samsung_official --limit 5
"""

import argparse
import time
from datetime import datetime, timezone

from src.collectors import youtube_transcript_collector
from src.database import meta_youtube
from src.storage import raw_export


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=10, help="이번 실행에서 처리할 영상 수 (기본 10)")
    parser.add_argument("--dataset-id", default=None, help="지정 시 그 데이터셋만, 생략 시 전체")
    args = parser.parse_args()

    targets = meta_youtube.get_untranscribed(dataset_id=args.dataset_id, limit=args.limit)
    if not targets:
        print("처리할 대상 없음 (모든 영상에 이미 트랜스크립트가 있거나 대상 데이터셋에 영상 없음)")
        return

    print(f"대상 {len(targets)}개")
    success, failed = 0, 0
    for i, video in enumerate(targets, 1):
        t0 = time.time()
        result = youtube_transcript_collector.fetch_transcript(video["video_id"])
        elapsed = time.time() - t0

        if result is None:
            print(f"[{i}/{len(targets)}] {video['video_id']} — 실패 ({elapsed:.1f}s)")
            failed += 1
            continue

        segments, full_text, language = result
        raw_export.write_video_transcript(video["dataset_id"], video["video_id"], segments, full_text, language)
        meta_youtube.mark_transcribed(video["id"], transcribed_at=datetime.now(timezone.utc))
        print(
            f"[{i}/{len(targets)}] {video['video_id']} — 성공 ({elapsed:.1f}s, "
            f"language={language}, segments={len(segments)})"
        )
        success += 1

    print(f"완료: 성공 {success} / 실패 {failed} / 전체 {len(targets)}")


if __name__ == "__main__":
    main()
