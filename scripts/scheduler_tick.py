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
TICK_BUDGET_SEC = int(os.getenv("TICK_BUDGET_SEC", str(50 * 60)))

#: 시각 기준은 **UTC**. DB가 TIMESTAMPTZ라 비교는 서버가 하지만, 로그는 사람이 읽는다.
TZ = timezone.utc

#: 이 상태의 데이터셋만 돌린다. 'paused'는 의도적 중단이라 건드리지 않는다.
RUNNABLE_STATUS = ("active", "pending")

#: 같은 데이터셋이 두 틱에서 동시에 돌지 않게 하는 자문 잠금(advisory lock)의 키 공간.
#: 틱이 예산(50분)보다 오래 걸리고 크론이 1시간마다 돌면 겹칠 수 있다 —
#: 겹치면 같은 원천을 두 번 호출해 rate limit에 걸리고 item_count가 꼬인다.
#: 스키마 변경이 필요 없어서 테이블 락 대신 이것을 쓴다.
LOCK_NAMESPACE = 0x6D657461  # 'meta'


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


def due_datasets(conn, limit: int, dataset_id=None):
    """수집할 차례가 된 데이터셋. 오래 밀린 것부터 돌린다."""
    cur = conn.cursor()
    if dataset_id:
        cur.execute(
            "SELECT dataset_id, next_collect_at, status FROM data_registry WHERE dataset_id = %s",
            (dataset_id,),
        )
    else:
        cur.execute(
            "SELECT dataset_id, next_collect_at, status "
            "FROM   data_registry "
            "WHERE  status = ANY(%s) "
            "  AND  next_collect_at IS NOT NULL "
            "  AND  next_collect_at <= now() "
            "ORDER  BY next_collect_at "      # 가장 오래 밀린 것부터
            "LIMIT  %s",
            (list(RUNNABLE_STATUS), limit),
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


def tick(max_datasets: int, budget_sec: int, dry_run=False, dataset_id=None) -> int:
    conn = get_conn()
    rows = due_datasets(conn, max_datasets, dataset_id)
    now = datetime.now(TZ)

    if not rows:
        logger.info("수집할 차례가 된 데이터셋 없음 (기준 %s UTC)", now.strftime("%Y-%m-%d %H:%M"))
        return 0

    logger.info("대상 %d건 (틱 상한 %d, 예산 %d분)", len(rows), max_datasets, budget_sec // 60)
    for ds, due, st in rows:
        late = (now - due).days if due else None
        logger.info("   %-44s 예정 %s  %s일 경과  [%s]",
                    ds, due.strftime("%m-%d %H:%M") if due else "-", late, st)
    if dry_run:
        logger.info("dry-run — 실행하지 않는다")
        return len(rows)

    dl = _Deadline(budget_sec)
    ok = failed = skipped = 0

    for ds, _due, _st in rows:
        if dl.exhausted():
            # 남은 건은 다음 틱이 집는다 — next_collect_at이 그대로라 자연히 다시 due다
            logger.warning("예산 소진 — 남은 %d건은 다음 틱으로", len(rows) - ok - failed - skipped)
            break
        if not _try_lock(conn, ds):
            logger.warning("%s — 다른 틱이 실행 중, 건너뜀", ds)
            skipped += 1
            continue
        t0 = time.time()
        try:
            logger.info("▶ %s 시작 (남은 예산 %d초)", ds, dl.remaining())
            run_dataset(ds, triggered_by="scheduler_tick")
            ok += 1
            logger.info("✅ %s 완료 (%.1f초)", ds, time.time() - t0)
        except Exception as e:                     # noqa: BLE001
            # 한 건이 실패해도 나머지는 돌린다. 파이프라인이 실패 시
            # next_collect_at을 +1시간으로 잡으므로 재시도는 자동이다.
            failed += 1
            logger.error("❌ %s 실패 (%.1f초): %s", ds, time.time() - t0, e)
        finally:
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
