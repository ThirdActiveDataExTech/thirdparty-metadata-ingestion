# YouTube

> **Last Updated:** 2026-07-28
> **dataset_id:** 채널당/큐레이션당 자유 (예: `youtube_{채널명}`, `user_{제목}_{랜덤}`)
> **source_type:** `video`
> **상태:** Collector 구현·검증 완료(§6.1), SeaweedFS raw/JSON-LD 저장 + 자체 STT
> 트랜스크립트까지 구현·검증 완료(architecture/05_Object_Storage_Export.md)

---

## 개요

YouTube Data API v3로 채널 영상 메타데이터를 수집한다. 등록 시점에 **채널
전체 발견**과 **관리자가 직접 고른 개별 영상**을 한 데이터셋 안에 섞을 수 있다
(2026-07-28 확장 — "위암수술전 환자 추천영상"처럼 여러 채널에서 영상을 하나씩
고르는 큐레이션형 데이터셋 지원 목적).

## API

| 항목 | 값 |
|------|-----|
| Endpoint | YouTube Data API v3 (`channels`/`playlistItems`/`videos`) |
| 인증 | API Key (`YOUTUBE_API_KEY` 플랫폼 공유 폴백, 또는 데이터셋별 `dataset_credentials`) |
| 수집 단위 | 채널 전체 영상(재생목록 페이지네이션) 또는 관리자가 지정한 개별 video_id |
| 수집 주기 | 데이터셋마다 다름(`accrual_periodicity`, 기본 `P1D`) |
| Shorts(≤60초) | 채널 전체 발견 시에는 자동 제외, 개별 지정 영상은 제외 안 함(명시적 선택 존중) |

## 현재 등록된 데이터셋 (실 DB 기준, 2026-07-28)

| dataset_id | 채널 | 성격 |
|---|---|---|
| `youtube_samsung_official` | 삼성전자 글로벌 채널(`UCWwgaK7x0_FR1goeSRazfsQ`) | 개발/검증용 — 실 서비스 데이터셋으로 교체될 가능성 있음 |
| `youtube_sk_hynix_official` | SK하이닉스 채널(`UCltyil2FaQZZ4kUNinKkKmw`) | 개발/검증용 |
| `user_hbm_video_collection` | 위 두 채널 혼합 | 개발/검증용 |

과거 이 문서에 적혀있던 채널 ID(`UCWwgaK7x0_FR1goeSRDDOkg`)는 **실존하지 않는
오기**였다 — 실제 삼성전자 채널 ID로 정정됨(`UCWwgaK7x0_FR1goeSRazfsQ`).

## 수집 항목 (구현 완료)

- 영상 ID, 제목, 설명, 태그, 카테고리, topic categories
- 업로드일, 조회수, 좋아요 수, 댓글 수(시계열, `active_meta_youtube`)
- 썸네일 URL, 재생시간, 화질, 자막 유무, 언어
- **트랜스크립트**(`has_transcript`/`transcribed_at` 컬럼, SeaweedFS
  `raw/video/{dataset_id}/{video_id}.json`에 세그먼트+전체텍스트 저장) — 자체
  STT(`yt-dlp` 오디오 다운로드 + `faster-whisper` 로컬 전사). 레거시가 쓰던
  `youtube-transcript-api`(비공식 API 직접 호출)는 IP 차단이 확인돼 채택 안 함,
  상세: [architecture/05_Object_Storage_Export.md](../architecture/05_Object_Storage_Export.md) §4
- 삭제 감지(`is_removed`/`removed_at`) — 채널 전체 발견은 재생목록 페이지네이션이라
  "이번 실행에 없으면 삭제"가 안전, 개별 지정 영상도 `videos.list` 직접 조회라
  같은 판정이 안전하게 적용됨

## 등록 방법 (지금은 CLI, §6.3 프론트엔드 API 전까지)

```bash
# 채널 전체
python scripts/register_dataset.py video \
    --title "..." --description "..." --subjects <채널ID,채널ID,...>

# 채널과 개별 영상 혼합
python scripts/register_dataset.py video \
    --title "..." --description "..." \
    --subjects <채널ID> --videos <video_id,video_id,...>
```

**알려진 제약**: 채널 URL(`youtube.com/@핸들`)이나 핸들을 채널 ID로 자동 변환하는
기능이 아직 없다 — 지금은 채널 ID를 직접 알아내서 넣어야 한다(§6.3에서 해결
예정, `04_Collection_Pipeline_Operations.md` §5.1 참조).

## 관련 파일

- 콜렉터: `src/collectors/youtube_collector.py`(채널 발견), `src/collectors/
  youtube_transcript_collector.py`(STT)
- 파이프라인: `src/pipelines/youtube_pipeline.py`
- 백필: `scripts/backfill_youtube_transcripts.py` (기존 영상 트랜스크립트
  소급 처리 — 현재 데이터셋들은 개발/테스트용이라 아직 실행 안 함,
  `NEXT_STEPS.md` §6.2 안전망 태스크 항목 참조)
