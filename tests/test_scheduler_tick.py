"""수집 스케줄러 틱 — 실패 격리·중복 방지·예산 준수.

이 스크립트가 틀리면 드러나는 방식이 고약하다. 한 데이터셋이 실패했을 때
나머지를 안 돌리면 **조용히 수집이 멈추고**, 그 사실은 몇 주 뒤 시계열이
비어 있는 것으로만 드러난다(실제로 2026-11-02에 그렇게 발견됐다).
"""

import importlib

import pytest

tick_mod = importlib.import_module("scripts.scheduler_tick")


class _FakeCursor:
    """SQL 내용으로 응답을 고른다 — 틱이 던지는 질의 종류가 여럿이라(대상·진행 표시·수거)."""

    def __init__(self, conn):
        self.conn = conn
        self._result = []

    def execute(self, sql, params=None):
        c = self.conn
        c.sql.append((sql, params))
        if "pg_try_advisory_lock" in sql:
            self._result = [(c.lock_grants.pop(0) if c.lock_grants else True,)]
        elif "pg_advisory_unlock" in sql:
            c.unlocked.append(params[1])
            self._result = [(True,)]
        elif "data_registry r" in sql and sql.lstrip().startswith("SELECT"):
            self._result = c.rows
        elif "status = 'running' AND ended_at IS NULL" in sql:
            self._result = c.markers
        elif sql.startswith("INSERT INTO dcat_provenance"):
            c.next_prov += 1
            c.marked.append((params[0], c.next_prov))
            self._result = [(c.next_prov,)]
        elif "prov_id > %s" in sql:
            self._result = [(1,)] if params[0] in c.pipeline_recorded else []
        elif sql.startswith("SELECT count(*)"):
            self._result = [(c.prior_interrupts,)]
        else:
            self._result = []

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows=(), lock_grants=None, markers=(), pipeline_recorded=(), prior_interrupts=0):
        self.rows = list(rows)
        self.lock_grants = list(lock_grants or [])
        self.markers = list(markers)
        self.pipeline_recorded = set(pipeline_recorded)
        self.prior_interrupts = prior_interrupts
        self.sql = []
        self.unlocked = []
        self.marked = []
        self.next_prov = 1000
        self.commits = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def writes(self, prefix):
        return [(q, p) for q, p in self.sql if q.startswith(prefix)]


from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)


def _rows(n):
    return [(f"urn:test:ds{i}", NOW - timedelta(days=i + 1), "active", None) for i in range(n)]


@pytest.fixture
def harness(monkeypatch):
    state = {"ran": [], "fail": set()}

    def _run(ds, triggered_by=None):
        state["ran"].append(ds)
        if ds in state["fail"]:
            raise RuntimeError("수집 실패 시뮬레이션")

    def _apply(rows=(), lock_grants=None, fail=(), **kw):
        conn = _FakeConn(rows, lock_grants, **kw)
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

    def test_짧은_것부터_같으면_오래_밀린_것부터_집는다(self, harness):
        # 블로그 1건(53분) 뒤에 수 초짜리 쇼핑 5건이 전부 밀렸다(2026-11-09 시험 가동)
        conn, _ = harness(rows=_rows(1))
        tick_mod.tick(10, 600, dry_run=True)
        sql, params = conn.sql[0]
        assert "ORDER  BY coalesce(est.sec, %s), r.next_collect_at" in sql
        assert "r.next_collect_at <= now()" in sql
        assert "p.status = 'success'" in sql and "LIMIT 5" in sql
        assert params[1] == tick_mod.UNKNOWN_DURATION_SEC

    def test_상한을_질의에_건다(self, harness):
        conn, _ = harness(rows=_rows(1))
        tick_mod.tick(3, 600, dry_run=True)
        _, params = conn.sql[0]
        assert params[2] == 3

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
        # 15분 주기 크론(와이즈넛 계약)에 14분 예산 — 틱이 겹칠 여지를 줄인다.
        # 그래도 겹칠 수 있어서 advisory lock이 따로 있다.
        assert tick_mod.TICK_BUDGET_SEC < 15 * 60

    def test_실패한_데이터셋도_다시_집는다(self):
        """실패 시 next_collect_at을 +1시간으로 잡는다 — error를 빼면 그 재시도가 영영 안 돈다.

        2026-11-09 발견: 주석은 '재시도는 자동'이라 했지만 폴링이 error를 제외해
        일시적 오류 한 번이면 사람이 손댈 때까지 멈췄다.
        """
        assert "error" in tick_mod.RUNNABLE_STATUS


class TestNextCollectInterval:
    """다음 수집 시각 = 종료 시각 + 이 간격. 와이즈넛 자동 실행 계약의 산정 규칙(ADR-008)."""

    def test_갱신_주기를_따른다(self):
        from src.database.dcat import parse_iso8601_duration_to_timedelta as f
        assert f("P1D") == timedelta(days=1) and f("P7D") == timedelta(days=7)

    @pytest.mark.parametrize("missing", [None, ""])
    def test_주기가_없으면_주간이다(self, missing):
        """예전엔 None에서 AttributeError → 그 데이터셋이 수집 성공 직후 error로 떨어졌다."""
        from src.database.dcat import parse_iso8601_duration_to_timedelta as f
        assert f(missing) == timedelta(days=7)

    def test_모르는_형식은_조용히_넘기지_않는다(self):
        from src.database.dcat import parse_iso8601_duration_to_timedelta as f
        with pytest.raises(ValueError):
            f("PT1H")


class TestRunMarker:
    """진행 표시 — 파드가 죽어도 흔적이 남아야 한다(2026-11-11)."""

    def test_실행_전에_진행_표시를_남기고_커밋한다(self, harness, monkeypatch):
        conn, state = harness(rows=_rows(1), pipeline_recorded={"urn:test:ds0"})
        seen = {}

        def _run(ds, triggered_by=None):
            seen["marked"] = list(conn.marked)
            seen["commits"] = conn.commits

        monkeypatch.setattr(tick_mod, "run_dataset", _run)
        tick_mod.tick(10, 600)
        assert seen["marked"] == [("urn:test:ds0", 1001)]
        assert seen["commits"] >= 1        # 파이프라인이 돌기 전에 이미 DB에 있다
        (ins, params), = conn.writes("INSERT INTO dcat_provenance")
        assert "'running'" in ins and params[1] == tick_mod.MARKER_AGENT

    def test_파이프라인이_기록을_남기면_표시를_지운다(self, harness):
        # 계약(ADR-008): 실행당 dcat_provenance 1행
        conn, _ = harness(rows=_rows(1), pipeline_recorded={"urn:test:ds0"})
        tick_mod.tick(10, 600)
        (q, p), = conn.writes("DELETE FROM dcat_provenance")
        assert p == (1001,) and "status = 'running'" in q
        assert not conn.writes("UPDATE dcat_provenance")

    def test_파이프라인_진입_전_예외면_표시를_실패_기록으로_바꾼다(self, harness):
        conn, _ = harness(rows=_rows(1), fail={"urn:test:ds0"})
        tick_mod.tick(10, 600)
        (q, p), = conn.writes("UPDATE dcat_provenance")
        assert p[0] == "failure" and "수집 실패 시뮬레이션" in p[1] and p[2] == 1001
        assert not conn.writes("DELETE FROM dcat_provenance")


class TestReapInterrupted:
    """주인 없는 진행 표시 = 끝나지 못하고 죽은 실행(OOMKilled 등)."""

    MARKER = [(77, "urn:test:killed", NOW - timedelta(hours=2))]

    def _registry_update(self, conn):
        (q, p), = conn.writes("UPDATE data_registry")
        return q, p

    @pytest.mark.parametrize("prior,hours", [(0, 1), (1, 6), (2, 24), (9, 24)])
    def test_실패로_바꾸고_반복될수록_재시도를_늦춘다(self, harness, prior, hours):
        conn, _ = harness(rows=[], markers=self.MARKER, prior_interrupts=prior)
        tick_mod.tick(10, 600)
        (q, p), = conn.writes("UPDATE dcat_provenance")
        assert "status = 'failure'" in q and p == (tick_mod.INTERRUPTED_MSG, 77)
        rq, rp = self._registry_update(conn)
        assert "status = 'error'" in rq and rp == (tick_mod.INTERRUPTED_MSG, hours, "urn:test:killed")
        assert conn.unlocked == ["urn:test:killed"]

    def test_사람이_멈춘_데이터셋은_상태를_건드리지_않는다(self, harness):
        conn, _ = harness(rows=[], markers=self.MARKER)
        tick_mod.tick(10, 600)
        rq, _ = self._registry_update(conn)
        assert "status <> 'paused'" in rq

    def test_잠금이_잡혀_있으면_아직_실행_중이라_수거하지_않는다(self, harness):
        conn, _ = harness(rows=[], markers=self.MARKER, lock_grants=[False])
        tick_mod.tick(10, 600)
        assert not conn.writes("UPDATE") and not conn.writes("DELETE")
        assert conn.unlocked == []

    def test_파이프라인_기록이_있으면_표시만_지운다(self, harness):
        conn, _ = harness(rows=[], markers=self.MARKER, pipeline_recorded={"urn:test:killed"})
        tick_mod.tick(10, 600)
        (_, p), = conn.writes("DELETE FROM dcat_provenance")
        assert p == (77,)
        assert not conn.writes("UPDATE")

    def test_dry_run은_수거하지_않는다(self, harness):
        conn, _ = harness(rows=_rows(1), markers=self.MARKER)
        tick_mod.tick(10, 600, dry_run=True)
        assert not any("status = 'running' AND ended_at IS NULL" in q for q, _ in conn.sql)

    def test_중단_오류는_원인_분류에서_실행_중단으로_보인다(self):
        from src.common.error_kind import classify_error, for_user
        assert classify_error(tick_mod.INTERRUPTED_MSG)["kind"] == "interrupted"
        assert for_user(tick_mod.INTERRUPTED_MSG)["user_action"] is False
