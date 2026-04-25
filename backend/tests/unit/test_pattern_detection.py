"""Unit tests for the nightly pattern-detection service.

Each detector gets a synthetic DB mock — we assert the signal fires when the
plan's conditions are met and does not fire when they aren't. The upsert
orchestrator also gets its own smoke test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.pattern_detection import (
    _upsert_signal,
    detect_friday_land,
    detect_load_skew,
    detect_review_bottlenecks,
    detect_silent_areas,
    detect_slow_lanes,
    run_pattern_detection,
)

NOW = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)


def _work_item(
    *,
    id: str,
    topics: list[str] | None = None,
    state: str = "merged",
    cycle_time_hours: float | None = None,
    completed_at: datetime | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    source: str = "github_pr",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        topics=topics or [],
        state=state,
        cycle_time_hours=cycle_time_hours,
        completed_at=completed_at,
        created_at=created_at or NOW - timedelta(days=2),
        started_at=started_at,
        source=source,
    )


def _contrib(
    *,
    member_id: str,
    topics: list[str],
    timestamp: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        member_id=member_id,
        topics=topics,
        timestamp=timestamp,
        contribution_type="git_commit",
        artifact_id="art",
    )


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


def _db_with(**by_model) -> MagicMock:
    db = MagicMock()
    db.added: list = []

    def router(model):
        name = getattr(model, "__name__", str(model))
        # SQLAlchemy sometimes passes columns (e.g. Signal.id) — fall back to empty.
        if not hasattr(model, "__tablename__"):
            return _Query(by_model.get("_cols", []))
        return _Query(by_model.get(name, []))

    db.query.side_effect = router
    db.add.side_effect = lambda r: db.added.append(r)
    db.commit = MagicMock()
    return db


class TestSlowLanes:
    def test_fires_when_topic_p50_exceeds_threshold(self):
        items = [
            _work_item(id=f"api-{i}", topics=["api"], cycle_time_hours=20, completed_at=NOW - timedelta(days=3))
            for i in range(3)
        ]
        items += [
            _work_item(id=f"docs-{i}", topics=["docs"], cycle_time_hours=4, completed_at=NOW - timedelta(days=3))
            for i in range(3)
        ]
        items += [
            _work_item(id=f"ui-{i}", topics=["ui"], cycle_time_hours=5, completed_at=NOW - timedelta(days=3))
            for i in range(3)
        ]

        db = _db_with(WorkItem=items)
        signals = detect_slow_lanes(db, "org-1", NOW)

        assert len(signals) == 1
        assert signals[0].dedup_key == "slow_lane:api"
        assert signals[0].severity in ("medium", "high")
        assert signals[0].evidence["sample_size"] == 3
        assert "api" in signals[0].title

    def test_does_not_fire_when_all_topics_fast(self):
        items = [
            _work_item(id=f"x-{i}", topics=["x"], cycle_time_hours=5, completed_at=NOW - timedelta(days=1))
            for i in range(5)
        ]
        db = _db_with(WorkItem=items)
        assert detect_slow_lanes(db, "org-1", NOW) == []

    def test_does_not_fire_when_topic_has_too_few_items(self):
        # Team median 5h; one very slow item but only 1 in the topic → ignored.
        items = [_work_item(id="slow", topics=["api"], cycle_time_hours=40, completed_at=NOW - timedelta(days=1))]
        items += [
            _work_item(id=f"fast-{i}", topics=["ui"], cycle_time_hours=5, completed_at=NOW - timedelta(days=1))
            for i in range(4)
        ]
        db = _db_with(WorkItem=items)
        assert detect_slow_lanes(db, "org-1", NOW) == []


class TestSilentAreas:
    def test_fires_for_topic_with_zero_recent(self):
        prior = [
            _contrib(member_id="alice", topics=["legacy-auth"], timestamp=NOW - timedelta(days=40)) for _ in range(12)
        ]
        # Active topic — should not fire.
        prior += [_contrib(member_id="bob", topics=["billing"], timestamp=NOW - timedelta(days=30)) for _ in range(12)]
        recent = [_contrib(member_id="bob", topics=["billing"], timestamp=NOW - timedelta(days=3))]

        db = _db_with(ContributionRecord=prior + recent)
        signals = detect_silent_areas(db, "org-1", NOW)

        keys = [s.dedup_key for s in signals]
        assert "silent_area:legacy-auth" in keys
        assert "silent_area:billing" not in keys

    def test_does_not_fire_when_prior_count_low(self):
        prior = [_contrib(member_id="alice", topics=["tiny"], timestamp=NOW - timedelta(days=40)) for _ in range(3)]
        db = _db_with(ContributionRecord=prior)
        assert detect_silent_areas(db, "org-1", NOW) == []


class TestLoadSkew:
    def test_fires_when_one_owner_dominates(self):
        # alice does 8 / 10 contribs to "payments"; 3 total contributors.
        c = []
        for _ in range(8):
            c.append(_contrib(member_id="alice", topics=["payments"], timestamp=NOW - timedelta(days=10)))
        c.append(_contrib(member_id="bob", topics=["payments"], timestamp=NOW - timedelta(days=10)))
        c.append(_contrib(member_id="carol", topics=["payments"], timestamp=NOW - timedelta(days=10)))

        db = _db_with(ContributionRecord=c)
        signals = detect_load_skew(db, "org-1", NOW)
        assert len(signals) == 1
        assert signals[0].dedup_key == "load_skew:payments"
        assert signals[0].evidence["top_contributor_id"] == "alice"
        assert signals[0].evidence["top_contributor_share"] >= 0.6

    def test_does_not_fire_below_min_contributors(self):
        # Only 2 contributors → skip even if skewed.
        c = [_contrib(member_id="alice", topics=["tiny"], timestamp=NOW - timedelta(days=5)) for _ in range(9)]
        c.append(_contrib(member_id="bob", topics=["tiny"], timestamp=NOW - timedelta(days=5)))
        db = _db_with(ContributionRecord=c)
        assert detect_load_skew(db, "org-1", NOW) == []

    def test_does_not_fire_when_balanced(self):
        c = []
        for m in ("alice", "bob", "carol"):
            for _ in range(4):
                c.append(_contrib(member_id=m, topics=["fair"], timestamp=NOW - timedelta(days=5)))
        db = _db_with(ContributionRecord=c)
        assert detect_load_skew(db, "org-1", NOW) == []


class TestFridayLand:
    def test_fires_when_friday_p50_significantly_higher(self):
        # Friday = weekday 4. April 17 2026 is Friday.
        friday = datetime(2026, 4, 17, 18, 0, tzinfo=UTC)
        monday = datetime(2026, 4, 13, 18, 0, tzinfo=UTC)
        items = []
        for _ in range(6):
            items.append(_work_item(id=f"fri-{_}", topics=["x"], cycle_time_hours=30, completed_at=friday))
        for _ in range(6):
            items.append(_work_item(id=f"mon-{_}", topics=["x"], cycle_time_hours=10, completed_at=monday))

        db = _db_with(WorkItem=items)
        signals = detect_friday_land(db, "org-1", NOW)
        assert len(signals) == 1
        assert signals[0].dedup_key == "friday_land"
        assert signals[0].evidence["ratio"] >= 1.5

    def test_does_not_fire_when_sample_too_small(self):
        items = [_work_item(id="f", cycle_time_hours=30, completed_at=datetime(2026, 4, 17, tzinfo=UTC))]
        db = _db_with(WorkItem=items)
        assert detect_friday_land(db, "org-1", NOW) == []


class TestReviewBottlenecks:
    def test_fires_when_many_slow_or_stuck(self):
        items = []
        # 4 PRs where first review came after 30h
        for i in range(4):
            c = NOW - timedelta(days=3)
            items.append(
                _work_item(
                    id=f"slow-{i}",
                    source="github_pr",
                    created_at=c,
                    started_at=c + timedelta(hours=30),
                    state="in_progress",
                )
            )
        db = _db_with(WorkItem=items)
        signals = detect_review_bottlenecks(db, "org-1", NOW)
        assert len(signals) == 1
        assert signals[0].dedup_key == "review_bottleneck"
        assert signals[0].evidence["slow_reviewed_count"] == 4

    def test_counts_open_stuck_prs(self):
        items = [
            _work_item(
                id=f"stuck-{i}",
                source="github_pr",
                created_at=NOW - timedelta(days=2),
                started_at=None,
                state="open",
            )
            for i in range(5)
        ]
        db = _db_with(WorkItem=items)
        signals = detect_review_bottlenecks(db, "org-1", NOW)
        assert signals[0].evidence["stuck_open_count"] == 5

    def test_does_not_fire_with_healthy_reviews(self):
        items = [
            _work_item(
                id=f"ok-{i}",
                source="github_pr",
                created_at=NOW - timedelta(hours=4),
                started_at=NOW - timedelta(hours=2),
                state="in_progress",
            )
            for i in range(5)
        ]
        db = _db_with(WorkItem=items)
        assert detect_review_bottlenecks(db, "org-1", NOW) == []


class TestUpsert:
    def test_creates_new_row(self):
        from app.services.pattern_detection import PendingSignal

        pending = PendingSignal(
            signal_type="slow_lane",
            severity="high",
            title="test",
            description="",
            evidence={},
            suggested_action="do it",
            dedup_key="slow_lane:foo",
            organization_id="org-1",
            detected_at=NOW,
        )
        db = _db_with(Signal=[])
        _upsert_signal(db, pending)
        assert len(db.added) == 1
        added = db.added[0]
        assert added.signal_type == "slow_lane"
        assert added.dedup_key == "slow_lane:foo"

    def test_updates_existing_open_row(self):
        from app.services.pattern_detection import PendingSignal

        existing = MagicMock()
        existing.severity = "low"
        existing.title = "old"
        existing.resolved_at = None
        db = _db_with(Signal=[existing])

        pending = PendingSignal(
            signal_type="slow_lane",
            severity="high",
            title="updated",
            description="d2",
            evidence={"x": 1},
            suggested_action="act",
            dedup_key="slow_lane:foo",
            organization_id="org-1",
            detected_at=NOW,
        )
        _upsert_signal(db, pending)

        assert existing.severity == "high"
        assert existing.title == "updated"
        assert existing.detected_at == NOW
        assert db.add.call_count == 0


class TestOrchestrator:
    def test_run_pattern_detection_handles_no_orgs(self, monkeypatch):
        """Runs once in 'global' mode when the org table is empty."""
        from app.services import pattern_detection as pd

        calls: list[str | None] = []

        def fake_detector(db, org_id, now, **kwargs):
            calls.append(org_id)
            return []

        monkeypatch.setattr(pd, "DETECTORS", [fake_detector])
        db = _db_with(OrganizationRecord=[], Signal=[])
        summary = run_pattern_detection(db, now=NOW)

        assert summary["orgs_scanned"] == 1
        assert calls == [None]

    def test_run_pattern_detection_iterates_all_orgs(self, monkeypatch):
        from app.services import pattern_detection as pd

        calls: list[str | None] = []

        def fake_detector(db, org_id, now, **kwargs):
            calls.append(org_id)
            return []

        monkeypatch.setattr(pd, "DETECTORS", [fake_detector])
        orgs = [
            SimpleNamespace(id="org-a", is_active=True),
            SimpleNamespace(id="org-b", is_active=True),
        ]
        db = _db_with(OrganizationRecord=orgs, Signal=[])
        run_pattern_detection(db, now=NOW)
        assert calls == ["org-a", "org-b"]

    def test_run_pattern_detection_for_org_runs_only_target_org(self, monkeypatch):
        """Per-org runner introduced in RFC #17 sequencing step 2. The
        orchestrator's per-org loop (follow-up work) calls this so a
        detector raising for org A cannot block detection for org B."""
        from app.services import pattern_detection as pd

        calls: list[str | None] = []

        def fake_detector(db, org_id, now, **kwargs):
            calls.append(org_id)
            return []

        monkeypatch.setattr(pd, "DETECTORS", [fake_detector])
        db = _db_with(Signal=[])

        summary = pd.run_pattern_detection_for_org(db, "org-a", now=NOW)

        assert calls == ["org-a"]
        assert summary["organization_id"] == "org-a"
        assert summary["signals_created"] == 0
        assert summary["signals_updated"] == 0


@pytest.mark.parametrize(
    "detector",
    [
        detect_slow_lanes,
        detect_silent_areas,
        detect_load_skew,
        detect_friday_land,
        detect_review_bottlenecks,
    ],
)
def test_all_detectors_return_empty_on_empty_db(detector):
    """Every detector must gracefully return [] when there is nothing to scan."""
    db = _db_with(WorkItem=[], ContributionRecord=[])
    assert detector(db, "org-1", NOW) == []
