"""Unit tests for RiskRadarService."""

from collections import namedtuple
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, call

import pytest

from app.services.risk_radar import RiskRadarService


def _make_member(member_id, name, expertise_tags=None, status="active"):
    m = MagicMock()
    m.id = member_id
    m.name = name
    m.expertise_tags = expertise_tags or []
    m.status = status
    return m


def _make_artifact(artifact_id, title="Test Artifact", member_ids=None, ingested_at=None):
    a = MagicMock()
    a.id = artifact_id
    a.title = title
    a.member_ids = member_ids or []
    a.ingested_at = ingested_at or datetime.now(UTC)
    return a


def _make_alert(
    alert_id="alert-1",
    alert_type="knowledge_silo",
    severity="high",
    title="Test Alert",
    description="Desc",
    affected_entity_type="member",
    affected_entity_id="m1",
    metrics=None,
    is_acknowledged=False,
    is_resolved=False,
    detected_at=None,
    acknowledged_at=None,
    resolved_at=None,
):
    a = MagicMock()
    a.id = alert_id
    a.alert_type = alert_type
    a.severity = severity
    a.title = title
    a.description = description
    a.affected_entity_type = affected_entity_type
    a.affected_entity_id = affected_entity_id
    a.metrics = metrics or {}
    a.is_acknowledged = is_acknowledged
    a.is_resolved = is_resolved
    a.detected_at = detected_at or datetime.now(UTC)
    a.acknowledged_at = acknowledged_at
    a.resolved_at = resolved_at
    return a


# Helper namedtuple for group_by query results
ContribRow = namedtuple("ContribRow", ["artifact_id", "cnt"])


# ---------------------------------------------------------------------------
# TestDetectProjectStalls
# ---------------------------------------------------------------------------


class TestDetectProjectStalls:
    def test_detects_contribution_drop(self, mock_db):
        service = RiskRadarService()

        # Previous week: 10 contributions to artifact a1
        # Current week: 2 contributions -> 80% drop
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [ContribRow(artifact_id="a1", cnt=2)],   # recent
            [ContribRow(artifact_id="a1", cnt=10)],   # previous
        ]
        artifact = _make_artifact("a1", title="Backend API")
        mock_db.query.return_value.filter.return_value.first.return_value = artifact

        alerts = service._detect_project_stalls(mock_db)

        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "project_stall"
        assert alerts[0]["metrics"]["drop_percentage"] == 80.0
        assert alerts[0]["severity"] == "high"

    def test_no_alert_when_stable(self, mock_db):
        service = RiskRadarService()

        mock_db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [ContribRow(artifact_id="a1", cnt=10)],  # recent
            [ContribRow(artifact_id="a1", cnt=10)],  # previous
        ]

        alerts = service._detect_project_stalls(mock_db)
        assert len(alerts) == 0

    def test_handles_no_contributions(self, mock_db):
        service = RiskRadarService()

        mock_db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [],  # recent
            [],  # previous
        ]

        alerts = service._detect_project_stalls(mock_db)
        assert alerts == []


# ---------------------------------------------------------------------------
# TestDetectKnowledgeSilos
# ---------------------------------------------------------------------------


class TestDetectKnowledgeSilos:
    def test_detects_single_expert_tags(self, mock_db):
        service = RiskRadarService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["kubernetes", "python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_knowledge_silos(mock_db)

        # "kubernetes" is only known by Alice
        silo_tags = [a["affected_entity_id"] for a in alerts]
        assert "kubernetes" in silo_tags
        # "python" is shared, should NOT be flagged
        assert "python" not in silo_tags

    def test_no_silo_when_shared_expertise(self, mock_db):
        service = RiskRadarService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python", "api"]),
            _make_member("m2", "Bob", expertise_tags=["python", "api"]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_knowledge_silos(mock_db)
        assert alerts == []

    def test_handles_empty_expertise(self, mock_db):
        service = RiskRadarService()
        members = [
            _make_member("m1", "Alice", expertise_tags=[]),
            _make_member("m2", "Bob", expertise_tags=[]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_knowledge_silos(mock_db)
        assert alerts == []

    def test_handles_no_active_members(self, mock_db):
        service = RiskRadarService()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        alerts = service._detect_knowledge_silos(mock_db)
        assert alerts == []


# ---------------------------------------------------------------------------
# TestDetectKeyPersonRisks
# ---------------------------------------------------------------------------


class TestDetectKeyPersonRisks:
    def test_flags_sole_contributor_to_multiple_artifacts(self, mock_db):
        service = RiskRadarService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        # Alice contributed to 4 artifacts, all as sole contributor
        contrib_results = [("a1",), ("a2",), ("a3",), ("a4",)]

        call_count = [0]

        def _query_side_effect(*args):
            """Handle different query().filter() chains."""
            q = MagicMock()

            def _filter_side(*fargs, **fkwargs):
                f = MagicMock()
                call_count[0] += 1
                # We need to handle the distinct().all() chain for contributions
                # and the scalar() chain for other_count
                f.distinct.return_value.all.return_value = contrib_results
                f.scalar.return_value = 0  # no other contributors
                return f

            q.filter.side_effect = _filter_side
            return q

        mock_db.query.side_effect = _query_side_effect

        # Re-mock the initial member query
        # We need a more careful setup; let's use a simpler approach
        mock_db.query.side_effect = None
        mock_db.query.return_value.filter.return_value.all.return_value = members
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("a1",), ("a2",), ("a3",),
        ]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        alerts = service._detect_key_person_risks(mock_db)

        # Both members are sole contributors to 3 artifacts each (due to shared mocks)
        assert len(alerts) >= 1
        assert any(a["alert_type"] == "key_person_risk" for a in alerts)

    def test_no_risk_when_shared_contributions(self, mock_db):
        service = RiskRadarService()
        members = [
            _make_member("m1", "Alice", expertise_tags=["python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("a1",),
        ]
        # Other contributors exist
        mock_db.query.return_value.filter.return_value.scalar.return_value = 2

        alerts = service._detect_key_person_risks(mock_db)

        # No sole artifacts and python is shared -> no risk
        assert alerts == []


# ---------------------------------------------------------------------------
# TestDetectCollaborationDrops
# ---------------------------------------------------------------------------


class TestDetectCollaborationDrops:
    def test_detects_decreasing_multi_contributor_ratio(self, mock_db):
        service = RiskRadarService()
        now = datetime.now(UTC)

        # Recent: 4 artifacts, 0 multi-contributor = 0%
        recent_artifacts = [
            _make_artifact(f"ra{i}", member_ids=["m1"], ingested_at=now - timedelta(days=3))
            for i in range(4)
        ]
        # Older: 4 artifacts, 4 multi-contributor = 100%
        older_artifacts = [
            _make_artifact(f"oa{i}", member_ids=["m1", "m2"], ingested_at=now - timedelta(days=20))
            for i in range(4)
        ]

        call_count = [0]

        def _filter_side(*args, **kwargs):
            m = MagicMock()
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                m.all.return_value = recent_artifacts
            else:
                m.all.return_value = older_artifacts
            return m

        mock_db.query.return_value.filter.side_effect = _filter_side

        alerts = service._detect_collaboration_drops(mock_db)

        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "collaboration_drop"
        assert alerts[0]["metrics"]["drop_percentage"] == 100.0

    def test_no_alert_when_collaboration_stable(self, mock_db):
        service = RiskRadarService()
        now = datetime.now(UTC)

        artifacts = [
            _make_artifact(f"a{i}", member_ids=["m1", "m2"], ingested_at=now - timedelta(days=3))
            for i in range(4)
        ]

        mock_db.query.return_value.filter.side_effect = None
        mock_db.query.return_value.filter.return_value.all.return_value = artifacts

        alerts = service._detect_collaboration_drops(mock_db)
        assert alerts == []


# ---------------------------------------------------------------------------
# TestDetectExpertiseConcentration
# ---------------------------------------------------------------------------


class TestDetectExpertiseConcentration:
    def test_flags_low_expert_ratio(self, mock_db):
        service = RiskRadarService()
        # 10 members, only 1 knows "kubernetes" -> ratio = 0.1 < 0.15
        members = [_make_member(f"m{i}", f"Person{i}", expertise_tags=["python"]) for i in range(10)]
        members[0].expertise_tags = ["python", "kubernetes"]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_expertise_concentration(mock_db)

        k8s_alerts = [a for a in alerts if a["affected_entity_id"] == "kubernetes"]
        assert len(k8s_alerts) == 1
        assert k8s_alerts[0]["severity"] == "high"

    def test_no_alert_when_well_distributed(self, mock_db):
        service = RiskRadarService()
        # 4 members, 3 know "python" -> ratio = 0.75 > 0.15
        members = [
            _make_member("m1", "Alice", expertise_tags=["python"]),
            _make_member("m2", "Bob", expertise_tags=["python"]),
            _make_member("m3", "Charlie", expertise_tags=["python"]),
            _make_member("m4", "Dave", expertise_tags=["python"]),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_expertise_concentration(mock_db)
        assert alerts == []

    def test_skips_for_too_few_members(self, mock_db):
        service = RiskRadarService()
        members = [_make_member("m1", "Alice", expertise_tags=["kubernetes"])]
        mock_db.query.return_value.filter.return_value.all.return_value = members

        alerts = service._detect_expertise_concentration(mock_db)
        assert alerts == []


# ---------------------------------------------------------------------------
# TestScanAllRisks
# ---------------------------------------------------------------------------


class TestScanAllRisks:
    def test_runs_all_detectors(self, mock_db):
        service = RiskRadarService()

        # Patch all detection methods to return known alerts
        service._detect_project_stalls = MagicMock(return_value=[
            {
                "alert_type": "project_stall", "severity": "high", "title": "Stall",
                "description": "desc", "affected_entity_type": "artifact",
                "affected_entity_id": "a1", "metrics": {},
            }
        ])
        service._detect_knowledge_silos = MagicMock(return_value=[])
        service._detect_key_person_risks = MagicMock(return_value=[])
        service._detect_collaboration_drops = MagicMock(return_value=[])
        service._detect_expertise_concentration = MagicMock(return_value=[])

        # No existing alert
        mock_db.query.return_value.filter.return_value.first.return_value = None

        alerts = service.scan_all_risks(mock_db)

        service._detect_project_stalls.assert_called_once_with(mock_db)
        service._detect_knowledge_silos.assert_called_once_with(mock_db)
        service._detect_key_person_risks.assert_called_once_with(mock_db)
        service._detect_collaboration_drops.assert_called_once_with(mock_db)
        service._detect_expertise_concentration.assert_called_once_with(mock_db)

        assert len(alerts) == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_saves_alerts_to_db(self, mock_db):
        service = RiskRadarService()

        service._detect_project_stalls = MagicMock(return_value=[])
        service._detect_knowledge_silos = MagicMock(return_value=[
            {
                "alert_type": "knowledge_silo", "severity": "high",
                "title": "Silo: k8s", "description": "Only Alice",
                "affected_entity_type": "expertise_tag",
                "affected_entity_id": "kubernetes", "metrics": {},
            }
        ])
        service._detect_key_person_risks = MagicMock(return_value=[])
        service._detect_collaboration_drops = MagicMock(return_value=[])
        service._detect_expertise_concentration = MagicMock(return_value=[])

        mock_db.query.return_value.filter.return_value.first.return_value = None

        alerts = service.scan_all_risks(mock_db)

        assert len(alerts) == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        # Verify the saved RiskAlert has correct fields
        saved = mock_db.add.call_args[0][0]
        assert saved.alert_type == "knowledge_silo"
        assert saved.severity == "high"

    def test_handles_empty_org_gracefully(self, mock_db):
        service = RiskRadarService()

        service._detect_project_stalls = MagicMock(return_value=[])
        service._detect_knowledge_silos = MagicMock(return_value=[])
        service._detect_key_person_risks = MagicMock(return_value=[])
        service._detect_collaboration_drops = MagicMock(return_value=[])
        service._detect_expertise_concentration = MagicMock(return_value=[])

        alerts = service.scan_all_risks(mock_db)

        assert alerts == []
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# TestRiskSummary
# ---------------------------------------------------------------------------


class TestRiskSummary:
    def test_returns_correct_counts_by_severity(self, mock_db):
        service = RiskRadarService()

        alert1 = _make_alert(alert_id="a1", severity="critical", alert_type="key_person_risk")
        alert2 = _make_alert(alert_id="a2", severity="high", alert_type="knowledge_silo")
        alert3 = _make_alert(alert_id="a3", severity="high", alert_type="project_stall")

        mock_db.query.return_value.filter.return_value.all.return_value = [alert1, alert2, alert3]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        summary = service.get_risk_summary(mock_db)

        assert summary["total_alerts"] == 3
        assert summary["critical_count"] == 1
        assert summary["high_count"] == 2
        assert summary["medium_count"] == 0
        assert summary["low_count"] == 0

    def test_includes_trend_data(self, mock_db):
        service = RiskRadarService()

        mock_db.query.return_value.filter.return_value.all.return_value = []
        # recent_count=5, older_count=2 -> increasing
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [5, 2]

        summary = service.get_risk_summary(mock_db)

        assert summary["trend"] == "increasing"
        assert summary["recent_count"] == 5
        assert summary["previous_count"] == 2

    def test_empty_alerts_returns_zeros(self, mock_db):
        service = RiskRadarService()

        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        summary = service.get_risk_summary(mock_db)

        assert summary["total_alerts"] == 0
        assert summary["critical_count"] == 0
        assert summary["high_count"] == 0
        assert summary["trend"] == "stable"

    def test_trend_decreasing(self, mock_db):
        service = RiskRadarService()

        mock_db.query.return_value.filter.return_value.all.return_value = []
        # recent=1, older=5 -> decreasing
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [1, 5]

        summary = service.get_risk_summary(mock_db)
        assert summary["trend"] == "decreasing"


# ---------------------------------------------------------------------------
# TestAlertManagement
# ---------------------------------------------------------------------------


class TestAlertManagement:
    def test_acknowledge_alert(self, mock_db):
        service = RiskRadarService()
        alert = _make_alert(alert_id="a1")

        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.acknowledge_alert(mock_db, "a1")

        assert result is not None
        assert alert.is_acknowledged is True
        assert alert.acknowledged_at is not None
        mock_db.commit.assert_called_once()

    def test_resolve_alert(self, mock_db):
        service = RiskRadarService()
        alert = _make_alert(alert_id="a1")

        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.resolve_alert(mock_db, "a1")

        assert result is not None
        assert alert.is_resolved is True
        assert alert.resolved_at is not None
        mock_db.commit.assert_called_once()

    def test_alert_not_found_acknowledge(self, mock_db):
        service = RiskRadarService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.acknowledge_alert(mock_db, "nonexistent")
        assert result is None

    def test_alert_not_found_resolve(self, mock_db):
        service = RiskRadarService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.resolve_alert(mock_db, "nonexistent")
        assert result is None

    def test_get_alert_by_id(self, mock_db):
        service = RiskRadarService()
        alert = _make_alert(alert_id="a1", title="Test Alert")
        mock_db.query.return_value.filter.return_value.first.return_value = alert

        result = service.get_alert_by_id(mock_db, "a1")

        assert result is not None
        assert result["id"] == "a1"
        assert result["title"] == "Test Alert"

    def test_get_alert_by_id_not_found(self, mock_db):
        service = RiskRadarService()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_alert_by_id(mock_db, "missing")
        assert result is None
