"""Unit tests for week-over-week deltas in the digest service."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.digest_service import (
    _compute_window_stats,
    _delta,
    _format_delta_suffix,
    format_slack_blocks,
    format_text_digest,
    generate_weekly_digest,
)


def _contrib(
    ts: datetime,
    *,
    member_id: str = "alice",
    topics: list[str] | None = None,
    ctype: str = "git_commit",
    artifact_id: str | None = "art-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=ts,
        member_id=member_id,
        topics=topics or [],
        contribution_type=ctype,
        artifact_id=artifact_id,
        room_id=None,
    )


def _db_for_window(contribs: list[SimpleNamespace]) -> MagicMock:
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = contribs
    db.query.return_value = q
    return db


class TestDelta:
    def test_positive_delta(self):
        d = _delta(50, 40)
        assert d == {"current": 50, "previous": 40, "delta": 10, "pct": 25.0}

    def test_negative_delta(self):
        d = _delta(30, 40)
        assert d == {"current": 30, "previous": 40, "delta": -10, "pct": -25.0}

    def test_flat_delta(self):
        d = _delta(10, 10)
        assert d == {"current": 10, "previous": 10, "delta": 0, "pct": 0.0}

    def test_previous_zero_returns_none_pct(self):
        # Growth from zero has no defined percentage — the suffix renderer
        # turns this into "(N new)" rather than "+∞%".
        d = _delta(5, 0)
        assert d == {"current": 5, "previous": 0, "delta": 5, "pct": None}

    def test_both_zero(self):
        d = _delta(0, 0)
        assert d == {"current": 0, "previous": 0, "delta": 0, "pct": None}


class TestDeltaSuffix:
    def test_both_zero_renders_empty(self):
        assert _format_delta_suffix(_delta(0, 0)) == ""

    def test_new_when_previous_zero(self):
        assert _format_delta_suffix(_delta(5, 0)) == " (5 new)"

    def test_flat(self):
        assert _format_delta_suffix(_delta(10, 10)) == " (flat)"

    def test_positive_uses_up_arrow(self):
        # Renderer emits a ▲ with absolute diff and signed pct.
        suffix = _format_delta_suffix(_delta(50, 40))
        assert "▲" in suffix
        assert "10" in suffix
        assert "+25.0%" in suffix

    def test_negative_uses_down_arrow(self):
        suffix = _format_delta_suffix(_delta(30, 40))
        assert "▼" in suffix
        assert "10" in suffix
        assert "-25.0%" in suffix


class TestComputeWindowStats:
    def test_filters_by_date_and_aggregates(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        week_ago = now - timedelta(days=7)
        rows = [
            _contrib(now - timedelta(days=1), topics=["api"], artifact_id="a"),
            _contrib(now - timedelta(days=3), member_id="bob", topics=["api", "docs"], artifact_id="a"),
            _contrib(now - timedelta(days=6), member_id="alice", topics=["docs"], artifact_id="b"),
        ]
        db = _db_for_window(rows)

        stats = _compute_window_stats(db, start=week_ago, end=now, room_id=None)

        assert stats["contributions"] == 3
        assert stats["active_contributors"] == 2
        assert stats["new_artifacts"] == 2
        assert stats["topic_counts"]["api"] == 2
        assert stats["topic_counts"]["docs"] == 2
        assert stats["member_counts"]["alice"] == 2

    def test_empty_window(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        db = _db_for_window([])
        stats = _compute_window_stats(db, start=now - timedelta(days=7), end=now, room_id=None)
        assert stats["contributions"] == 0
        assert stats["active_contributors"] == 0
        assert stats["topic_counts"] == {}


class TestGenerateWeeklyDigest:
    def test_wow_deltas_are_populated(self, monkeypatch):
        """End-to-end shape — we only care the digest contains delta fields."""
        now = datetime(2026, 4, 23, tzinfo=UTC)

        # Patch datetime inside the service so windowing is deterministic.
        from app.services import digest_service as svc

        class FrozenDT(datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        monkeypatch.setattr(svc, "datetime", FrozenDT)

        # First call = current window; second = prior window.
        current_stats = {
            "contributions": 50,
            "active_contributors": 8,
            "new_artifacts": 5,
            "topic_counts": {"api": 20, "docs": 15, "billing": 3},
            "member_counts": {"alice": 25, "bob": 20},
            "type_counts": {"git_commit": 50},
        }
        prior_stats = {
            "contributions": 40,
            "active_contributors": 6,
            "new_artifacts": 4,
            "topic_counts": {"api": 12, "docs": 18},
            "member_counts": {"alice": 20},
            "type_counts": {"git_commit": 40},
        }

        call_counter = {"n": 0}

        def fake_stats(db, *, start, end, room_id):
            call_counter["n"] += 1
            return current_stats if call_counter["n"] == 1 else prior_stats

        monkeypatch.setattr(svc, "_compute_window_stats", fake_stats)

        # Member query / new-member count / graph all stubbed.
        db = MagicMock()

        def query_router(model):
            q = MagicMock()
            name = getattr(model, "__name__", "")
            q.filter.return_value = q
            q.order_by.return_value = q
            q.all.return_value = [
                SimpleNamespace(id="alice", name="Alice"),
                SimpleNamespace(id="bob", name="Bob"),
            ]
            q.count.return_value = 1  # prior-week new members
            return q

        db.query.side_effect = query_router

        fake_graph = MagicMock()
        fake_graph.get_graph_stats.return_value = {}
        fake_graph.get_expertise_gaps.return_value = {"bus_factor_risks": []}
        with patch("app.services.digest_service.MemoryGraph", return_value=fake_graph):
            digest = generate_weekly_digest(db)

        assert digest["total_contributions"] == 50
        assert digest["contributions_delta"]["delta"] == 10
        assert digest["contributions_delta"]["pct"] == 25.0
        assert digest["active_contributors_delta"]["current"] == 8
        assert digest["active_contributors_delta"]["previous"] == 6
        assert digest["new_members_delta"]["previous"] == 1

        # Top topics should carry prior-week comparison counts.
        topics = {t["topic"]: t for t in digest["top_topics"]}
        assert topics["api"]["previous"] == 12
        assert topics["api"]["delta"] == 8
        assert topics["billing"]["previous"] == 0  # never appeared prior week


class TestRendering:
    def _sample_digest(self) -> dict:
        return {
            "period_start": "2026-04-16T00:00:00+00:00",
            "period_end": "2026-04-23T00:00:00+00:00",
            "prior_period_start": "2026-04-09T00:00:00+00:00",
            "prior_period_end": "2026-04-16T00:00:00+00:00",
            "total_contributions": 50,
            "active_contributors": 8,
            "new_members": [],
            "new_members_count": 2,
            "new_artifacts_count": 5,
            "contributions_delta": _delta(50, 40),
            "active_contributors_delta": _delta(8, 6),
            "new_artifacts_delta": _delta(5, 4),
            "new_members_delta": _delta(2, 0),
            "top_topics": [
                {"topic": "api", "count": 20, "previous": 12, "delta": 8},
                {"topic": "billing", "count": 3, "previous": 0, "delta": 3},
            ],
            "top_contributors": [{"member_id": "alice", "name": "Alice", "count": 25}],
            "contribution_types": {"git_commit": 50},
            "graph_stats": {},
            "bus_factor_risks": [],
            "bus_factor_risk_count": 0,
        }

    def test_text_digest_contains_delta_markers(self):
        text = format_text_digest(self._sample_digest())
        # Global metrics carry the (▲/▼) suffix.
        assert "+25.0%" in text
        # Topics pick up "(+N)" or "(new)" tags — "api" has a +8 delta, "billing"
        # is brand new.
        assert "(+8)" in text
        assert "(new)" in text

    def test_slack_blocks_contain_delta_markers(self):
        blocks = format_slack_blocks(self._sample_digest())
        overview = blocks[1]["text"]["text"]
        assert "▲" in overview
        trending = next(b for b in blocks if "Trending" in b.get("text", {}).get("text", ""))
        text = trending["text"]["text"]
        assert "(▲ 8)" in text
        assert "(new)" in text

    def test_zero_prior_renders_N_new(self):
        digest = self._sample_digest()
        # Force a "from zero" scenario on contributions.
        digest["contributions_delta"] = _delta(50, 0)
        text = format_text_digest(digest)
        assert "(50 new)" in text
