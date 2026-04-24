"""Unit tests for the nightly pipeline orchestrator.

RFC #17: deep-module wrapper over the 5 existing nightly jobs.

Test strategy (this PR — scaffold only):
- Inject fake adapters via ``_adapters`` so no real services run.
- Assert on the ``RunReport`` / ``StepResult`` shape returned — the only
  observable outputs at this layer.
- Per-org fan-out, ``as_of`` contextvar, and telemetry are follow-up PRs;
  nothing in this file asserts on them yet.
"""

from __future__ import annotations

from app.services.nightly_pipeline import (
    STEPS_IN_ORDER,
    RunReport,
    run_nightly,
    run_step,
)


def _ok_adapters() -> dict:
    """All four adapters return a trivial success payload."""
    return {
        "contribution_rollup": lambda: {"rows_written": 42},
        "health_snapshot": lambda: {"health_score": 70.0},
        "strengths_weaknesses": lambda: {"members_updated": 5},
        "pattern_detection": lambda: {"signals_created": 1},
    }


def test_run_nightly_returns_runreport_with_all_steps():
    """Baseline: every step adapter is called once, in declared order."""
    called: list[str] = []

    def tracked(name: str):
        def _fn():
            called.append(name)
            return {}

        return _fn

    adapters = {s: tracked(s) for s in STEPS_IN_ORDER}

    report = run_nightly(_adapters=adapters)

    assert isinstance(report, RunReport)
    assert called == list(STEPS_IN_ORDER), "steps must run in declared order"
    assert len(report.steps) == len(STEPS_IN_ORDER)
    assert all(s.status == "ok" for s in report.steps)
    assert report.ok is True


def test_run_nightly_isolates_per_step_failures():
    """A failing step logs + records 'failed' but subsequent steps still run.

    This is the scaffold-PR isolation guarantee — per-org isolation comes
    in the follow-up PR once run_*_for_org extractions land.
    """

    def boom():
        raise RuntimeError("simulated step failure")

    adapters = _ok_adapters()
    adapters["health_snapshot"] = boom  # Middle step fails.

    report = run_nightly(_adapters=adapters)

    assert len(report.steps) == len(STEPS_IN_ORDER)
    by_name = {s.step: s for s in report.steps}
    assert by_name["contribution_rollup"].status == "ok"
    assert by_name["health_snapshot"].status == "failed"
    assert "RuntimeError" in by_name["health_snapshot"].error
    assert "simulated step failure" in by_name["health_snapshot"].error
    # Key assertion: subsequent steps still ran.
    assert by_name["strengths_weaknesses"].status == "ok"
    assert by_name["pattern_detection"].status == "ok"
    # Report overall is NOT ok when any step failed.
    assert report.ok is False


def test_run_nightly_records_duration_per_step():
    """Every StepResult carries a non-negative millisecond duration.
    Needed downstream for SLO histograms and timeout alerts."""
    report = run_nightly(_adapters=_ok_adapters())

    assert all(isinstance(s.duration_ms, int) for s in report.steps)
    assert all(s.duration_ms >= 0 for s in report.steps)


def test_run_nightly_only_steps_filters_to_subset():
    """``only_steps=[...]`` is the backfill + admin path — run a subset,
    skip the rest, preserve declared order."""
    called: list[str] = []

    def tracked(name: str):
        def _fn():
            called.append(name)
            return {}

        return _fn

    adapters = {s: tracked(s) for s in STEPS_IN_ORDER}

    report = run_nightly(
        only_steps=["contribution_rollup", "pattern_detection"],
        _adapters=adapters,
    )

    assert called == ["contribution_rollup", "pattern_detection"]
    assert [s.step for s in report.steps] == ["contribution_rollup", "pattern_detection"]
    # Order within only_steps still follows STEPS_IN_ORDER, not the user's
    # list ordering — callers who swap the order get the canonical sequence.


def test_run_step_produces_single_entry_report():
    """Admin path. ``run_step("pattern_detection")`` yields a one-entry
    report tied to that step only."""
    called: list[str] = []

    def tracked(name: str):
        def _fn():
            called.append(name)
            return {"marker": name}

        return _fn

    adapters = {s: tracked(s) for s in STEPS_IN_ORDER}

    report = run_step("pattern_detection", _adapters=adapters)

    assert called == ["pattern_detection"]
    assert len(report.steps) == 1
    assert report.steps[0].step == "pattern_detection"
    assert report.steps[0].status == "ok"
    assert report.steps[0].payload == {"marker": "pattern_detection"}


def test_missing_adapter_produces_failed_stepresult_not_crash():
    """If an adapter table is incomplete (someone shipped a bad deploy),
    surface it as a step failure rather than KeyError-ing the whole run."""
    # Deliberately leave one adapter out.
    partial = {s: (lambda: {}) for s in STEPS_IN_ORDER if s != "pattern_detection"}

    report = run_nightly(_adapters=partial)

    pd = next(s for s in report.steps if s.step == "pattern_detection")
    assert pd.status == "failed"
    assert "no adapter registered" in (pd.error or "")
    # The other steps still completed.
    ok_names = [s.step for s in report.steps if s.status == "ok"]
    assert set(ok_names) == {"contribution_rollup", "health_snapshot", "strengths_weaknesses"}


def test_stepresult_payload_carries_service_return_value():
    """Callers can read each service's return dict from the StepResult —
    enables the admin UI to show 'rows_written: 42' per step."""
    adapters = _ok_adapters()
    report = run_nightly(_adapters=adapters)

    by_name = {s.step: s for s in report.steps}
    assert by_name["contribution_rollup"].payload == {"rows_written": 42}
    assert by_name["pattern_detection"].payload == {"signals_created": 1}


def test_report_timestamps_are_monotonic():
    """finished_at >= started_at — sanity check no wallclock misuse."""
    report = run_nightly(_adapters=_ok_adapters())
    assert report.finished_at >= report.started_at


def test_report_runid_is_stable_per_call_but_unique_across_calls():
    """Each run gets its own ID so structured logs can filter by run."""
    r1 = run_nightly(_adapters=_ok_adapters())
    r2 = run_nightly(_adapters=_ok_adapters())
    assert r1.run_id != r2.run_id
    assert len(r1.run_id) == 12  # 12-char hex from uuid4().hex[:12]


# ── Admin endpoint routing ───────────────────────────────────────────────────


def test_admin_trigger_job_routes_pipeline_step_to_run_step(monkeypatch):
    """POST /admin/trigger-job/pattern_detection (or any step name) must
    invoke nightly_pipeline.run_step, NOT the scheduler. Ensures removing
    the 4 individual scheduler.register calls didn't break admin re-runs."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.routers.admin import trigger_job

    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    # Scheduler must NOT be called for pipeline step names.
    scheduler = MagicMock()
    request = MagicMock()
    request.app.state.scheduler = scheduler

    called = {"step": None}

    def fake_run_step(step, **kwargs):
        called["step"] = step
        return SimpleNamespace(
            run_id="abc123",
            steps=[
                SimpleNamespace(
                    status="ok",
                    duration_ms=10,
                    payload={"rows_written": 1},
                    error=None,
                )
            ],
        )

    monkeypatch.setattr("app.services.nightly_pipeline.run_step", fake_run_step)

    result = asyncio.run(trigger_job(request=request, job_name="pattern_detection"))

    assert called["step"] == "pattern_detection"
    assert result["status"] == "ok"
    assert result["pipeline_step"] == "pattern_detection"
    assert result["run_id"] == "abc123"
    assert result["step"]["status"] == "ok"
    scheduler.run_now.assert_not_called()


def test_admin_trigger_job_unknown_name_returns_404(monkeypatch):
    """Neither a pipeline step nor a scheduler job → 404, not 500."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    from app.routers.admin import trigger_job

    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    scheduler = MagicMock()
    scheduler.run_now.side_effect = KeyError("not found")
    request = MagicMock()
    request.app.state.scheduler = scheduler

    try:
        asyncio.run(trigger_job(request=request, job_name="totally_made_up_job"))
        raise AssertionError("should have raised HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 404
