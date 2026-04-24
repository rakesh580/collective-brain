"""Tests for the Week 14 business-outcome Prometheus metrics.

These metrics let operators alert on *outcomes* (no digests sent in 24h,
signal-detection ratio dropped) rather than just process liveness. They
are wired into the write paths of pattern_detection and digest_dispatcher
so the Prometheus counter and the DB audit row always agree.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock


def _counter_value(counter, **labels) -> float:
    """Read the current value of a Prometheus counter with matching labels."""
    return counter.labels(**labels)._value.get()


def test_digests_sent_metric_increments_on_each_log_write(monkeypatch):
    from app.services.digest_dispatcher import _record_log
    from app.services.metrics import DIGESTS_SENT_TOTAL

    before = _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="slack", status="sent")

    db = MagicMock()
    _record_log(
        db,
        organization_id="org-1",
        workspace_id="ws-1",
        channel_id="C123",
        delivery_channel="slack",
        recipient=None,
        status="sent",
        now=datetime.now(UTC),
    )

    after = _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="slack", status="sent")
    assert after == before + 1
    db.add.assert_called_once()


def test_digests_sent_metric_labels_failures_separately():
    """sent vs failed must be distinguishable for alerting."""
    from app.services.digest_dispatcher import _record_log
    from app.services.metrics import DIGESTS_SENT_TOTAL

    before_failed = _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="email", status="failed")
    before_sent = _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="email", status="sent")

    db = MagicMock()
    _record_log(
        db,
        organization_id="org-1",
        workspace_id=None,
        channel_id=None,
        delivery_channel="email",
        recipient="user@example.com",
        status="failed",
        error="SMTP refused",
        now=datetime.now(UTC),
    )

    assert _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="email", status="failed") == before_failed + 1
    # Must NOT have moved the success counter.
    assert _counter_value(DIGESTS_SENT_TOTAL, delivery_channel="email", status="sent") == before_sent


def test_signal_metric_counts_created_vs_updated():
    """A newly-detected signal increments outcome=created; re-detection of
    the same open signal increments outcome=updated."""
    from app.services.metrics import SIGNALS_DETECTED_TOTAL
    from app.services.pattern_detection import PendingSignal, _upsert_signal

    pending = PendingSignal(
        organization_id="org-1",
        signal_type="slow_lane",
        severity="medium",
        title="Slow lane on api",
        description="",
        evidence={"topic": "api"},
        suggested_action=None,
        dedup_key="slow_lane:api:v14test",
        detected_at=datetime.now(UTC),
    )

    before_created = _counter_value(
        SIGNALS_DETECTED_TOTAL,
        signal_type="slow_lane",
        severity="medium",
        outcome="created",
    )
    before_updated = _counter_value(
        SIGNALS_DETECTED_TOTAL,
        signal_type="slow_lane",
        severity="medium",
        outcome="updated",
    )

    # First call: no existing row → creates.
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    _upsert_signal(db, pending)

    assert (
        _counter_value(
            SIGNALS_DETECTED_TOTAL,
            signal_type="slow_lane",
            severity="medium",
            outcome="created",
        )
        == before_created + 1
    )

    # Second call: existing row is returned → updates.
    existing = MagicMock()
    q.first.return_value = existing

    _upsert_signal(db, pending)

    assert (
        _counter_value(
            SIGNALS_DETECTED_TOTAL,
            signal_type="slow_lane",
            severity="medium",
            outcome="updated",
        )
        == before_updated + 1
    )


def test_http_request_duration_histogram_exists():
    """Smoke: the new histogram is registered and labels are correct."""
    from app.services.metrics import HTTP_REQUEST_DURATION

    # .labels() with the correct label set must succeed; mismatched labels raise.
    HTTP_REQUEST_DURATION.labels(method="GET", path_template="/health", status_code="200")
