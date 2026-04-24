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
``run_pattern_detection_job``) stay unchanged in this PR — the pipeline
dispatches to them via an adapter table. Follow-up PRs will extract
``run_*_for_org`` helpers from each so per-org isolation + ``as_of``
backfill become real.

Digest dispatcher is NOT part of the nightly pipeline — it runs hourly
on its own cron because individual orgs have different weekly schedules.

Week 15 (RFC #17).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

logger = logging.getLogger("collective_brain.nightly_pipeline")

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
    only_steps: list[StepName] | None = None,
    _adapters: dict[StepName, StepFn] | None = None,
) -> RunReport:
    """Run the nightly pipeline. Zero required args — this is the cron path.

    ``only_steps`` filters to a subset (admin + backfill). ``_adapters`` is a
    test seam; production callers should never pass it.
    """
    adapters = _adapters if _adapters is not None else _default_adapters()
    steps_to_run = [s for s in STEPS_IN_ORDER if only_steps is None or s in only_steps]

    run_id = uuid.uuid4().hex[:12]
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
            continue

        t0 = time.perf_counter()
        try:
            payload = fn() or {}
            step_results.append(
                StepResult(
                    step=step_name,
                    status="ok",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    payload=payload,
                )
            )
        except Exception as exc:
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
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
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

    logger.info(
        "nightly_pipeline run_id=%s done ok=%s duration_ms=%d steps_ok=%d/%d",
        run_id,
        report.ok,
        int((finished_at - started_at).total_seconds() * 1000),
        sum(1 for s in step_results if s.status == "ok"),
        len(step_results),
    )
    return report


def run_step(
    step: StepName,
    *,
    _adapters: dict[StepName, StepFn] | None = None,
) -> RunReport:
    """Admin path — run exactly one step. Kept separate from ``run_nightly``
    so the callsite reads clearly and so we can add step-specific args here
    later (e.g. ``org_id`` filtering) without bloating ``run_nightly``."""
    return run_nightly(only_steps=[step], _adapters=_adapters)
