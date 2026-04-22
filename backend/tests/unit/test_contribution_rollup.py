"""Unit tests for the per-member contribution rollup service."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.contribution_rollup_service import (
    _member_window_stats,
    _upsert_rollup,
    compute_and_save_rollups,
)


def _contrib(
    ts: datetime,
    topics: list[str] | None = None,
    ctype: str = "git_commit",
    artifact_id: str = "art-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=ts,
        topics=topics or [],
        contribution_type=ctype,
        artifact_id=artifact_id,
    )


def _db_with_contribs(contribs: list) -> MagicMock:
    db = MagicMock()
    query_chain = MagicMock()
    query_chain.filter.return_value = query_chain
    query_chain.all.return_value = contribs
    db.query.return_value = query_chain
    return db


class TestMemberWindowStats:
    def test_counts_contributions_in_window(self):
        now = datetime(2026, 4, 22, tzinfo=UTC)
        contribs = [
            _contrib(now - timedelta(days=1), topics=["api"], artifact_id="a"),
            _contrib(now - timedelta(days=3), topics=["api", "docs"], artifact_id="a"),
            _contrib(now - timedelta(days=5), topics=["docs"], artifact_id="b"),
        ]
        db = _db_with_contribs(contribs)

        stats = _member_window_stats(db, "alice", 7, now)

        assert stats["contributions_count"] == 3
        assert stats["artifacts_touched"] == 2  # a, b
        assert stats["distinct_topics"] == 2  # api, docs
        assert stats["top_topic"] in ("api", "docs")
        assert stats["type_histogram"] == {"git_commit": 3}
        assert stats["last_activity_at"] == now - timedelta(days=1)

    def test_empty_window_returns_zeros(self):
        db = _db_with_contribs([])
        stats = _member_window_stats(db, "alice", 7, datetime.now(UTC))
        assert stats["contributions_count"] == 0
        assert stats["artifacts_touched"] == 0
        assert stats["distinct_topics"] == 0
        assert stats["top_topic"] is None
        assert stats["last_activity_at"] is None

    def test_topic_histogram_capped_at_10(self):
        now = datetime(2026, 4, 22, tzinfo=UTC)
        contribs = [_contrib(now - timedelta(days=1), topics=[f"t{i}"]) for i in range(15)]
        db = _db_with_contribs(contribs)

        stats = _member_window_stats(db, "alice", 7, now)

        assert len(stats["topic_histogram"]) == 10
        assert stats["distinct_topics"] == 15


class TestUpsertRollup:
    def test_creates_new_row_when_absent(self):
        db = MagicMock()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.first.return_value = None
        db.query.return_value = query_chain

        member = SimpleNamespace(id="alice", organization_id="org-1")
        stats = {
            "contributions_count": 5,
            "artifacts_touched": 2,
            "distinct_topics": 3,
            "topic_histogram": {"api": 3, "docs": 2},
            "top_topic": "api",
            "type_histogram": {"git_commit": 5},
            "last_activity_at": datetime(2026, 4, 22, tzinfo=UTC),
        }

        rollup = _upsert_rollup(
            db,
            member=member,
            window_days=7,
            computed_at=datetime(2026, 4, 22, 2, 30, tzinfo=UTC),
            stats=stats,
        )

        assert rollup.contributions_count == 5
        assert rollup.top_topic == "api"
        assert rollup.window_days == 7
        assert rollup.organization_id == "org-1"
        db.add.assert_called_once()

    def test_overwrites_same_day_run(self):
        existing = MagicMock()
        db = MagicMock()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.first.return_value = existing
        db.query.return_value = query_chain

        member = SimpleNamespace(id="alice", organization_id="org-1")
        new_stats = {
            "contributions_count": 9,
            "artifacts_touched": 4,
            "distinct_topics": 2,
            "topic_histogram": {"api": 9},
            "top_topic": "api",
            "type_histogram": {"git_commit": 9},
            "last_activity_at": None,
        }

        result = _upsert_rollup(
            db,
            member=member,
            window_days=7,
            computed_at=datetime(2026, 4, 22, 14, 0, tzinfo=UTC),
            stats=new_stats,
        )

        assert result is existing
        assert existing.contributions_count == 9
        db.add.assert_not_called()


class TestComputeAndSaveRollups:
    def test_skips_inactive_members_on_largest_window(self, monkeypatch):
        """Members with zero activity in 30d should not get a rollup row."""
        now = datetime(2026, 4, 22, tzinfo=UTC)

        active = SimpleNamespace(id="alice", organization_id="org-1")
        silent = SimpleNamespace(id="bob", organization_id="org-1")

        # Monkeypatch the stats helper — deterministic behavior per (member, window).
        from app.services import contribution_rollup_service as svc

        calls: list[tuple[str, int]] = []

        def fake_stats(db, member_id, window_days, now_):
            calls.append((member_id, window_days))
            if member_id == "alice":
                return {
                    "contributions_count": 3 if window_days == 7 else 10,
                    "artifacts_touched": 2,
                    "distinct_topics": 2,
                    "topic_histogram": {"api": 3},
                    "top_topic": "api",
                    "type_histogram": {"git_commit": 3},
                    "last_activity_at": now - timedelta(days=1),
                }
            return {
                "contributions_count": 0,
                "artifacts_touched": 0,
                "distinct_topics": 0,
                "topic_histogram": {},
                "top_topic": None,
                "type_histogram": {},
                "last_activity_at": None,
            }

        monkeypatch.setattr(svc, "_member_window_stats", fake_stats)

        # Rollup upsert is a noop against the mock DB.
        db = MagicMock()

        def query_router(model):
            q = MagicMock()
            name = getattr(model, "__name__", "")
            if name == "MemberRecord":
                q.all.return_value = [active, silent]
                return q
            # ContributionRollup lookup — always "not found" so _upsert_rollup inserts.
            q.filter.return_value = q
            q.first.return_value = None
            return q

        db.query.side_effect = query_router

        summary = compute_and_save_rollups(db, windows=(7, 30), now=now)

        assert summary["members_processed"] == 2
        # alice: 7d + 30d = 2. bob: 7d only (30d has zero → skipped).
        assert summary["rows_written"] == 3
        assert calls == [("alice", 7), ("alice", 30), ("bob", 7), ("bob", 30)]
        db.commit.assert_called_once()

    def test_empty_member_list_is_a_noop(self):
        db = MagicMock()

        def query_router(model):
            q = MagicMock()
            name = getattr(model, "__name__", "")
            if name == "MemberRecord":
                q.all.return_value = []
            return q

        db.query.side_effect = query_router

        summary = compute_and_save_rollups(db, now=datetime.now(UTC))

        assert summary["members_processed"] == 0
        assert summary["rows_written"] == 0
