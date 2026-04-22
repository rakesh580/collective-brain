"""Background job scheduler wrapping APScheduler.

Thin, test-friendly wrapper around ``AsyncIOScheduler``:

- Jobs are registered by string name with a trigger (cron/interval/date).
- Sync callables are executed in a threadpool; async callables are awaited.
- Every execution emits Prometheus metrics (count, duration, errors).
- Exposes ``run_now(name)`` for admin-triggered manual runs.

Job functions must accept no positional arguments from the scheduler; if
they need a DB session, they should open and close it themselves.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from opentelemetry import trace
from prometheus_client import Counter, Histogram

_tracer = trace.get_tracer("collective_brain.scheduler")

logger = logging.getLogger("collective_brain.scheduler")

_JOB_EXECUTIONS = Counter(
    "cb_job_executions_total",
    "Total scheduler job executions",
    labelnames=("job_name",),
)
_JOB_ERRORS = Counter(
    "cb_job_errors_total",
    "Total scheduler job failures",
    labelnames=("job_name",),
)
_JOB_DURATION = Histogram(
    "cb_job_duration_seconds",
    "Scheduler job duration in seconds",
    labelnames=("job_name",),
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 300, 900),
)


JobFunc = Callable[[], Any] | Callable[[], Awaitable[Any]]


@dataclass
class JobRun:
    run_id: str
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    success: bool = False
    error: str | None = None
    result: Any = None


@dataclass
class JobDef:
    name: str
    func: JobFunc
    trigger: BaseTrigger | None = None
    description: str = ""
    last_run: JobRun | None = field(default=None)


class Scheduler:
    """Registers and runs named background jobs."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._jobs: dict[str, JobDef] = {}
        self._started = False

    def register(
        self,
        name: str,
        func: JobFunc,
        trigger: BaseTrigger | None = None,
        description: str = "",
    ) -> None:
        """Register a job. If a trigger is provided, it runs on that schedule."""
        if name in self._jobs:
            raise ValueError(f"Job '{name}' already registered")
        self._jobs[name] = JobDef(name=name, func=func, trigger=trigger, description=description)

    def list_jobs(self) -> list[dict[str, Any]]:
        out = []
        for job in self._jobs.values():
            out.append(
                {
                    "name": job.name,
                    "description": job.description,
                    "has_trigger": job.trigger is not None,
                    "last_run": _run_to_dict(job.last_run) if job.last_run else None,
                }
            )
        return out

    async def start(self) -> None:
        """Start the underlying APScheduler. Safe to call multiple times."""
        if self._started:
            return
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        for job in self._jobs.values():
            if job.trigger is not None:
                self._scheduler.add_job(
                    self._run_by_name_async,
                    trigger=job.trigger,
                    args=[job.name],
                    id=job.name,
                    name=job.name,
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started with %d scheduled job(s)", len(self._scheduler.get_jobs()))

    async def stop(self) -> None:
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler stopped")

    async def run_now(self, name: str) -> JobRun:
        """Trigger a named job immediately. Returns the completed JobRun."""
        if name not in self._jobs:
            raise KeyError(f"Unknown job '{name}'")
        return await self._execute(self._jobs[name])

    async def _run_by_name_async(self, name: str) -> None:
        """Internal entrypoint used by APScheduler-triggered runs."""
        job = self._jobs.get(name)
        if job is None:
            logger.warning("Scheduled job '%s' no longer registered", name)
            return
        await self._execute(job)

    async def _execute(self, job: JobDef) -> JobRun:
        run = JobRun(
            run_id=str(uuid.uuid4()),
            job_name=job.name,
            started_at=datetime.now(UTC),
        )
        start = time.perf_counter()

        # OTel span so job runs show up in traces alongside HTTP requests.
        # Span status follows success; exceptions are recorded to the span.
        with _tracer.start_as_current_span(
            f"scheduler.job.{job.name}",
            attributes={
                "cb.job.name": job.name,
                "cb.job.run_id": run.run_id,
                "cb.job.trigger_type": type(job.trigger).__name__ if job.trigger else "manual",
            },
        ) as span:
            try:
                if inspect.iscoroutinefunction(job.func):
                    result = await job.func()
                else:
                    # Run sync jobs in a threadpool so blocking DB I/O doesn't
                    # stall the event loop the scheduler is running on.
                    result = await asyncio.to_thread(job.func)
                run.result = result
                run.success = True
                span.set_attribute("cb.job.success", True)
            except Exception as exc:  # pragma: no cover exercised by tests
                run.success = False
                run.error = f"{type(exc).__name__}: {exc}"
                logger.exception("Scheduler job '%s' failed", job.name)
                _JOB_ERRORS.labels(job_name=job.name).inc()
                span.set_attribute("cb.job.success", False)
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            finally:
                duration = time.perf_counter() - start
                run.duration_seconds = duration
                run.finished_at = datetime.now(UTC)
                _JOB_EXECUTIONS.labels(job_name=job.name).inc()
                _JOB_DURATION.labels(job_name=job.name).observe(duration)
                span.set_attribute("cb.job.duration_seconds", duration)
                job.last_run = run
        return run


def _run_to_dict(run: JobRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_seconds": run.duration_seconds,
        "success": run.success,
        "error": run.error,
    }


def run_to_dict(run: JobRun) -> dict[str, Any]:
    """Public helper for routers."""
    return _run_to_dict(run)
