"""Unit tests for the nightly strengths/weaknesses analyzer."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.strengths_weaknesses_service import (
    CURRENT_WINDOW_DAYS,
    _member_strengths_and_weaknesses,
    _org_summary,
    compute_and_save_strengths_weaknesses,
)


def _contrib(
    ts: datetime,
    *,
    member_id: str = "alice",
    topics: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=ts,
        member_id=member_id,
        topics=topics or [],
    )


class TestMemberStrengthsWeaknesses:
    def test_strengths_only_when_min_threshold_hit(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        # 4 x api (strong), 2 x docs (below 3-count threshold), nothing prior.
        current = [
            _contrib(now - timedelta(days=1), topics=["api"]),
            _contrib(now - timedelta(days=2), topics=["api"]),
            _contrib(now - timedelta(days=3), topics=["api"]),
            _contrib(now - timedelta(days=4), topics=["api"]),
            _contrib(now - timedelta(days=5), topics=["docs"]),
            _contrib(now - timedelta(days=6), topics=["docs"]),
        ]
        strengths, weaknesses = _member_strengths_and_weaknesses(current, [])
        assert strengths == [{"topic": "api", "count": 4}]
        assert weaknesses == []

    def test_weakness_detected_when_prior_active_but_current_zero(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        # Prior window had 5 x auth, current window has none.
        prior = [_contrib(now - timedelta(days=40 + i), topics=["auth"]) for i in range(5)]
        strengths, weaknesses = _member_strengths_and_weaknesses([], prior)
        assert strengths == []
        assert weaknesses == [{"topic": "auth", "prior_count": 5, "current_count": 0}]

    def test_topic_active_both_windows_is_not_a_weakness(self):
        """Even one current-window contribution means the topic is still warm."""
        now = datetime(2026, 4, 23, tzinfo=UTC)
        current = [_contrib(now - timedelta(days=1), topics=["auth"])]
        prior = [_contrib(now - timedelta(days=40), topics=["auth"]) for _ in range(5)]
        strengths, weaknesses = _member_strengths_and_weaknesses(current, prior)
        assert weaknesses == []  # auth is not stale, just reduced

    def test_strengths_capped_at_three(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        current = []
        for topic in ("a", "b", "c", "d", "e"):
            current.extend([_contrib(now - timedelta(days=1), topics=[topic]) for _ in range(4)])
        strengths, _ = _member_strengths_and_weaknesses(current, [])
        assert len(strengths) == 3


class TestOrgSummary:
    def test_bus_factor_isolates_single_contributor_topics(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        current = [
            _contrib(now - timedelta(days=1), member_id="alice", topics=["api"]),
            _contrib(now - timedelta(days=2), member_id="bob", topics=["api"]),
            _contrib(now - timedelta(days=3), member_id="alice", topics=["billing"]),
            _contrib(now - timedelta(days=4), member_id="alice", topics=["billing"]),
            _contrib(now - timedelta(days=5), member_id="alice", topics=["billing"]),
        ]
        summary = _org_summary(
            org_id="org-1",
            member_ids=["alice", "bob"],
            current_rows=current,
            prior_rows=[],
            member_names_by_id={"alice": "Alice", "bob": "Bob"},
            computed_at=now,
        )
        # billing has 3 contributions all from alice → bus-factor risk.
        bf_topics = {b["topic"] for b in summary["bus_factor"]}
        assert "billing" in bf_topics
        assert "api" not in bf_topics
        alice_entry = next(b for b in summary["bus_factor"] if b["topic"] == "billing")
        assert alice_entry["sole_expert_name"] == "Alice"

    def test_top_members_ordered_by_count(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        current = [_contrib(now - timedelta(days=1), member_id="alice", topics=["api"]) for _ in range(5)]
        current += [_contrib(now - timedelta(days=1), member_id="bob", topics=["api"]) for _ in range(3)]

        summary = _org_summary(
            org_id="org-1",
            member_ids=["alice", "bob"],
            current_rows=current,
            prior_rows=[],
            member_names_by_id={"alice": "Alice", "bob": "Bob"},
            computed_at=now,
        )
        assert [m["name"] for m in summary["top_members"]] == ["Alice", "Bob"]
        assert summary["top_members"][0]["count"] == 5

    def test_weaknesses_require_prior_activity_and_current_silence(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        prior = [_contrib(now - timedelta(days=40), member_id="alice", topics=["legacy"]) for _ in range(4)]
        summary = _org_summary(
            org_id="org-1",
            member_ids=["alice"],
            current_rows=[],
            prior_rows=prior,
            member_names_by_id={"alice": "Alice"},
            computed_at=now,
        )
        assert summary["weaknesses"] == [{"topic": "legacy", "prior_count": 4, "current_count": 0}]


class TestComputeAndSaveStrengthsWeaknesses:
    def test_updates_members_and_org(self):
        now = datetime(2026, 4, 23, tzinfo=UTC)
        recent = now - timedelta(days=CURRENT_WINDOW_DAYS - 5)

        alice = SimpleNamespace(
            id="alice",
            name="Alice",
            organization_id="org-1",
            strengths=[],
            weaknesses=[],
        )
        bob = SimpleNamespace(
            id="bob",
            name="Bob",
            organization_id="org-1",
            strengths=[],
            weaknesses=[],
        )

        org = SimpleNamespace(id="org-1", strengths_weaknesses_json={})

        contribs = [
            _contrib(recent - timedelta(days=1), member_id="alice", topics=["api"]),
            _contrib(recent - timedelta(days=2), member_id="alice", topics=["api"]),
            _contrib(recent - timedelta(days=3), member_id="alice", topics=["api"]),
            _contrib(recent - timedelta(days=4), member_id="alice", topics=["api"]),
            _contrib(recent - timedelta(days=5), member_id="bob", topics=["docs"]),
        ]

        db = MagicMock()

        def query_router(model):
            q = MagicMock()
            name = getattr(model, "__name__", "")
            q.filter.return_value = q
            if name == "MemberRecord":
                q.all.return_value = [alice, bob]
            elif name == "ContributionRecord":
                q.all.return_value = contribs
            elif name == "OrganizationRecord":
                q.first.return_value = org
            return q

        db.query.side_effect = query_router

        result = compute_and_save_strengths_weaknesses(db, now=now)

        assert result["members_processed"] == 2
        # Alice got 4x api → 1 strength. Bob got 1x docs (below threshold) → no change.
        assert alice.strengths == [{"topic": "api", "count": 4}]
        assert bob.strengths == []
        # Org JSON was repopulated.
        assert org.strengths_weaknesses_json["organization_id"] == "org-1"
        assert any(s["topic"] == "api" for s in org.strengths_weaknesses_json["strengths"])
        db.commit.assert_called_once()

    def test_no_members_is_a_noop(self):
        db = MagicMock()

        def query_router(model):
            q = MagicMock()
            q.filter.return_value = q
            name = getattr(model, "__name__", "")
            if name == "MemberRecord":
                q.all.return_value = []
            else:
                q.all.return_value = []
            return q

        db.query.side_effect = query_router
        result = compute_and_save_strengths_weaknesses(db, now=datetime.now(UTC))
        assert result["members_updated"] == 0
        assert result["orgs_updated"] == 0
