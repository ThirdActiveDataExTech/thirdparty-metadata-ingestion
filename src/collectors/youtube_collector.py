"""YouTube Data API v3 — 순수 API 호출만 담당, DB 접근 없음.

레거시(3amd/youtube_channel_extractor.py, youtube_video_extractor.py)의 페이지네이션·
50개 배치·Shorts 필터 로직을 병합·중복 제거해 포팅했다. 채널명→채널ID 해석은
등록 시점(runbooks/04_Add_New_Dataset_Existing_Source.md §5.5)에 이미 끝난다고
전제하고, 여기서는 채널 ID를 입력으로 받는다.
"""

import re
import time
from typing import Any, Dict, List

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.common.retry import RetryableError, with_retry

SHORTS_MAX_SECONDS = 60
_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def build_service(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


def parse_duration_seconds(duration: str) -> int:
    """ISO 8601 duration('PT1H2M3S')을 초 단위로 변환."""
    m = _DURATION_RE.match(duration)
    if not m:
        return 0
    parts = m.groupdict()
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def is_short(duration: str) -> bool:
    return parse_duration_seconds(duration) <= SHORTS_MAX_SECONDS


def _call_with_retry(request):
    def _execute():
        try:
            return request.execute()
        except HttpError as e:
            if e.resp is not None and e.resp.status >= 500:
                raise RetryableError(str(e))
            raise  # 4xx(쿼터 초과 등)는 재시도해도 소용없음 — 즉시 전파

    return with_retry(_execute)


def get_uploads_playlist_id(service, channel_id: str) -> Dict[str, str]:
    """채널의 업로드 재생목록 ID와 채널명을 함께 반환."""
    resp = _call_with_retry(
        service.channels().list(id=channel_id, part="contentDetails,snippet")
    )
    items = resp.get("items", [])
    if not items:
        raise ValueError(f"channel_id={channel_id!r}에 해당하는 채널 없음")
    item = items[0]
    return {
        "playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
        "channel_title": item["snippet"]["title"],
    }


def get_all_video_ids(service, playlist_id: str) -> List[str]:
    """업로드 재생목록의 전체 video_id를 페이지네이션으로 수집."""
    video_ids: List[str] = []
    page_token = None
    while True:
        resp = _call_with_retry(
            service.playlistItems().list(
                playlistId=playlist_id,
                part="contentDetails",
                maxResults=50,
                pageToken=page_token,
            )
        )
        for item in resp.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.1)
    return video_ids


def _normalize_video(item: Dict[str, Any]) -> Dict[str, Any]:
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})
    topic_details = item.get("topicDetails", {})

    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = None
    for key in ("maxres", "high", "medium", "default"):
        if key in thumbnails:
            thumbnail_url = thumbnails[key]["url"]
            break

    duration = content_details.get("duration", "PT0S")

    return {
        "video_id": item["id"],
        "title": snippet.get("title", ""),
        "description": snippet.get("description"),
        "published_at": snippet.get("publishedAt"),
        "channel_id": snippet.get("channelId"),
        "channel_title": snippet.get("channelTitle"),
        "tags": snippet.get("tags", []),
        "category_id": snippet.get("categoryId"),
        "topic_categories": topic_details.get("topicCategories", []),
        "duration": duration,
        "duration_seconds": parse_duration_seconds(duration),
        "definition": content_details.get("definition"),
        "default_language": snippet.get("defaultLanguage"),
        "default_audio_language": snippet.get("defaultAudioLanguage"),
        "has_caption": content_details.get("caption") == "true",
        "thumbnail_url": thumbnail_url,
        "view_count": int(statistics["viewCount"]) if "viewCount" in statistics else None,
        "like_count": int(statistics["likeCount"]) if "likeCount" in statistics else None,
        "comment_count": int(statistics["commentCount"]) if "commentCount" in statistics else None,
    }


def get_video_details(service, video_ids: List[str]) -> List[Dict[str, Any]]:
    """video_id 목록을 50개씩 배치로 조회 — Shorts(<=60초)는 결과에서 제외."""
    videos: List[Dict[str, Any]] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = _call_with_retry(
            service.videos().list(
                id=",".join(batch),
                part="snippet,statistics,contentDetails,topicDetails",
            )
        )
        for item in resp.get("items", []):
            video = _normalize_video(item)
            if is_short(video["duration"]):
                continue
            videos.append(video)
        time.sleep(0.1)
    return videos


def fetch_channel_videos(service, channel_id: str) -> List[Dict[str, Any]]:
    """채널 1개의 전체 영상(Shorts 제외) 메타데이터를 반환하는 최상위 진입점."""
    playlist_info = get_uploads_playlist_id(service, channel_id)
    video_ids = get_all_video_ids(service, playlist_info["playlist_id"])
    return get_video_details(service, video_ids)
