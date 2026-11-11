"""수집 예정이 지난 데이터셋을 찾아 순서대로 돌린다 (C4 최소선 · P0-7).

**왜 필요한가.** 2026-11-02 실측에서 18개 데이터셋이 `next_collect_at`을 2~3일
넘긴 채 멈춰 있었다. Airflow가 아직 없고 K8s CronJob도 없어서 사람이 직접
`python -m src.main run <id>`를 쳐야만 수집이 되기 때문이다.

그 결과 발견형 3종(video·news·blog)의 `active_meta_*` 관측일이 **1일**뿐이고,
B2 시계열 공변동이 **정의 자체가 안 된다**. 시계열은 벽시계 시간으로만 쌓이므로
늦게 시작할수록 손해가 복리로 커진다
(docs/database/metadata_quality_probe.md).

**스케줄은 DB가 갖고 있다**(ADR-007). 파이프라인이 성공하면 스스로
`next_collect_at = 종료시각 + accrual_periodicity`로 갱신하고, 실패하면 +1시간으로
재시도를 잡는다. 그래서 이 스크립트가 할 일은 셋뿐이다 —
**due 조회 / 순차 호출 / 실패 격리.**

2026-11-11 보강 (3시간 시험 가동에서 본 문제 두 가지)

- **중단된 실행 수거.** 파드가 메모리 부족(OOMKilled)·시간 초과로 죽으면 파이프라인이 기록을
  남기기 전에 프로세스가 끝나, DB에는 아무 흔적이 없었다. 그러면 그 데이터셋은 계속 "가장 오래
  밀린 것"이라 다음 틱이 또 맨 먼저 집고, 또 죽고, 뒤의 데이터셋이 전부 막힌다. 그래서 시작할 때
  `dcat_provenance`에 진행 표시(`status='running'`, DDL에 원래 있는 값)를 남기고, 정상 종료하면
  파이프라인 기록으로 대체되도록 지운다. 다음 틱은 주인 없는 진행 표시(잠금이 풀린 것)를 찾아
  실패로 바꾸고, 반복될수록 재시도를 늦춘다(1시간 → 6시간 → 24시간).
- **짧은 것부터.** 블로그 1건이 53분 걸리는 동안 수 초짜리 쇼핑 5건이 전부 기다렸다. 예정이 지난
  것들 중 **최근 성공 실행 시간(중앙값)이 짧은 것부터** 돌린다. 기록이 없으면 중간값(5분)으로 본다.

실행:
    PYTHONPATH=. python scripts/scheduler_tick.py              # 기본 규격대로
    PYTHONPATH=. python scripts/scheduler_tick.py --dry-run    # 대상만 보고 끝
    PYTHONPATH=. python scripts/scheduler_tick.py --max 3      # 이번 틱은 3건만
    PYTHONPATH=. python scripts/scheduler_tick.py --dataset <id>   # 한 건 강제

운영 규격은 아래 상수에 모여 있다. 바꿀 때는 docs/adr 쪽도 같이 본다.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from src.database.db import get_conn
from src.main import run_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler_tick")

# ── 운영 규격 ──────────────────────────────────────────────────────
# 착수 전에 정해 둔다. 안 정하면 "일단 돌려보고" 사고가 난 뒤에 정하게 된다.

#: 한 틱이 손대는 최대 데이터셋 수. 한 번에 다 돌리려다 몇 시간씩 묶이는 것을 막는다.
MAX_DATASETS_PER_TICK = int(os.getenv("TICK_MAX_DATASETS", "10"))

#: 한 틱의 전체 시간 예산(초). 초과하면 **진행 중인 건을 끝내고** 다음 건은 안 집는다.
#: 중간에 끊지 않는 이유 — 파이프라인이 DB·S3를 중간 상태로 남길 수 있다.
#: 크론 주기(15분, 와이즈넛 계약)보다 짧게 둔다.
TICK_BUDGET_SEC = int(os.getenv("TICK_BUDGET_SEC", str(14 * 60)))

#: 시각 기준은 **UTC**. DB가 TIMESTAMPTZ라 비교는 서버가 하지만, 로그는 사람이 읽는다.
TZ = timezone.utc

#: 이 상태의 데이터셋만 돌린다. 'paused'는 의도적 중단이라 건드리지 않는다.
#: 'error'도 돌린다 — 파이프라인이 실패 시 next_collect_at을 +1시간으로 잡아 두므로 그 시각이
#: 지나면 재시도된다. ⚠️ 와이즈넛 자동 실행 계약의 폴링 조건은 ('pending','active')뿐이다(ADR-008).
#: 그대로면 일시적 오류 한 번에 사람이 손댈 때까지 멈춘다 → **우리 확장**, 와이즈넛 협의 대상
#: (2026-11-09 결정 11-2(b), NEXT_STEPS D1 메일 목록).
RUNNABLE_STATUS = ("active", "pending", "error")

#: 같은 데이터셋이 두 틱에서 동시에 돌지 않게 하는 자문 잠금(advisory lock)의 키 공간.
#: 틱이 예산(50분)보다 오래 걸리고 크론이 1시간마다 돌면 겹칠 수 있다 —
#: 겹치면 같은 원천을 두 번 호출해 rate limit에 걸리고 item_count가 꼬인다.
#: 스키마 변경이 필요 없어서 테이블 락 대신 이것을 쓴다.
LOCK_NAMESPACE = 0x6D657461  # 'meta'

#: 진행 표시 — `dcat_provenance.agent` 값. 파이프라인은 자기 모듈명을 쓰므로 겹치지 않는다
MARKER_AGENT = "scheduler_tick"
MARKER_NOTE = "수집 진행 표시 — 정상 종료되면 파이프라인 기록으로 대체되어 지워진다"
#: 중단된 실행의 오류 문구. src/common/error_kind.py의 `interrupted` 규칙이 이 앞부분으로 분류한다
INTERRUPTED_PREFIX = "수집 프로세스가 끝나지 않고 중단되었습니다"
INTERRUPTED_MSG = (INTERRUPTED_PREFIX
                   + " — 메모리 부족·실행 시간 초과·강제 종료로 추정됩니다(파드 종료 사유 확인 필요)")
#: 24시간 안 중단 횟수(이번 포함)별 재시도 간격(시간). 같은 원인으로 매시간 죽는 것을 막는다
INTERRUPTED_RETRY_HOURS = (1, 6, 24)
#: 성공 기록이 없는 데이터셋의 예상 실행 시간(초) — 정렬용
UNKNOWN_DURATION_SEC = 300


class _Deadline:
    """틱 예산과 종료 신호를 한 곳에서 본다."""

    def __init__(self, budget_sec: int):
        self.until = time.monotonic() + budget_sec
        self.stopped = False
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._stop)

    def _stop(self, signum, _frame):
        # K8s가 Pod를 정리할 때 SIGTERM을 보낸다. 진행 중인 건은 끝내고 다음은 안 집는다.
        logger.warning("종료 신호(%s) 수신 — 진행 중인 건을 끝내고 멈춘다", signum)
        self.stopped = True

    def exhausted(self) -> bool:
        return self.stopped or time.monotonic() >= self.until

    def remaining(self) -> int:
        return max(0, int(self.until - time.monotonic()))


#: 최근 성공 실행 5회의 소요 시간 중앙값(초). 성공 기록이 없으면 NULL
_EST_DURATION = """
    LEFT JOIN LATERAL (
        SELECT percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY EXTRACT(EPOCH FROM (h.ended_at - h.started_at))) AS sec
        FROM (SELECT started_at, ended_at FROM dcat_provenance p
              WHERE  p.dataset_id = r.dataset_id AND p.status = 'success' AND p.ended_at IS NOT NULL
              ORDER  BY p.started_at DESC LIMIT 5) h
    ) est ON true"""


def due_datasets(conn, limit: int, dataset_id=None):
    """수집할 차례가 된 데이터셋 — (id, 예정 시각, 상태, 예상 소요 초 또는 None).

    예상 소요가 짧은 것부터, 같으면 오래 밀린 것부터 돌린다(모듈 머리말 참조).
    """
    cur = conn.cursor()
    if dataset_id:
        cur.execute(
            "SELECT r.dataset_id, r.next_collect_at, r.status, est.sec "
            "FROM data_registry r" + _EST_DURATION + " WHERE r.dataset_id = %s",
            (dataset_id,),
        )
    else:
        cur.execute(
            "SELECT r.dataset_id, r.next_collect_at, r.status, est.sec "
            "FROM   data_registry r" + _EST_DURATION + " "
            "WHERE  r.status = ANY(%s) "
            "  AND  r.next_collect_at IS NOT NULL "
            "  AND  r.next_collect_at <= now() "
            "ORDER  BY coalesce(est.sec, %s), r.next_collect_at, r.dataset_id "
            "LIMIT  %s",
            (list(RUNNABLE_STATUS), UNKNOWN_DURATION_SEC, limit),
        )
    rows = cur.fetchall()
    cur.close()
    return rows


def _try_lock(conn, dataset_id: str) -> bool:
    """이 데이터셋을 지금 내가 돌려도 되는지. 다른 틱이 잡고 있으면 False."""
    cur = conn.cursor()
    # hashtext는 PostgreSQL 내장. 같은 문자열은 항상 같은 정수가 나온다.
    cur.execute("SELECT pg_try_advisory_lock(%s, hashtext(%s))", (LOCK_NAMESPACE, dataset_id))
    got = cur.fetchone()[0]
    cur.close()
    return got


def _unlock(conn, dataset_id: str) -> None:
    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_unlock(%s, hashtext(%s))", (LOCK_NAMESPACE, dataset_id))
    cur.close()


def _mark_start(conn, dataset_id: str) -> int:
    """진행 표시를 남기고 그 prov_id를 돌려준다. 바로 커밋한다 — 파드가 죽어도 남아야 한다."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dcat_provenance (dataset_id, activity_type, agent, triggered_by, status, notes) "
        "VALUES (%s, 'update', %s, %s, 'running', %s) RETURNING prov_id",
        (dataset_id, MARKER_AGENT, MARKER_AGENT, MARKER_NOTE),
    )
    prov_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return prov_id


def _settle_marker(conn, prov_id: int, dataset_id: str, error: Optional[str]) -> None:
    """실행이 (성공이든 예외든) 돌아온 뒤 진행 표시를 정리한다. 실패해도 틱은 계속 간다.

    파이프라인이 자기 기록을 남겼으면(표시보다 뒤의 prov_id) 표시는 지운다 — 계약대로 실행당 1행.
    남기지 못했으면(파이프라인 진입 전 예외 등) 표시를 그 실행의 결과 기록으로 바꾼다.
    """
    try:
        conn.rollback()     # 파이프라인이 남긴 미완료 트랜잭션이 있으면 버린다
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM dcat_provenance WHERE dataset_id = %s AND prov_id > %s LIMIT 1",
                    (dataset_id, prov_id))
        if cur.fetchone():
            cur.execute("DELETE FROM dcat_provenance WHERE prov_id = %s AND status = 'running'", (prov_id,))
        else:
            cur.execute(
                "UPDATE dcat_provenance SET status = %s, ended_at = now(), error_message = %s, notes = NULL "
                "WHERE prov_id = %s AND status = 'running'",
                ("failure" if error else "success", error, prov_id),
            )
        conn.commit()
        cur.close()
    except Exception as e:                         # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                          # noqa: BLE001
            pass
        logger.warning("%s — 진행 표시 정리 실패(다음 틱이 수거한다): %s", dataset_id, type(e).__name__)


def reap_interrupted(conn) -> int:
    """주인 없는 진행 표시 = 끝나지 못하고 죽은 실행. 실패로 바꾸고 재시도를 늦춘다. 수거한 건수.

    주인이 있는지는 자문 잠금으로 본다 — 실행 중인 세션은 그 데이터셋 잠금을 쥐고 있고, 세션이
    죽으면(파드 종료) 잠금도 풀린다.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT prov_id, dataset_id, started_at FROM dcat_provenance "
        "WHERE agent = %s AND status = 'running' AND ended_at IS NULL ORDER BY prov_id",
        (MARKER_AGENT,),
    )
    markers = cur.fetchall()
    conn.rollback()
    reaped = 0
    for prov_id, ds, started in markers:
        if not _try_lock(conn, ds):
            continue                               # 아직 누군가 돌리는 중
        try:
            cur.execute("SELECT 1 FROM dcat_provenance WHERE dataset_id = %s AND prov_id > %s LIMIT 1",
                        (ds, prov_id))
            if cur.fetchone():
                # 파이프라인은 기록을 남겼고 표시만 못 지운 경우 — 표시만 지운다
                cur.execute("DELETE FROM dcat_provenance WHERE prov_id = %s", (prov_id,))
                conn.commit()
                continue
            cur.execute(
                "SELECT count(*) FROM dcat_provenance WHERE dataset_id = %s AND agent = %s "
                "AND status = 'failure' AND error_message LIKE %s AND started_at > now() - interval '24 hours'",
                (ds, MARKER_AGENT, INTERRUPTED_PREFIX + "%"),
            )
            nth = cur.fetchone()[0] + 1            # 이번 포함 24시간 안 몇 번째 중단인가
            hours = INTERRUPTED_RETRY_HOURS[min(nth, len(INTERRUPTED_RETRY_HOURS)) - 1]
            cur.execute(
                "UPDATE dcat_provenance SET status = 'failure', ended_at = now(), error_message = %s, notes = NULL "
                "WHERE prov_id = %s",
                (INTERRUPTED_MSG, prov_id),
            )
            # 'paused'(사람이 멈춘 것)는 건드리지 않는다
            cur.execute(
                "UPDATE data_registry SET status = 'error', last_error = %s, "
                "next_collect_at = now() + make_interval(hours => %s), updated_at = now() "
                "WHERE dataset_id = %s AND status <> 'paused'",
                (INTERRUPTED_MSG, hours, ds),
            )
            conn.commit()
            reaped += 1
            logger.error("⚠ %s — %s 시작한 실행이 끝나지 못하고 중단됨(24시간 안 %d번째). %d시간 뒤 재시도",
                         ds, started.strftime("%m-%d %H:%M") if started else "-", nth, hours)
        except Exception as e:                     # noqa: BLE001
            conn.rollback()
            logger.warning("%s — 중단된 실행 수거 실패: %s", ds, type(e).__name__)
        finally:
            _unlock(conn, ds)
    cur.close()
    return reaped


def tick(max_datasets: int, budget_sec: int, dry_run=False, dataset_id=None) -> int:
    conn = get_conn()
    if not dry_run:
        reap_interrupted(conn)
    rows = due_datasets(conn, max_datasets, dataset_id)
    now = datetime.now(TZ)

    if not rows:
        logger.info("수집할 차례가 된 데이터셋 없음 (기준 %s UTC)", now.strftime("%Y-%m-%d %H:%M"))
        return 0

    logger.info("대상 %d건 (틱 상한 %d, 예산 %d분)", len(rows), max_datasets, budget_sec // 60)
    for ds, due, st, est in rows:
        late = (now - due).days if due else None
        logger.info("   %-44s 예정 %s  %s일 경과  [%s]  예상 %s",
                    ds, due.strftime("%m-%d %H:%M") if due else "-", late, st,
                    f"{est:.0f}초" if est is not None else "기록 없음")
    if dry_run:
        logger.info("dry-run — 실행하지 않는다")
        return len(rows)

    dl = _Deadline(budget_sec)
    ok = failed = skipped = 0

    for ds, _due, _st, _est in rows:
        if dl.exhausted():
            # 남은 건은 다음 틱이 집는다 — next_collect_at이 그대로라 자연히 다시 due다
            logger.warning("예산 소진 — 남은 %d건은 다음 틱으로", len(rows) - ok - failed - skipped)
            break
        if not _try_lock(conn, ds):
            logger.warning("%s — 다른 틱이 실행 중, 건너뜀", ds)
            skipped += 1
            continue
        t0 = time.time()
        marker = None
        error: Optional[str] = None
        try:
            marker = _mark_start(conn, ds)
            logger.info("▶ %s 시작 (남은 예산 %d초)", ds, dl.remaining())
            run_dataset(ds, triggered_by="scheduler_tick")
            ok += 1
            logger.info("✅ %s 완료 (%.1f초)", ds, time.time() - t0)
        except Exception as e:                     # noqa: BLE001
            # 한 건이 실패해도 나머지는 돌린다. 파이프라인이 실패 시
            # next_collect_at을 +1시간으로 잡으므로 재시도는 자동이다.
            failed += 1
            error = str(e)[:2000] or type(e).__name__
            logger.error("❌ %s 실패 (%.1f초): %s", ds, time.time() - t0, e)
        finally:
            if marker is not None:
                _settle_marker(conn, marker, ds, error)
            _unlock(conn, ds)

    logger.info("틱 종료 — 성공 %d · 실패 %d · 건너뜀 %d", ok, failed, skipped)
    # 실패가 있어도 틱 자체는 성공으로 본다(0). CronJob이 매번 실패로 뜨면
    # 알림이 무뎌진다 — 개별 실패는 data_registry.last_error와 로그로 본다.
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=MAX_DATASETS_PER_TICK,
                    help=f"이번 틱의 최대 데이터셋 수 (기본 {MAX_DATASETS_PER_TICK})")
    ap.add_argument("--budget", type=int, default=TICK_BUDGET_SEC,
                    help=f"이번 틱의 시간 예산(초) (기본 {TICK_BUDGET_SEC})")
    ap.add_argument("--dry-run", action="store_true", help="대상만 보고 끝낸다")
    ap.add_argument("--dataset", help="예정 시각과 무관하게 이 데이터셋 하나만 돌린다")
    args = ap.parse_args()
    return tick(args.max, args.budget, args.dry_run, args.dataset)


if __name__ == "__main__":
    sys.exit(main())
