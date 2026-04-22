"""Unit tests for the Scheduler service.

Covers: registration, run_now for sync/async jobs, error handling,
metric label emission, and duplicate registration protection.
"""

import asyncio

import pytest
from apscheduler.triggers.interval import IntervalTrigger

from app.services.scheduler import _JOB_ERRORS, _JOB_EXECUTIONS, Scheduler


class TestRegistration:
    def test_register_new_job(self):
        s = Scheduler()
        s.register("noop", lambda: None, description="does nothing")
        jobs = s.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "noop"
        assert jobs[0]["description"] == "does nothing"
        assert jobs[0]["has_trigger"] is False
        assert jobs[0]["last_run"] is None

    def test_register_with_trigger(self):
        s = Scheduler()
        s.register("tick", lambda: None, trigger=IntervalTrigger(seconds=60))
        jobs = s.list_jobs()
        assert jobs[0]["has_trigger"] is True

    def test_duplicate_registration_rejected(self):
        s = Scheduler()
        s.register("dup", lambda: None)
        with pytest.raises(ValueError, match="already registered"):
            s.register("dup", lambda: None)


class TestRunNow:
    @pytest.mark.asyncio
    async def test_run_sync_job(self):
        s = Scheduler()
        calls: list[int] = []

        def work() -> str:
            calls.append(1)
            return "done"

        s.register("sync_job", work)
        run = await s.run_now("sync_job")

        assert run.success is True
        assert run.result == "done"
        assert run.error is None
        assert run.duration_seconds is not None and run.duration_seconds >= 0
        assert calls == [1]

    @pytest.mark.asyncio
    async def test_run_async_job(self):
        s = Scheduler()

        async def work() -> int:
            await asyncio.sleep(0)
            return 42

        s.register("async_job", work)
        run = await s.run_now("async_job")

        assert run.success is True
        assert run.result == 42

    @pytest.mark.asyncio
    async def test_unknown_job_raises(self):
        s = Scheduler()
        with pytest.raises(KeyError):
            await s.run_now("missing")

    @pytest.mark.asyncio
    async def test_failing_job_recorded(self):
        s = Scheduler()

        def broken():
            raise RuntimeError("nope")

        s.register("break", broken)
        run = await s.run_now("break")

        assert run.success is False
        assert run.error is not None
        assert "RuntimeError" in run.error
        assert "nope" in run.error

    @pytest.mark.asyncio
    async def test_last_run_persists_on_job(self):
        s = Scheduler()
        s.register("tracker", lambda: "x")
        await s.run_now("tracker")

        jobs = s.list_jobs()
        assert jobs[0]["last_run"] is not None
        assert jobs[0]["last_run"]["success"] is True


class TestMetrics:
    @pytest.mark.asyncio
    async def test_execution_counter_increments(self):
        s = Scheduler()
        s.register("counted", lambda: 1)

        before = _JOB_EXECUTIONS.labels(job_name="counted")._value.get()
        await s.run_now("counted")
        after = _JOB_EXECUTIONS.labels(job_name="counted")._value.get()

        assert after - before == 1

    @pytest.mark.asyncio
    async def test_error_counter_on_failure(self):
        s = Scheduler()

        def bad():
            raise ValueError("x")

        s.register("err_job", bad)

        before = _JOB_ERRORS.labels(job_name="err_job")._value.get()
        await s.run_now("err_job")
        after = _JOB_ERRORS.labels(job_name="err_job")._value.get()

        assert after - before == 1


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self):
        s = Scheduler()
        s.register("ping", lambda: None, trigger=IntervalTrigger(hours=24))
        await s.start()
        await s.start()  # should no-op, not raise
        await s.stop()
