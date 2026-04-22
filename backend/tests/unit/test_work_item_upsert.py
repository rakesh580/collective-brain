"""Unit tests for the WorkItem upsert helpers in github_event_processor."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.github_event_processor import (
    _hours_between,
    _mark_work_item_reviewed,
    _parse_ts,
    _pr_state,
    _upsert_work_item,
)


class TestPrState:
    @pytest.mark.parametrize(
        ("action", "merged", "raw", "expected"),
        [
            ("opened", False, "open", "open"),
            ("reopened", False, "open", "open"),
            ("synchronize", False, "open", "open"),
            ("closed", True, "closed", "merged"),
            ("closed", False, "closed", "closed"),
        ],
    )
    def test_maps_actions(self, action, merged, raw, expected):
        assert _pr_state(action, merged, raw) == expected


class TestParseTs:
    def test_parses_iso_z(self):
        ts = _parse_ts("2026-04-22T12:30:00Z")
        assert ts == datetime(2026, 4, 22, 12, 30, tzinfo=UTC)

    def test_none_on_empty(self):
        assert _parse_ts(None) is None
        assert _parse_ts("") is None

    def test_none_on_garbage(self):
        assert _parse_ts("not a date") is None


class TestHoursBetween:
    def test_simple_delta(self):
        a = datetime(2026, 4, 22, 0, 0, tzinfo=UTC)
        b = datetime(2026, 4, 22, 3, 30, tzinfo=UTC)
        assert _hours_between(a, b) == 3.5

    def test_none_returns_none(self):
        assert _hours_between(None, datetime.now(UTC)) is None
        assert _hours_between(datetime.now(UTC), None) is None

    def test_handles_naive_inputs(self):
        """DB may return naive datetimes — must not crash."""
        a = datetime(2026, 4, 22, 0, 0)
        b = datetime(2026, 4, 22, 1, 0)
        assert _hours_between(a, b) == 1.0


class _FakeQuery:
    """Mimics SQLAlchemy's .filter(...).first() chain for WorkItem lookups."""

    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


def _db_with(existing=None) -> MagicMock:
    db = MagicMock()
    db.query.return_value = _FakeQuery(existing)
    return db


class TestUpsertWorkItem:
    def test_inserts_new_open_item(self):
        db = _db_with(existing=None)
        wi = _upsert_work_item(
            db,
            source="github_pr",
            external_id="42",
            repo="foo/bar",
            title="Add thing",
            state="open",
            author_member_id="alice",
            created_at=datetime(2026, 4, 20, tzinfo=UTC),
            completed_at=None,
            labels=["bug"],
            topics=["api"],
        )
        assert wi.state == "open"
        assert wi.completed_at is None
        assert wi.cycle_time_hours is None
        assert wi.author_member_id == "alice"
        db.add.assert_called_once()

    def test_inserts_terminal_state_computes_cycle_time(self):
        db = _db_with(existing=None)
        created = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
        closed = datetime(2026, 4, 20, 16, 0, tzinfo=UTC)
        wi = _upsert_work_item(
            db,
            source="github_pr",
            external_id="43",
            repo="foo/bar",
            title="Ship feature",
            state="merged",
            author_member_id="alice",
            created_at=created,
            completed_at=closed,
            labels=[],
            topics=[],
        )
        assert wi.state == "merged"
        assert wi.cycle_time_hours == 6.0
        assert wi.completed_at == closed

    def test_updates_existing_open_to_merged(self):
        existing = MagicMock()
        existing.state = "open"
        existing.created_at = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
        existing.completed_at = None
        existing.cycle_time_hours = None
        existing.author_member_id = "alice"
        existing.title = "old title"
        existing.labels = []
        existing.topics = []

        db = _db_with(existing=existing)
        closed = datetime(2026, 4, 20, 12, 30, tzinfo=UTC)
        wi = _upsert_work_item(
            db,
            source="github_pr",
            external_id="44",
            repo="foo/bar",
            title="new title",
            state="merged",
            author_member_id="alice",
            created_at=None,  # new payload may omit — must not wipe
            completed_at=closed,
            labels=["priority"],
            topics=["backend"],
        )
        assert wi is existing
        assert wi.state == "merged"
        assert wi.completed_at == closed
        assert wi.cycle_time_hours == 2.5
        assert wi.title == "new title"
        db.add.assert_not_called()  # Update, not insert.

    def test_reopen_clears_terminal_state(self):
        existing = MagicMock()
        existing.state = "closed"
        existing.created_at = datetime(2026, 4, 20, tzinfo=UTC)
        existing.completed_at = datetime(2026, 4, 21, tzinfo=UTC)
        existing.cycle_time_hours = 24.0
        existing.author_member_id = "alice"
        existing.title = "title"
        existing.labels = []
        existing.topics = []

        db = _db_with(existing=existing)
        _upsert_work_item(
            db,
            source="github_pr",
            external_id="45",
            repo="foo/bar",
            title="title",
            state="open",
            author_member_id="alice",
            created_at=None,
            completed_at=None,
            labels=[],
            topics=[],
        )
        assert existing.state == "open"
        assert existing.completed_at is None
        # cycle_time_hours preserved as historical signal
        assert existing.cycle_time_hours == 24.0

    def test_merged_stays_merged_on_duplicate_webhook(self):
        """Terminal states are not re-set by repeated close/merge deliveries."""
        existing = MagicMock()
        existing.state = "merged"
        existing.created_at = datetime(2026, 4, 20, tzinfo=UTC)
        existing.completed_at = datetime(2026, 4, 20, 6, 0, tzinfo=UTC)
        existing.cycle_time_hours = 6.0
        existing.author_member_id = "alice"
        existing.title = "title"
        existing.labels = []
        existing.topics = []

        db = _db_with(existing=existing)
        _upsert_work_item(
            db,
            source="github_pr",
            external_id="46",
            repo="foo/bar",
            title="title",
            state="merged",
            author_member_id="alice",
            created_at=None,
            completed_at=datetime(2026, 5, 1, tzinfo=UTC),  # later redelivery
            labels=[],
            topics=[],
        )
        # completed_at must not move forward on duplicate
        assert existing.completed_at == datetime(2026, 4, 20, 6, 0, tzinfo=UTC)
        assert existing.cycle_time_hours == 6.0

    def test_backfills_missing_author(self):
        existing = MagicMock()
        existing.state = "open"
        existing.created_at = datetime(2026, 4, 20, tzinfo=UTC)
        existing.completed_at = None
        existing.cycle_time_hours = None
        existing.author_member_id = None
        existing.title = "title"
        existing.labels = []
        existing.topics = []

        db = _db_with(existing=existing)
        _upsert_work_item(
            db,
            source="github_pr",
            external_id="47",
            repo="foo/bar",
            title="title",
            state="open",
            author_member_id="alice",
            created_at=None,
            completed_at=None,
            labels=[],
            topics=[],
        )
        assert existing.author_member_id == "alice"


class TestMarkWorkItemReviewed:
    def test_first_review_flips_state_and_sets_started_at(self):
        wi = MagicMock()
        wi.state = "open"
        wi.started_at = None
        db = _db_with(existing=wi)

        submitted = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
        result = _mark_work_item_reviewed(
            db, repo="foo/bar", pr_external_id="42", review_submitted_at=submitted
        )

        assert result is wi
        assert wi.state == "in_progress"
        assert wi.started_at == submitted

    def test_subsequent_review_keeps_earliest_started_at(self):
        wi = MagicMock()
        wi.state = "in_progress"
        first = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
        wi.started_at = first
        db = _db_with(existing=wi)

        later = datetime(2026, 4, 22, 14, 0, tzinfo=UTC)
        _mark_work_item_reviewed(
            db, repo="foo/bar", pr_external_id="42", review_submitted_at=later
        )
        assert wi.started_at == first  # later review must not overwrite

    def test_earlier_review_backfills(self):
        wi = MagicMock()
        wi.state = "in_progress"
        later = datetime(2026, 4, 22, 14, 0, tzinfo=UTC)
        wi.started_at = later
        db = _db_with(existing=wi)

        earlier = datetime(2026, 4, 22, 10, 0, tzinfo=UTC)
        _mark_work_item_reviewed(
            db, repo="foo/bar", pr_external_id="42", review_submitted_at=earlier
        )
        assert wi.started_at == earlier

    def test_merged_state_preserved(self):
        wi = MagicMock()
        wi.state = "merged"
        wi.started_at = None
        db = _db_with(existing=wi)

        _mark_work_item_reviewed(
            db,
            repo="foo/bar",
            pr_external_id="42",
            review_submitted_at=datetime(2026, 4, 22, tzinfo=UTC),
        )
        # Review after merge (rare but possible) doesn't un-merge.
        assert wi.state == "merged"

    def test_no_workitem_is_noop(self):
        db = _db_with(existing=None)
        result = _mark_work_item_reviewed(
            db,
            repo="foo/bar",
            pr_external_id="999",
            review_submitted_at=datetime(2026, 4, 22, tzinfo=UTC),
        )
        assert result is None

    def test_naive_started_at_handled(self):
        wi = MagicMock()
        wi.state = "in_progress"
        wi.started_at = datetime(2026, 4, 22, 14, 0)  # naive
        db = _db_with(existing=wi)

        earlier = datetime(2026, 4, 22, 10, 0, tzinfo=UTC)
        _mark_work_item_reviewed(
            db, repo="foo/bar", pr_external_id="42", review_submitted_at=earlier
        )
        assert wi.started_at == earlier
