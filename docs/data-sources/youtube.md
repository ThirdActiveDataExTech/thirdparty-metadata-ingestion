# YouTube

> **Last Updated:** 2026-07-01
> **dataset_id:** `youtube_{채널명}` (채널별로 별도 dataset_id)
> **source_type:** `video`

---

## 개요

YouTube Data API v3를 통해 특정 채널의 영상 메타데이터를 수집한다.
현재 수집 대상: 삼성전자 공식 채널 (`youtube_samsung_official`)

---

## API

| 항목 | 값 |
|------|-----|
| Endpoint | `https://www.googleapis.com/youtube/v3/videos` |
| 인증 | API Key |
| 수집 단위 | 채널 전체 영상 메타데이터 |
| 수집 주기 | 주 1회 (P7D) |

---

## 수집 대상

| dataset_id | 채널 | 채널 ID |
|------------|------|---------|
| `youtube_samsung_official` | 삼성전자 공식 | UCWwgaK7x0_FR1goeSRDDOkg |

---

## 수집 항목 (예정)

- 영상 ID, 제목, 설명
- 업로드일, 조회수, 좋아요 수, 댓글 수
- 썸네일 URL, 태그, 카테고리

---

## 관련 파일

- 수집 코드: `src/collectors/youtube_collector.py` (예정)
