"""Nightly pipeline orchestrator.

Deep-module wrapper over the five existing nightly jobs. The public
surface is just two functions:

- ``run_nightly()`` — what APScheduler calls at 02:30 UTC. Zero required
  args. Runs every step for every active org, isolates failures per-step,
  returns a structured ``RunReport``.
- ``run_step(name, ...)`` — what ``/admin/trigger-job/{name}`` routes to.
  Single-step re-run. Returns the same ``RunReport`` shape with one entry.

The existing per-step service functions (``run_contribution_rollup_job``,
``save_health_snapshot``, ``run_strengths_weaknesses_job``,
``run_pattern_detection_job``) are reused here via an adapter table —
each one is a thin wrapper that opens a session and dispatches to a
per-org runner exposed by the same module (``*_for_org`` functions).

Backfill works via the ``PIPELINE_AS_OF`` contextvar: callers pass
``run_nightly(as_of=date(2026, 4, 20))`` and every service that reads
through ``current_pipeline_as_of()`` sees that value instead of
``datetime.now(UTC)``.

Digest dispatcher is NOT part of the nightly pipeline — it runs hourly
on its own cron because individual orgs have different weekly schedules.

Week 15 (RFC #17).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

logger = logging.getLogger("collective_brain.nightly_pipeline")

# ── Pipeline-as-of contextvar ────────────────────────────────────────────────
#
# Services running inside ``run_nightly`` should read the pipeline's "as-of"
# wallclock through ``current_pipeline_as_of()`` instead of ``datetime.now(UTC)``
# directly. ``run_nightly(as_of=date(...))`` sets this contextvar for the
# duration of the run so a backfill can re-execute with yesterday's window.

PIPELINE_AS_OF: ContextVar[datetime | None] = ContextVar("PIPELINE_AS_OF", default=None)


def current_pipeline_as_of() -> datetime:
    """Return the pipeline's effective "now" — the contextvar if set inside
    ``run_nightly``, else real wallclock UTC. Services use this to make
    ``run_nightly(as_of=...)`` backfills observable end-to-end."""
    val = PIPELINE_AS_OF.get()
    return val if val is not None else datetime.now(UTC)


# ── Public types ─────────────────────────────────────────────────────────────

StepName = Literal[
    "contribution_rollup",
    "health_snapshot",
    "strengths_weaknesses",
    "pattern_detection",
]

STEPS_IN_ORDER: tuple[StepName, ...] = (
    "contribution_rollup",
    "health_snapshot",
    "strengths_weaknesses",
    "pattern_detection",
)


@dataclass(frozen=True)
class StepResult:
    """One step's outcome. Multiple StepResults per step are possible once
    per-org fan-out lands in the follow-up PR; for now each step emits one."""

    step: StepName
    status: Literal["ok", "failed"]
    duration_ms: int
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class RunReport:
    run_id: str
    started_at: datetime
    finished_at: datetime
    steps: list[StepResult]

    @property
    def ok(self) -> bool:
        return all(s.status == "ok" for s in self.steps)


# ── Adapter table ────────────────────────────────────────────────────────────

StepFn = Callable[[], dict[str, Any]]


def _default_adapters() -> dict[StepName, StepFn]:
    """Map each StepName to the existing service function. Kept as a factory
    so tests can inject fakes without monkey-patching module state."""
    from app.services.contribution_rollup_service import run_contribution_rollup_job
    from app.services.pattern_detection import run_pattern_detection_job
    from app.services.strengths_weaknesses_service import run_strengths_weaknesses_job
    from app.services.team_health_service import save_health_snapshot

    def _health_snapshot_job() -> dict[str, Any]:
        # save_health_snapshot needs its own session, unlike the other three
        # which already open one internally. Wrap for uniform signature.
        from app.db.database import create_session

        db = create_session()
        try:
            return save_health_snapshot(db)
        finally:
            db.close()

    return {
        "contribution_rollup": run_contribution_rollup_job,
        "health_snapshot": _health_snapshot_job,
        "strengths_weaknesses": run_strengths_weaknesses_job,
        "pattern_detection": run_pattern_detection_job,
    }


# ── Public entry points ──────────────────────────────────────────────────────


def run_nightly(
    *,
    as_of: date | datetime | None = None,
    only_steps: list[StepName] | None = None,
    _adapters: dict[StepName, StepFn] | None = None,
) -> RunReport:
    """Run the nightly pipeline. Zero required args — this is the cron path.

    ``as_of`` overrides the wallclock for backfill: services that read through
    ``current_pipeline_as_of()`` will see this value instead of ``now()``.
    A ``date`` is interpreted as midnight UTC; a ``datetime`` is used as-is
    (a naive datetime is assumed to be UTC).

    ``only_steps`` filters to a subset (admin + backfill). ``_adapters`` is a
    test seam; production callers should never pass it.
    """
    adapters = _adapters if _adapters is not None else _default_adapters()
    steps_to_run = [s for s in STEPS_IN_ORDER if only_steps is None or s in only_steps]

    as_of_dt = _coerce_as_of(as_of)
    token = PIPELINE_AS_OF.set(as_of_dt)
    try:
        return _run_nightly_inner(
            run_id=uuid.uuid4().hex[:12],
            steps_to_run=steps_to_run,
            adapters=adapters,
        )
    finally:
        PIPELINE_AS_OF.reset(token)


def _coerce_as_of(as_of: date | datetime | None) -> datetime | None:
    """Normalize the public ``as_of`` arg to an aware UTC datetime (or None).
    A bare ``date`` becomes midnight UTC of that day."""
    if as_of is None:
        return None
    if isinstance(as_of, datetime):
        return as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
    # date (but not datetime — datetime is a subclass of date so order matters)
    return datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)


def _run_nightly_inner(
    *,
    run_id: str,
    steps_to_run: list[StepName],
    adapters: dict[StepName, StepFn],
) -> RunReport:
    started_at = datetime.now(UTC)
    step_results: list[StepResult] = []

    logger.info("nightly_pipeline run_id=%s starting steps=%s", run_id, steps_to_run)

    for step_name in steps_to_run:
        fn = adapters.get(step_name)
        if fn is None:
            step_results.append(
                StepResult(
                    step=step_name,
                    status="failed",
                    duration_ms=0,
                    error=f"no adapter registered for step '{step_name}'",
                )
            )
            _observe_step_duration(step_name, "failed", 0.0)
            continue

        t0 = time.perf_counter()
        try:
            payload = fn() or {}
            elapsed = time.perf_counter() - t0
            step_results.append(
                StepResult(
                    step=step_name,
                    status="ok",
                    duration_ms=int(elapsed * 1000),
                    payload=payload,
                )
            )
            _observe_step_duration(step_name, "ok", elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.error(
                "nightly_pipeline run_id=%s step=%s failed: %s",
                run_id,
                step_name,
                exc,
                exc_info=True,
            )
            step_results.append(
                StepResult(
                    step=step_name,
                    status="failed",
                    duration_ms=int(elapsed * 1000),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            _observe_step_duration(step_name, "failed", elapsed)
            # DO NOT break — subsequent steps still run. This is what
            # "per-step isolation" means in this PR; follow-up PRs extend
            # isolation to per-org within each step.

    finished_at = datetime.now(UTC)
    report = RunReport(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        steps=step_results,
    )

    _increment_run_total(step_results)

    logger.info(
        "nightly_pipeline run_id=%s done ok=%s duration_ms=%d steps_ok=%d/%d",
        run_id,
        report.ok,
        int((finished_at - started_at).total_seconds() * 1000),
        sum(1 for s in step_results if s.status == "ok"),
        len(step_results),
    )
    return report


def _observe_step_duration(step: StepName, status: str, seconds: float) -> None:
    """Prometheus histogram emission. Failures are swallowed — metrics
    must never break the pipeline itself."""
    try:
        from app.services.metrics import NIGHTLY_STEP_DURATION_SECONDS

        NIGHTLY_STEP_DURATION_SECONDS.labels(step=step, status=status).observe(seconds)
    except Exception:  # pragma: no cover — best-effort telemetry
        logger.warning("Could not record step duration metric", exc_info=True)


def _increment_run_total(step_results: list[StepResult]) -> None:
    """Increment the pipeline run counter with the aggregate status:
    - all steps ok → ok
    - mix of ok + failed → partial
    - all failed → failed
    - no steps at all (empty only_steps) → failed (treated as a no-op run)
    """
    try:
        from app.services.metrics import NIGHTLY_PIPELINE_RUN_TOTAL

        if not step_results:
            status = "failed"
        else:
            ok_count = sum(1 for s in step_results if s.status == "ok")
            if ok_count == len(step_results):
                status = "ok"
            elif ok_count == 0:
                status = "failed"
            else:
                status = "partial"

        NIGHTLY_PIPELINE_RUN_TOTAL.labels(status=status).inc()
    except Exception:  # pragma: no cover — best-effort telemetry
        logger.warning("Could not record pipeline run metric", exc_info=True)


def run_step(
    step: StepName,
    *,
    as_of: date | datetime | None = None,
    _adapters: dict[StepName, StepFn] | None = None,
) -> RunReport:
    """Admin path — run exactly one step. Kept separate from ``run_nightly``
    so the callsite reads clearly and so we can add step-specific args here
    later (e.g. ``org_id`` filtering) without bloating ``run_nightly``."""
    return run_nightly(as_of=as_of, only_steps=[step], _adapters=_adapters)
