"""수집 스케줄러 틱 — 실패 격리·중복 방지·예산 준수.

이 스크립트가 틀리면 드러나는 방식이 고약하다. 한 데이터셋이 실패했을 때
나머지를 안 돌리면 **조용히 수집이 멈추고**, 그 사실은 몇 주 뒤 시계열이
비어 있는 것으로만 드러난다(실제로 2026-11-02에 그렇게 발견됐다).
"""

import importlib

import pytest

tick_mod = importlib.import_module("scripts.scheduler_tick")


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.sql.append((sql, params))
        if "pg_try_advisory_lock" in sql:
            self._result = [(self.conn.lock_grants.pop(0) if self.conn.lock_grants else True,)]
        elif "pg_advisory_unlock" in sql:
            self.conn.unlocked.append(params[1])
            self._result = [(True,)]
        else:
            self._result = self.conn.rows

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0]

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows=(), lock_grants=None):
        self.rows = list(rows)
        self.lock_grants = list(lock_grants or [])
        self.sql = []
        self.unlocked = []

    def cursor(self):
        return _FakeCursor(self)


from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)


def _rows(n):
    return [(f"urn:test:ds{i}", NOW - timedelta(days=i + 1), "active") for i in range(n)]


@pytest.fixture
def harness(monkeypatch):
    state = {"ran": [], "fail": set()}

    def _run(ds, triggered_by=None):
        state["ran"].append(ds)
        if ds in state["fail"]:
            raise RuntimeError("수집 실패 시뮬레이션")

    def _apply(rows=(), lock_grants=None, fail=()):
        conn = _FakeConn(rows, lock_grants)
        state["fail"] = set(fail)
        monkeypatch.setattr(tick_mod, "get_conn", lambda: conn)
        monkeypatch.setattr(tick_mod, "run_dataset", _run)
        # 시그널 핸들러 등록을 건너뛴다 — pytest는 메인 스레드가 아닐 수 있다
        monkeypatch.setattr(tick_mod.signal, "signal", lambda *a: None)
        return conn, state

    return _apply


class TestDueSelection:
    def test_paused는_대상이_아니다(self, harness):
        conn, _ = harness(rows=_rows(1))
        tick_mod.tick(10, 600, dry_run=True)
        sql, params = conn.sql[0]
        assert "status = ANY" in sql
        assert params[0] == list(tick_mod.RUNNABLE_STATUS)
        assert "paused" not in tick_mod.RUNNABLE_STATUS

    def test_오래_밀린_것부터_집는다(self, harness):
        conn, _ = harness(rows=_rows(1))
        tick_mod.tick(10, 600, dry_run=True)
        sql, _ = conn.sql[0]
        assert "ORDER  BY next_collect_at" in sql
        assert "next_collect_at <= now()" in sql

    def test_상한을_질의에_건다(self, harness):
        conn, _ = harness(rows=_rows(1))
        tick_mod.tick(3, 600, dry_run=True)
        _, params = conn.sql[0]
        assert params[1] == 3

    def test_대상이_없으면_조용히_끝난다(self, harness):
        harness(rows=[])
        assert tick_mod.tick(10, 600) == 0

    def test_dry_run은_실행하지_않는다(self, harness):
        _, state = harness(rows=_rows(3))
        tick_mod.tick(10, 600, dry_run=True)
        assert state["ran"] == []


class TestFailureIsolation:
    def test_한_건이_실패해도_나머지를_돌린다(self, harness):
        _, state = harness(rows=_rows(3), fail={"urn:test:ds1"})
        tick_mod.tick(10, 600)
        # 실패한 ds1 뒤의 ds2도 실행돼야 한다
        assert state["ran"] == ["urn:test:ds0", "urn:test:ds1", "urn:test:ds2"]

    def test_실패해도_틱은_성공으로_끝낸다(self, harness):
        # CronJob이 매번 실패로 뜨면 알림이 무뎌진다
        harness(rows=_rows(2), fail={"urn:test:ds0", "urn:test:ds1"})
        assert tick_mod.tick(10, 600) == 0

    def test_실패해도_잠금을_푼다(self, harness):
        conn, _ = harness(rows=_rows(2), fail={"urn:test:ds0"})
        tick_mod.tick(10, 600)
        assert conn.unlocked == ["urn:test:ds0", "urn:test:ds1"]


class TestConcurrency:
    def test_다른_틱이_잡고_있으면_건너뛴다(self, harness):
        # 겹치면 같은 원천을 두 번 호출해 rate limit에 걸리고 item_count가 꼬인다
        _, state = harness(rows=_rows(3), lock_grants=[True, False, True])
        tick_mod.tick(10, 600)
        assert state["ran"] == ["urn:test:ds0", "urn:test:ds2"]

    def test_건너뛴_건은_잠금해제를_부르지_않는다(self, harness):
        conn, _ = harness(rows=_rows(2), lock_grants=[False, True])
        tick_mod.tick(10, 600)
        assert conn.unlocked == ["urn:test:ds1"]


class TestBudget:
    def test_예산이_0이면_아무것도_집지_않는다(self, harness):
        _, state = harness(rows=_rows(3))
        tick_mod.tick(10, 0)
        assert state["ran"] == []

    def test_진행중인_건은_중간에_끊지_않는다(self, harness, monkeypatch):
        # 파이프라인이 DB·S3를 중간 상태로 남길 수 있어서 예산 초과로 kill하지 않는다
        _, state = harness(rows=_rows(3))
        calls = []

        def _slow(ds, triggered_by=None):
            calls.append(ds)
            tick_mod.time.monotonic = lambda: float("inf")   # 첫 건 도중 예산 소진

        monkeypatch.setattr(tick_mod, "run_dataset", _slow)
        real = tick_mod.time.monotonic
        try:
            tick_mod.tick(10, 600)
        finally:
            tick_mod.time.monotonic = real
        assert calls == ["urn:test:ds0"]     # 첫 건은 끝까지, 다음 건은 안 집음


class TestOperatingSpec:
    def test_규격이_상수로_고정돼_있다(self, harness):
        assert tick_mod.MAX_DATASETS_PER_TICK > 0
        assert tick_mod.TICK_BUDGET_SEC > 0
        assert tick_mod.TZ is not None
        assert "paused" not in tick_mod.RUNNABLE_STATUS

    def test_예산이_크론_주기보다_짧다(self):
        # 1시간 주기 크론에 50분 예산 — 틱이 겹칠 여지를 줄인다.
        # 그래도 겹칠 수 있어서 advisory lock이 따로 있다.
        assert tick_mod.TICK_BUDGET_SEC < 3600
