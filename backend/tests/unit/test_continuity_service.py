"""Unit tests for ContinuityScoreService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.continuity_service import ContinuityScoreService


def _make_member(
    member_id,
    name,
    expertise_tags=None,
    status="active",
    total_contributions=10,
    last_active=None,
):
    m = MagicMock()
    m.id = member_id
    m.name = name
    m.expertise_tags = expertise_tags or []
    m.status = status
    m.total_contributions = total_contributions
    m.last_active = last_active or datetime.now(UTC)
    return m


def _make_artifact(artifact_id, title="Test", member_ids=None):
    a = MagicMock()
    a.id = artifact_id
    a.title = title
    a.member_ids = member_ids or []
    return a


def _make_continuity_score(score_id="cs1", entity_type="team", score=75.0):
    cs = MagicMock()
    cs.id = score_id
    cs.entity_type = entity_type
    cs.score = score
    cs.calculated_at = datetime.now(UTC)
    return cs


# ---------------------------------------------------------------------------
# TestMemberContinuity
# ---------------------------------------------------------------------------


class TestMemberContinuity:
    def test_high_score_for_replaceable_member(self, mock_db):
        """A member whose expertise is shared by others should yield a high continuity score."""
        service = ContinuityScoreService()

        target = _make_member("m1", "Alice", expertise_tags=["python", "api"], total_contributions=5)
        all_members = [
            target,
            _make_member("m2", "Bob", expertise_tags=["python", "api"]),
            _make_member("m3", "Charlie", expertise_tags=["python", "api"]),
        ]

        # Member lookup
        mock_db.query.return_value.filter.return_value.first.return_value = target
        mock_db.query.return_value.filter.return_value.all.return_value = all_members

        # No sole-contributor artifacts
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = service.calculate_member_continuity(mock_db, "m1")

        assert result["member_name"] == "Alice"
        assert result["score"] >= 60  # Should be relatively high
        assert result["risk_level"] in ("low", "medium")
        assert len(result["knowledge_areas_at_risk"]) == 0

    def test_low_score_for_irreplaceable_member(self, mock_db):
        """A member with unique expertise and sole-contributor artifacts should score low."""
        service = ContinuityScoreService()

        target = _make_member(
            "m1", "Alice",
            expertise_tags=["kubernetes", "terraform", "helm"],
            total_contributions=50,
            last_active=datetime.now(UTC),
        )
        all_members = [
            target,
            _make_member("m2", "Bob", expertise_tags=["python"]),
            _make_member("m3", "Charlie", expertise_tags=["javascript"]),
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = target
        mock_db.query.return_value.filter.return_value.all.return_value = all_members

        # 4 sole-contributor artifacts
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("a1",), ("a2",), ("a3",), ("a4",),
        ]
        # No other contributors
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = service.calculate_member_continuity(mock_db, "m1")

        assert result["score"] <= 50
        assert result["risk_level"] in ("high", "critical")
        assert "kubernetes" in result["knowledge_areas_at_risk"]

    def test_member_not_found(self, mock_db):
        service = ContinuityScoreService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.calculate_member_continuity(mock_db, "nonexistent")

        assert result["member_name"] == "Unknown"
        assert result["score"] == 100
        assert result["risk_level"] == "low"

    def test_handles_member_with_no_contributions(self, mock_db):
        service = ContinuityScoreService()

        target = _make_member("m1", "NewPerson", expertise_tags=[], total_contributions=0)
        all_members = [target, _make_member("m2", "Bob", expertise_tags=["python"])]

        mock_db.query.return_value.filter.return_value.first.return_value = target
        mock_db.query.return_value.filter.return_value.all.return_value = all_members
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = service.calculate_member_continuity(mock_db, "m1")

        assert result["score"] >= 0
        assert result["artifacts_at_risk"] == 0


# ---------------------------------------------------------------------------
# TestTeamContinuity
# ---------------------------------------------------------------------------


class TestTeamContinuity:
    def _setup_team_mocks(self, mock_db, members):
        """Helper to set up mock chains for team continuity calculation."""
        mock_db.query.return_value.filter.return_value.all.return_value = members
        mock_db.query.return_value.filter.return_value.first.side_effect = members
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

    def test_returns_overall_score(self, mock_db):
        service = ContinuityScoreService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python", "api"]),
            _make_member("m2", "Bob", expertise_tags=["python", "api"]),
        ]
        self._setup_team_mocks(mock_db, members)

        result = service.calculate_team_continuity(mock_db)

        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100
        assert "risk_level" in result

    def test_identifies_weakest_links(self, mock_db):
        service = ContinuityScoreService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        self._setup_team_mocks(mock_db, members)

        result = service.calculate_team_continuity(mock_db)

        assert "weakest_links" in result
        assert isinstance(result["weakest_links"], list)

    def test_identifies_knowledge_gaps(self, mock_db):
        service = ContinuityScoreService()
        # Only Alice knows k8s -> knowledge gap
        members = [
            _make_member("m1", "Alice", expertise_tags=["kubernetes"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        self._setup_team_mocks(mock_db, members)

        result = service.calculate_team_continuity(mock_db)

        assert "knowledge_gaps" in result

    def test_generates_recommendations(self, mock_db):
        service = ContinuityScoreService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        self._setup_team_mocks(mock_db, members)

        result = service.calculate_team_continuity(mock_db)

        assert "recommendations" in result
        assert len(result["recommendations"]) >= 1

    def test_handles_no_active_members(self, mock_db):
        service = ContinuityScoreService()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service.calculate_team_continuity(mock_db)

        assert result["overall_score"] == 0
        assert result["risk_level"] == "critical"
        assert len(result["recommendations"]) >= 1

    def test_handles_single_member_team(self, mock_db):
        service = ContinuityScoreService()
        members = [_make_member("m1", "Alice", expertise_tags=["python"])]
        self._setup_team_mocks(mock_db, members)

        result = service.calculate_team_continuity(mock_db)

        assert result["overall_score"] >= 0
        assert result["member_count"] == 1


# ---------------------------------------------------------------------------
# TestProjectContinuity
# ---------------------------------------------------------------------------


class TestProjectContinuity:
    def test_calculates_for_artifact_set(self, mock_db):
        service = ContinuityScoreService()

        artifacts = [
            _make_artifact("a1", "Backend API", member_ids=["m1", "m2"]),
            _make_artifact("a2", "Frontend App", member_ids=["m1", "m3"]),
        ]

        active_members = [
            _make_member("m1", "Alice"),
            _make_member("m2", "Bob"),
            _make_member("m3", "Charlie"),
        ]

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            artifacts,       # artifacts query
            active_members,  # active contributors query
        ]

        result = service.calculate_project_continuity(mock_db, ["a1", "a2"])

        assert result["artifact_count"] == 2
        assert result["contributor_count"] == 3
        assert 0 <= result["score"] <= 100

    def test_empty_artifact_ids(self, mock_db):
        service = ContinuityScoreService()

        result = service.calculate_project_continuity(mock_db, [])

        assert result["score"] == 0
        assert result["risk_level"] == "critical"
        assert result["artifact_count"] == 0

    def test_single_contributor_artifacts_flagged(self, mock_db):
        service = ContinuityScoreService()

        artifacts = [
            _make_artifact("a1", "Lonely Project", member_ids=["m1"]),
        ]

        active_members = [_make_member("m1", "Alice")]

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            artifacts,
            active_members,
        ]

        result = service.calculate_project_continuity(mock_db, ["a1"])

        assert len(result["single_contributor_artifacts"]) == 1
        assert result["score"] < 100  # Penalized for single contributor


# ---------------------------------------------------------------------------
# TestContinuityDashboard
# ---------------------------------------------------------------------------


class TestContinuityDashboard:
    def test_returns_all_required_fields(self, mock_db):
        service = ContinuityScoreService()

        members = [
            _make_member("m1", "Alice", expertise_tags=["python", "api"]),
            _make_member("m2", "Bob", expertise_tags=["python", "api"]),
        ]

        # Team continuity mock
        mock_db.query.return_value.filter.return_value.all.return_value = members
        mock_db.query.return_value.filter.return_value.first.side_effect = members * 5
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        # ContinuityScore history
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = service.get_continuity_dashboard(mock_db)

        required_keys = [
            "overall_score", "risk_level", "members_at_risk",
            "knowledge_gaps", "backed_up_areas", "total_members",
            "recommendations",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_backed_up_areas_count_correct(self, mock_db):
        service = ContinuityScoreService()

        # python is shared (backed up), k8s is not
        members = [
            _make_member("m1", "Alice", expertise_tags=["python", "kubernetes"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
            _make_member("m3", "Charlie", expertise_tags=["python"]),
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = members
        mock_db.query.return_value.filter.return_value.first.side_effect = members * 5
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = service.get_continuity_dashboard(mock_db)

        # "python" is covered by 3 members -> backed up
        # "kubernetes" is covered by 1 member -> gap
        assert result["backed_up_areas"] >= 1
        gap_tags = [g["tag"] for g in result["knowledge_gaps"]]
        assert "kubernetes" in gap_tags


# ---------------------------------------------------------------------------
# TestScoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_score_range_0_to_100(self, mock_db):
        service = ContinuityScoreService()

        # Test with extreme case: very high impact member
        member = _make_member(
            "m1", "Alice",
            expertise_tags=["a", "b", "c", "d", "e"],
            total_contributions=100,
            last_active=datetime.now(UTC),
        )
        all_members = [member]

        mock_db.query.return_value.filter.return_value.first.return_value = member
        mock_db.query.return_value.filter.return_value.all.return_value = all_members
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("a1",), ("a2",), ("a3",), ("a4",), ("a5",),
        ]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = service.calculate_member_continuity(mock_db, "m1")
        assert 0 <= result["score"] <= 100

    def test_risk_level_mapping(self):
        service = ContinuityScoreService()

        assert service._risk_level(85) == "low"
        assert service._risk_level(80) == "low"
        assert service._risk_level(65) == "medium"
        assert service._risk_level(60) == "medium"
        assert service._risk_level(45) == "high"
        assert service._risk_level(40) == "high"
        assert service._risk_level(35) == "critical"
        assert service._risk_level(10) == "critical"
        assert service._risk_level(0) == "critical"

    def test_risk_level_boundary_values(self):
        service = ContinuityScoreService()

        # Exact boundaries based on the implementation:
        # >= 80 -> low, >= 60 -> medium, >= 40 -> high, < 40 -> critical
        assert service._risk_level(79.9) == "medium"
        assert service._risk_level(59.9) == "high"
        assert service._risk_level(39.9) == "critical"


# ---------------------------------------------------------------------------
# TestMemberRecommendations
# ---------------------------------------------------------------------------


class TestMemberRecommendations:
    def test_recommendations_for_unique_expertise(self):
        member = _make_member("m1", "Alice", expertise_tags=["kubernetes"])
        factors = {
            "unique_tags": ["kubernetes"],
            "sole_artifact_count": 0,
            "backup_members": {"kubernetes": []},
        }

        recs = ContinuityScoreService._member_recommendations(member, factors)

        assert len(recs) >= 1
        assert any("Cross-train" in r for r in recs)

    def test_recommendations_for_sole_contributor(self):
        member = _make_member("m1", "Alice")
        factors = {
            "unique_tags": [],
            "sole_artifact_count": 3,
            "backup_members": {},
        }

        recs = ContinuityScoreService._member_recommendations(member, factors)

        assert any("second contributor" in r for r in recs)

    def test_recommendations_when_well_covered(self):
        member = _make_member("m1", "Alice", expertise_tags=["python"])
        factors = {
            "unique_tags": [],
            "sole_artifact_count": 0,
            "backup_members": {"python": ["Bob", "Charlie"]},
        }

        recs = ContinuityScoreService._member_recommendations(member, factors)

        assert any("well-distributed" in r for r in recs)


# ---------------------------------------------------------------------------
# TestTeamRecommendations
# ---------------------------------------------------------------------------


class TestTeamRecommendations:
    def test_flags_critical_members(self):
        member_results = [
            {"member_name": "Alice", "risk_level": "critical", "score": 15, "artifacts_at_risk": 5,
             "knowledge_areas_at_risk": ["k8s"]},
            {"member_name": "Bob", "risk_level": "low", "score": 90, "artifacts_at_risk": 0,
             "knowledge_areas_at_risk": []},
        ]
        recs = ContinuityScoreService._team_recommendations(member_results, ["k8s"])

        assert any("critical" in r.lower() or "Alice" in r for r in recs)

    def test_healthy_team_gets_positive_recommendation(self):
        member_results = [
            {"member_name": "Alice", "risk_level": "low", "score": 90, "artifacts_at_risk": 0,
             "knowledge_areas_at_risk": []},
            {"member_name": "Bob", "risk_level": "low", "score": 85, "artifacts_at_risk": 0,
             "knowledge_areas_at_risk": []},
        ]
        recs = ContinuityScoreService._team_recommendations(member_results, [])

        assert any("healthy" in r.lower() for r in recs)
