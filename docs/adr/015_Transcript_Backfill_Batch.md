# ADR 015: 자막 백필을 수집 스케줄러와 분리된 CronJob으로 운영

> **Date:** 2026-10-29
> **Status:** Accepted
> **Related:** [ADR-008](008_Lightweight_Scheduler.md) (보완, supersede 아님)

---

## 배경

YouTube 자막(자체 STT)은 두 경로로 생성된다.

| 경로 | 대상 | 예산 | 현 상태 |
|---|---|---|---|
| 수집 파이프라인 인라인 | **신규 유입분** | `YOUTUBE_TRANSCRIPT_BUDGET_SEC` 기본 600초 | 운영 중 |
| `scripts/backfill_youtube_transcripts.py` | **기존 백로그** | `--budget-sec` | 스크립트만 있고 스케줄 미등록 |

백로그 1,540건이 남아 있고, 스케줄을 걸지 않으면 그대로 쌓여 있다.
처리량 실측(2026-10-29, faster-whisper small / CPU int8 / 6스레드)은 **영상 길이의 1/3 시간**,
코퍼스 중앙값 3분 기준 **건당 약 46초**다.

- 인라인 예산 600초 = 회차당 약 13건 → 주간 수집이면 **2년 3개월**
- 야간 배치 8시간 = **620건/일** → **2.5일**

따라서 백필은 별도 배치로 돌려야 하며, 남은 결정은 **어디에 붙이는가**다.
ADR-008이 채택한 경량 스케줄러(`*/15 * * * *` CronJob 1개가 `next_collect_at` 폴링)에
잡을 추가하는 방식과, 독립 CronJob을 두는 방식이 후보였다.

## 결정

**독립 CronJob으로 둔다.** 경량 스케줄러에 편입하지 않는다.

### 근거

**1. 작업 단위가 다르다**

경량 스케줄러는 `data_registry.next_collect_at` 기준 **데이터셋 단위** 폴링이다.
자막 백필의 대상은 `meta_video.has_transcript = FALSE`인 **아이템 단위 백로그**라서
폴링 조건에 해당하는 행이 없다. 편입하려면 `data_registry`에 실제 데이터셋이 아닌
행을 만들거나 폴링 쿼리에 특수 분기를 넣어야 하고, 둘 다 스케줄러 계약
(와이즈넛 설계 초안 §4.3)을 흐린다.

**2. 실행 시간 규모가 두세 자리 다르다 — 수집이 멈춘다**

수집 1회는 수 초~수 분, 자막 배치는 8시간이다. 15분 폴링 루프 안에서 8시간 잡을
실행하면 ADR-008이 중복 실행 방지를 위해 건 `concurrencyPolicy: Forbid`에 걸려
**그 8시간 동안 모든 데이터셋 수집이 멈춘다.** 중복을 막으려던 장치가
여기서는 정반대로 작동한다.

**3. 리소스 프로파일이 반대다**

수집은 외부 API 응답 대기 중심(I/O bound, CPU 거의 쓰지 않음)이고,
STT는 CPU 6스레드를 점유한다(faster-whisper int8). 한 Pod에 두면 `requests`를
STT 기준으로 잡아야 하므로 수집만 도는 나머지 시간 동안 그 코어가 유휴 상태가 되고,
노드 스케줄링에도 불리하다.

**4. 실패 격리**

자막 배치가 모델 로드 실패·OOM으로 죽어도 수집은 영향이 없어야 하고, 반대도 같다.
한 Pod에 묶으면 이 격리가 사라진다.

### ADR-008과의 관계

ADR-008은 전환 재검토 조건에 **"백필·재처리를 단계 단위로 해야 할 때"**를 이미 적어뒀다.
이번 건은 단계 간 의존관계가 없는 단일 잡이므로 외부 오케스트레이터(Airflow)까지 갈
근거는 아니다. 다만 **백필을 스케줄러 본체에 섞지 않는다**는 방향 자체는 ADR-008과 일치한다.
ADR-008을 대체하지 않고 적용 범위를 명확히 하는 문서다.

## 운영 규격 (구현 시 적용)

| 항목 | 값 | 근거 |
|---|---|---|
| `schedule` | `0 1 * * *` (KST 01:00) | 수집 피크 회피. 야간 8시간 확보 |
| `spec.timeZone` | `Asia/Seoul` | 클러스터 v1.30.11에서 지원 확인 (아래 참조) |
| `concurrencyPolicy` | `Forbid` | 전날 잡이 안 끝났으면 건너뛴다 |
| `activeDeadlineSeconds` | `30600` (8.5h) | `--budget-sec` 로직이 실패해도 K8s가 끊는 2차 방어선 |
| `restartPolicy` / `backoffLimit` | `Never` / `0` | 멱등이지만 재시작은 시간 낭비. 다음 날 틱이 이어받는다 |
| 실행 인자 | `--limit 2000 --budget-sec 28800` | 둘 중 먼저 걸리는 쪽에서 멈춘다 |
| `resources` | CPU requests = limits = 6 | int8 6스레드 고정. burst 없이 예측 가능하게 |

백로그 1,540건은 620건/일 기준 **2.5일**이면 소진된다. 이후에는 인라인 예산을 넘긴
신규 유입분만 남으므로 대부분의 날은 수 분 내에 끝난다.
**백로그가 0이 되어도 CronJob은 유지한다** — 인라인 예산 600초를 넘겨 밀린 영상의
안전망 역할을 계속한다.

## 받아들이는 대가

CronJob이 2개가 되어 운영 대상이 하나 늘어난다. 다만 두 잡은 공유 상태가 없고
(`has_transcript` 플래그만 공유), 서로의 실패가 전파되지 않으므로
운영 복잡도 증가는 매니페스트 1개 수준으로 제한된다.

## 사전 확인 결과 (2026-10-29)

**`spec.timeZone` — 지원 확인됨.** K8s CronJob은 기본적으로 kube-controller-manager의
타임존(보통 UTC)을 따르므로 `0 1 * * *`을 그대로 쓰면 KST 10:00에 실행된다.
`spec.timeZone`은 1.27부터 GA이며, 운영 클러스터에서 다음을 확인했다.

| 확인 항목 | 결과 |
|---|---|
| 서버 버전 | `v1.30.11` (1.27 GA 이후) |
| `cronjob.spec.timeZone` 필드 | `kubectl explain`에 존재 |
| `timeZone: "Asia/Seoul"` 수용 | `kubectl apply --dry-run=server` 통과 |

→ **UTC 환산(`0 16 * * *`) 불필요.** `schedule: "0 1 * * *"` + `timeZone: "Asia/Seoul"`로 적는다.

## 확인 필요

- **인라인 STT와의 동시 처리** — 두 경로 모두 `meta_video.get_untranscribed()`를 호출하고,
  이 쿼리는 `WHERE has_transcript = FALSE ... ORDER BY id`다. 플래그는 처리 **완료 후**에
  바뀌므로, 01:00 배치가 도는 중에 수집 폴링 틱이 겹치면 **둘 다 id가 가장 작은 쪽부터
  집어 같은 영상을 중복 전사한다.** `ORDER BY id`가 같기 때문에 충돌이 목록 앞쪽에
  집중되는 구조다.
  데이터 손상은 아니다(같은 결과를 두 번 쓴다). 낭비되는 것은 CPU 시간이다.
  필요 시 `pg_try_advisory_lock(네임스페이스, hash(video_id))`로 막는다 — ADR-008이
  데이터셋 단위 중복 실행에 쓰기로 한 것과 같은 방식이다.
  **백로그 소진 전까지는 인라인 쪽 대상이 거의 없어 1차 구현에서는 생략해도 된다.**

## 참고

- 처리 속도 실측·예산 산정: `scripts/backfill_youtube_transcripts.py` docstring
- STT 설계 근거: [architecture/05_Object_Storage_Export.md](../architecture/05_Object_Storage_Export.md) §4.4
