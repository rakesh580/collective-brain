"""Unit tests for OffboardingService and public KB publish logic."""

from unittest.mock import MagicMock

import pytest

from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.offboarding_report import OffboardingReport
from app.services.offboarding_service import (
    OffboardingService,
    _build_summary,
    _compute_risk,
    _find_candidates,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_member(
    member_id: str, name: str, expertise_tags: list[str] | None = None, status: str = "active"
) -> MagicMock:
    m = MagicMock(spec=MemberRecord)
    m.id = member_id
    m.name = name
    m.expertise_tags = expertise_tags or []
    m.expertise_scores = {}
    m.status = status
    return m


def _make_contribution(member_id: str, artifact_id: str, topics: list[str] | None = None) -> MagicMock:
    c = MagicMock(spec=ContributionRecord)
    c.member_id = member_id
    c.artifact_id = artifact_id
    c.topics = topics or []
    return c


# ── _compute_risk ──────────────────────────────────────────────────────────────


class TestComputeRisk:
    def test_no_unique_no_sole_is_low(self):
        assert _compute_risk([], 0, 10) == "low"

    def test_one_unique_zero_sole_is_medium(self):
        assert _compute_risk(["infra"], 0, 5) == "medium"

    def test_two_unique_one_sole_is_high(self):
        # score = 2*2 + 1 = 5
        assert _compute_risk(["infra", "kafka"], 1, 20) == "high"

    def test_many_unique_sole_is_critical(self):
        # score = 2*5 + 5 = 15
        assert _compute_risk(["a", "b", "c", "d", "e"], 5, 100) == "critical"

    def test_boundary_medium_to_high(self):
        # score = 2*1 + 1 = 3 → medium (<=3)
        assert _compute_risk(["x"], 1, 1) == "medium"
        # score = 2*2 + 1 = 5 → high
        assert _compute_risk(["x", "y"], 1, 1) == "high"


# ── _find_candidates ───────────────────────────────────────────────────────────


class TestFindCandidates:
    def test_exact_match_returned(self):
        alice = _make_member("alice", "Alice", expertise_tags=["kafka"])
        bob = _make_member("bob", "Bob", expertise_tags=["redis"])
        result = _find_candidates("kafka", [alice, bob])
        assert result[0].id == "alice"

    def test_no_match_returns_empty(self):
        alice = _make_member("alice", "Alice", expertise_tags=["redis"])
        result = _find_candidates("kafka", [alice])
        assert result == []

    def test_multiple_candidates_all_returned(self):
        alice = _make_member("alice", "Alice", expertise_tags=["kafka", "python"])
        bob = _make_member("bob", "Bob", expertise_tags=["kafka"])
        result = _find_candidates("kafka", [alice, bob])
        ids = [m.id for m in result]
        assert "alice" in ids and "bob" in ids

    def test_expertise_scores_boost_ranking(self):
        alice = _make_member("alice", "Alice", expertise_tags=["kafka"])
        bob = _make_member("bob", "Bob", expertise_tags=["kafka"])
        bob.expertise_scores = {"kafka": 5.0}
        result = _find_candidates("kafka", [alice, bob])
        # bob has higher score, should come first
        assert result[0].id == "bob"


# ── _build_summary ─────────────────────────────────────────────────────────────


class TestBuildSummary:
    def test_no_unique_expertise_says_well_distributed(self):
        m = _make_member("m1", "Dave")
        summary = _build_summary(m, [], [], "low")
        assert "well distributed" in summary.lower()

    def test_unique_expertise_listed(self):
        m = _make_member("m1", "Eve")
        summary = _build_summary(m, ["kafka", "redis"], [], "high")
        assert "kafka" in summary
        assert "redis" in summary

    def test_sole_artifact_count_mentioned(self):
        m = _make_member("m1", "Frank")
        summary = _build_summary(m, [], ["art-1", "art-2"], "medium")
        assert "2 artifact" in summary

    def test_risk_level_in_summary(self):
        m = _make_member("m1", "Grace")
        summary = _build_summary(m, [], [], "critical")
        assert "CRITICAL" in summary


# ── OffboardingService ─────────────────────────────────────────────────────────


class TestOffboardingService:
    def _make_db(self, member, contributions, other_members, contributions_for_artifact=None):
        db = MagicMock()

        def _query_side_effect(model):
            q = MagicMock()
            if model is MemberRecord:
                # First call: get the member; subsequent calls: get others
                filter_mock = MagicMock()
                filter_mock.first.return_value = member
                filter_mock.all.return_value = other_members
                q.filter.return_value = filter_mock
            elif model is ContributionRecord:
                filter_mock = MagicMock()
                filter_mock.all.return_value = (
                    contributions_for_artifact if contributions_for_artifact is not None else contributions
                )
                q.filter.return_value = filter_mock
            return q

        db.query.side_effect = _query_side_effect
        return db

    def test_no_contributions_gives_low_risk(self):
        svc = OffboardingService()
        member = _make_member("m1", "Alex")
        db = MagicMock()

        # MemberRecord queries
        member_filter = MagicMock()
        member_filter.first.return_value = member
        member_filter.all.return_value = []

        # ContributionRecord queries
        contrib_filter = MagicMock()
        contrib_filter.all.return_value = []
        contrib_filter.order_by = MagicMock(return_value=contrib_filter)

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = member_filter if model is MemberRecord else contrib_filter
            return q

        db.query.side_effect = query_side

        report = svc.generate_report(db, "m1", created_by="admin-1")
        assert report.risk_level == "low"
        assert member.status == "offboarding"
        db.commit.assert_called()

    def test_unique_expertise_detected(self):
        """Member with topics no-one else covers → unique_expertise populated."""
        svc = OffboardingService()
        member = _make_member("m1", "Heidi", expertise_tags=["kafka"])
        other = _make_member("m2", "Ivan", expertise_tags=["redis"])  # no kafka
        contrib = _make_contribution("m1", "art-1", topics=["kafka"])

        db = MagicMock()
        call_count = [0]

        def query_side(model):
            q = MagicMock()
            if model is MemberRecord:
                f = MagicMock()
                call_count[0] += 1
                if call_count[0] == 1:
                    f.first.return_value = member  # get_member
                else:
                    f.all.return_value = [other]  # get other members
                q.filter.return_value = f
            else:
                f = MagicMock()
                f.all.return_value = [contrib]
                q.filter.return_value = f
            return q

        db.query.side_effect = query_side

        report = svc.generate_report(db, "m1")
        assert "kafka" in report.unique_expertise

    def test_member_not_found_raises(self):
        svc = OffboardingService()
        db = MagicMock()
        f = MagicMock()
        f.first.return_value = None
        db.query.return_value.filter.return_value = f
        with pytest.raises(ValueError, match="not found"):
            svc.generate_report(db, "missing-id")

    def test_complete_offboarding_sets_status(self):
        svc = OffboardingService()
        member = _make_member("m1", "Judy")
        db = MagicMock()
        f = MagicMock()
        f.first.return_value = member
        db.query.return_value.filter.return_value = f
        svc.complete_offboarding(db, "m1")
        assert member.status == "offboarded"
        db.commit.assert_called()

    def test_complete_offboarding_not_found_raises(self):
        svc = OffboardingService()
        db = MagicMock()
        f = MagicMock()
        f.first.return_value = None
        db.query.return_value.filter.return_value = f
        with pytest.raises(ValueError, match="not found"):
            svc.complete_offboarding(db, "bad-id")

    def test_get_report_returns_latest(self):
        svc = OffboardingService()
        report = MagicMock(spec=OffboardingReport)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = report
        result = svc.get_report(db, "m1")
        assert result is report

    def test_get_report_none_when_no_report(self):
        svc = OffboardingService()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        result = svc.get_report(db, "m1")
        assert result is None


# ── PublishResponse schema (smoke test) ────────────────────────────────────────


class TestPublishSchemas:
    def test_publish_response_fields(self):
        from app.routers.public_kb import PublishResponse

        r = PublishResponse(id="art-1", is_public=True, message="Published")
        assert r.id == "art-1"
        assert r.is_public is True

    def test_public_artifact_response_fields(self):
        from app.routers.public_kb import PublicArtifactResponse

        r = PublicArtifactResponse(
            id="a1",
            title="My doc",
            source_type="notion",
            source_url="https://notion.so/abc",
            ingested_at="2026-01-01T00:00:00",
        )
        assert r.source_type == "notion"

    def test_public_insight_response_fields(self):
        from app.routers.public_kb import PublicInsightResponse

        r = PublicInsightResponse(
            id="i1",
            title="Pattern",
            body="We found X",
            insight_type="pattern",
            generated_at="2026-01-01T00:00:00",
            confidence=0.9,
        )
        assert r.confidence == 0.9
