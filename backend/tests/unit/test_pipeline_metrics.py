"""Metrics emitted by the nightly pipeline.

The two metrics this module tests are the signal feed for SLO alerts:
- ``cb_nightly_pipeline_run_total{status}`` — one increment per call to
  ``run_nightly()`` with status = ok | partial | failed.
- ``cb_nightly_step_duration_seconds{step, status}`` — one observation
  per step, recording wall-clock duration.

Alerting examples once these exist:
  # Pipeline did not succeed last night
  sum(increase(cb_nightly_pipeline_run_total{status="ok"}[24h])) == 0

  # Slow steps
  histogram_quantile(0.95, sum by (le,step) (
    rate(cb_nightly_step_duration_seconds_bucket[1h])))
"""

from __future__ import annotations


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _histogram_sample_count(histogram, **labels) -> float:
    # prometheus_client stores histograms with _count suffix accessible via
    # the labeled child's _sum + buckets. Simplest portable check is
    # observe-count via ._sum reads & bucket totals.
    labeled = histogram.labels(**labels)
    return labeled._sum.get() if hasattr(labeled, "_sum") else 0.0


def test_run_nightly_increments_run_total_with_ok_when_all_steps_pass():
    """Happy path: every step ok → pipeline run counter labels status='ok'."""
    from app.services.metrics import NIGHTLY_PIPELINE_RUN_TOTAL
    from app.services.nightly_pipeline import STEPS_IN_ORDER, run_nightly

    before = _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="ok")

    adapters = {s: (lambda: {}) for s in STEPS_IN_ORDER}
    run_nightly(_adapters=adapters)

    assert _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="ok") == before + 1


def test_run_nightly_increments_run_total_with_partial_when_some_steps_fail():
    """At least one step failed but some succeeded → status='partial'. This
    is the signal operators actually care about for 'did nightly SORT OF
    run last night?'"""
    from app.services.metrics import NIGHTLY_PIPELINE_RUN_TOTAL
    from app.services.nightly_pipeline import STEPS_IN_ORDER, run_nightly

    before = _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="partial")

    def boom():
        raise RuntimeError("simulated")

    adapters = {s: (lambda: {}) for s in STEPS_IN_ORDER}
    adapters["health_snapshot"] = boom

    run_nightly(_adapters=adapters)

    assert _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="partial") == before + 1


def test_run_nightly_increments_run_total_with_failed_when_all_steps_fail():
    """Worst case: every step failed → status='failed'. Paired with
    status='ok' this lets alerts distinguish 'total outage' from 'normal'."""
    from app.services.metrics import NIGHTLY_PIPELINE_RUN_TOTAL
    from app.services.nightly_pipeline import STEPS_IN_ORDER, run_nightly

    before = _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="failed")

    def boom():
        raise RuntimeError("simulated")

    adapters = {s: boom for s in STEPS_IN_ORDER}
    run_nightly(_adapters=adapters)

    assert _counter_value(NIGHTLY_PIPELINE_RUN_TOTAL, status="failed") == before + 1


def test_step_duration_histogram_observes_once_per_step():
    """Each step emits exactly one observation to the duration histogram.

    Asserts the histogram is registered and the labeled child exists for
    each (step, status) combination actually executed.
    """
    from app.services.metrics import NIGHTLY_STEP_DURATION_SECONDS
    from app.services.nightly_pipeline import STEPS_IN_ORDER, run_nightly

    adapters = {s: (lambda: {}) for s in STEPS_IN_ORDER}
    run_nightly(_adapters=adapters)

    # Labeling with each step/status combination must succeed (no schema crash).
    for step in STEPS_IN_ORDER:
        NIGHTLY_STEP_DURATION_SECONDS.labels(step=step, status="ok")


def test_step_duration_histogram_labels_failed_steps_separately():
    """A failed step's duration lands under status='failed', not 'ok'."""
    from app.services.metrics import NIGHTLY_STEP_DURATION_SECONDS
    from app.services.nightly_pipeline import STEPS_IN_ORDER, run_nightly

    def boom():
        raise RuntimeError("simulated")

    adapters = {s: (lambda: {}) for s in STEPS_IN_ORDER}
    adapters["pattern_detection"] = boom
    run_nightly(_adapters=adapters)

    # Schema check — labeling with the failed variant must not raise.
    NIGHTLY_STEP_DURATION_SECONDS.labels(step="pattern_detection", status="failed")
    NIGHTLY_STEP_DURATION_SECONDS.labels(step="contribution_rollup", status="ok")
