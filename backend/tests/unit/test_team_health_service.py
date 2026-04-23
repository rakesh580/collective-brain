"""Regression tests for team_health_service — the Pulse "Team Health" tab backend.

These tests pin the fixes for the Pulse 500 bug:

- ``compute_health_snapshot`` must never raise — a graph-build failure
  degrades to a zero-initialised snapshot so the tab renders empty rather
  than 500ing.
- ``save_health_snapshot`` must include ``organization_id`` in its INSERT
  so multi-tenant deployments don't leak snapshots across orgs.
- ``get_health_trends`` / ``predict_risks`` must accept an optional
  ``organization_id`` and scope queries accordingly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.services import team_health_service as svc


def test_compute_health_snapshot_returns_empty_on_graph_failure(monkeypatch):
    """Any exception inside MemoryGraph should not propagate — tab must render."""

    class Boom(Exception):
        pass

    class ExplodingGraph:
        def __init__(self, db):
            pass

        def _get_or_build_nx_graph(self):
            raise Boom("graph build failed")

    monkeypatch.setattr(svc, "MemoryGraph", ExplodingGraph)

    result = svc.compute_health_snapshot(MagicMock())

    assert result["health_score"] == 0.0
    assert result["bus_factor_count"] == 0
    assert result["top_risk"] is None
    assert "computed_at" in result


def test_save_health_snapshot_binds_organization_id(monkeypatch):
    """The raw SQL INSERT must pass organization_id — regression for the
    multi-tenant snapshot leak that manifested as 500s on /analytics/health."""
    recorded: dict = {}

    def fake_compute(db):
        return {
            "bus_factor_count": 1,
            "coverage_pct": 50.0,
            "collab_density": 0.2,
            "active_member_pct": 75.0,
            "avg_breadth": 3.5,
            "health_score": 65.0,
            "top_risk": {"topic": "api"},
            "computed_at": datetime.now(UTC).isoformat(),
        }

    monkeypatch.setattr(svc, "compute_health_snapshot", fake_compute)

    db = MagicMock()

    def capture(_stmt, params):
        recorded.update(params)
        return MagicMock()

    db.execute.side_effect = capture

    out = svc.save_health_snapshot(db, organization_id="org-42")

    assert recorded["organization_id"] == "org-42"
    assert recorded["bus_factor_count"] == 1
    assert out["success"] is True
    db.commit.assert_called_once()


def test_save_health_snapshot_default_org_is_none_for_scheduler(monkeypatch):
    """Nightly scheduler call passes no org — row written with NULL org."""
    recorded: dict = {}

    monkeypatch.setattr(
        svc,
        "compute_health_snapshot",
        lambda db: {
            "bus_factor_count": 0,
            "coverage_pct": 0.0,
            "collab_density": 0.0,
            "active_member_pct": 0.0,
            "avg_breadth": 0.0,
            "health_score": 0.0,
            "top_risk": None,
            "computed_at": datetime.now(UTC).isoformat(),
        },
    )

    db = MagicMock()
    db.execute.side_effect = lambda stmt, params: recorded.update(params) or MagicMock()

    svc.save_health_snapshot(db)

    assert recorded["organization_id"] is None


def test_get_health_trends_filters_by_org_when_provided(monkeypatch):
    """When an org is passed, the WHERE clause should include organization_id."""
    captured = {}

    class FakeResult:
        def fetchall(self):
            return []

    db = MagicMock()

    def capture(stmt, params):
        captured["sql"] = str(stmt)
        captured["params"] = params
        return FakeResult()

    db.execute.side_effect = capture

    svc.get_health_trends(db, period_days=30, organization_id="org-1")

    assert "organization_id = :org" in captured["sql"]
    assert captured["params"]["org"] == "org-1"


def test_get_health_trends_without_org_uses_legacy_query(monkeypatch):
    captured = {}

    class FakeResult:
        def fetchall(self):
            return []

    db = MagicMock()

    def capture(stmt, params):
        captured["sql"] = str(stmt)
        return FakeResult()

    db.execute.side_effect = capture

    svc.get_health_trends(db, period_days=30)

    # Unfiltered path intentionally does NOT carry the organization_id clause
    # so a nightly scheduler report can aggregate across tenants.
    assert "organization_id" not in captured["sql"]


def test_predict_risks_forwards_org_to_trends(monkeypatch):
    """predict_risks should plumb organization_id through to get_health_trends."""
    seen_orgs: list[str | None] = []

    def fake_trends(db, period_days, organization_id=None):
        seen_orgs.append(organization_id)
        return {"snapshots": [], "period_days": period_days}

    monkeypatch.setattr(svc, "get_health_trends", fake_trends)

    result = svc.predict_risks(MagicMock(), organization_id="org-xyz")

    assert seen_orgs == ["org-xyz"]
    assert "predictions" in result


def test_predict_risks_survives_null_metric_values(monkeypatch):
    """Regression for production TypeError (error_ref=022b7601).

    Old health_snapshots rows can have NULL numeric columns (written before
    defaults were applied, or from a manual backfill). The previous code did
    ``sum([None, 65.0, ...]) / n`` and crashed with TypeError, 500ing the
    entire Team Health tab — not just the row in question. Users saw only
    the red error banner, with no snapshot, trend, or prediction rendered.

    Behavior asserted: when any snapshot has a NULL metric, predict_risks
    returns a full predictions payload rather than raising. None values are
    treated as 0 for the linear-regression math.
    """

    def fake_trends(db, period_days, organization_id=None):
        return {
            "snapshots": [
                {
                    "health_score": None,  # Null from an old row.
                    "coverage_pct": 30.0,
                    "bus_factor_count": 2,
                    "collab_density": None,
                    "active_member_pct": 50.0,
                    "avg_breadth": 1.5,
                    "timestamp": "2026-03-01T00:00:00+00:00",
                },
                {
                    "health_score": 65.0,
                    "coverage_pct": 50.0,
                    "bus_factor_count": 1,
                    "collab_density": 0.3,
                    "active_member_pct": 75.0,
                    "avg_breadth": 2.5,
                    "timestamp": "2026-04-01T00:00:00+00:00",
                },
            ],
            "period_days": period_days,
        }

    monkeypatch.setattr(svc, "get_health_trends", fake_trends)

    # Must not raise. Must return one prediction per known metric.
    result = svc.predict_risks(MagicMock(), organization_id="org-1")

    metric_names = {p["metric"] for p in result["predictions"]}
    assert "Overall Health Score" in metric_names
    assert "Collaboration Density" in metric_names
    # Every prediction should have a numeric current_value — None would have
    # propagated if coercion didn't happen.
    for pred in result["predictions"]:
        assert isinstance(pred["current_value"], int | float)
        assert isinstance(pred["predicted_value"], int | float)
