"""Unit tests for GET /insights/team-strengths."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.routers.insights import get_team_strengths


@pytest.mark.asyncio
async def test_returns_empty_shape_when_no_organization(monkeypatch):
    """Users without an org get a stable empty payload — not an error."""
    user = SimpleNamespace(organization_id=None)

    result = await get_team_strengths(user=user)

    assert result == {
        "computed_at": None,
        "strengths": [],
        "weaknesses": [],
        "bus_factor": [],
        "top_members": [],
    }


@pytest.mark.asyncio
async def test_returns_empty_shape_when_org_has_no_snapshot(monkeypatch):
    """Before the nightly job has run, strengths_weaknesses_json is {}."""
    org = SimpleNamespace(id="org-1", strengths_weaknesses_json={})
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = org
    db.query.return_value = q

    monkeypatch.setattr("app.routers.insights._get_db", lambda: db)
    user = SimpleNamespace(organization_id="org-1")

    result = await get_team_strengths(user=user)

    assert result == {
        "computed_at": None,
        "strengths": [],
        "weaknesses": [],
        "bus_factor": [],
        "top_members": [],
    }
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_returns_snapshot_payload_unchanged(monkeypatch):
    snapshot = {
        "computed_at": "2026-04-23T03:30:00+00:00",
        "organization_id": "org-1",
        "strengths": [{"topic": "api", "count": 10, "contributors": 3}],
        "weaknesses": [{"topic": "legacy", "prior_count": 6, "current_count": 0}],
        "bus_factor": [{"topic": "billing", "sole_expert_name": "Alice", "count": 5}],
        "top_members": [{"member_id": "m1", "name": "Alice", "count": 20}],
    }
    org = SimpleNamespace(id="org-1", strengths_weaknesses_json=snapshot)

    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = org
    db.query.return_value = q

    monkeypatch.setattr("app.routers.insights._get_db", lambda: db)
    user = SimpleNamespace(organization_id="org-1")

    result = await get_team_strengths(user=user)

    assert result["computed_at"] == "2026-04-23T03:30:00+00:00"
    assert result["strengths"] == snapshot["strengths"]
    assert result["weaknesses"] == snapshot["weaknesses"]
    assert result["bus_factor"] == snapshot["bus_factor"]
    assert result["top_members"] == snapshot["top_members"]


@pytest.mark.asyncio
async def test_missing_org_row_still_returns_empty_shape(monkeypatch):
    """If the org ID resolves to no row (edge case), don't 500 — empty payload."""
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    monkeypatch.setattr("app.routers.insights._get_db", lambda: db)
    user = SimpleNamespace(organization_id="org-ghost")

    result = await get_team_strengths(user=user)

    assert result == {
        "computed_at": None,
        "strengths": [],
        "weaknesses": [],
        "bus_factor": [],
        "top_members": [],
    }
