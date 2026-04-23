"""Regression tests for the Signals router.

The production symptom that motivated this file: Pulse > Signals returned
``API error 500: {"detail":"Internal server error","error_ref":"fe26079b",
"error_type":"ProgrammingError"}``.

``ProgrammingError`` from SQLAlchemy means the underlying SQL statement
could not execute — typically because the ``signals`` table does not exist
on the live DB (migration 012 did not apply at container startup on
Supabase). We can't retroactively fix the migration state from code, but we
can stop the tab from 500ing: treat an un-queryable signals table the same
as an empty one.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

from app.routers.signals import list_signals


@pytest.mark.asyncio
async def test_list_signals_returns_empty_when_table_missing(monkeypatch):
    """If the signals table is absent (ProgrammingError), the endpoint must
    degrade to an empty list rather than 500ing the whole Pulse tab."""
    db = MagicMock()

    # Any call chain starting with db.query(Signal) should blow up exactly
    # like Supabase does when the relation is missing.
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.side_effect = ProgrammingError("SELECT 1", {}, Exception("relation signals does not exist"))
    db.query.return_value = q

    monkeypatch.setattr("app.routers.signals._get_db", lambda: db)

    user = SimpleNamespace(organization_id="org-1", id="u-1")
    request = MagicMock()

    result = await list_signals(request=request, status="open", limit=50, user=user)

    assert result == {"signals": [], "count": 0}
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_list_signals_happy_path_returns_serialized_rows(monkeypatch):
    """Sanity: when the table exists and has rows, the original shape is kept."""
    from datetime import UTC, datetime

    row = SimpleNamespace(
        id="s-1",
        organization_id="org-1",
        signal_type="slow_lane",
        severity="medium",
        title="Slow lane on api",
        description="",
        evidence={"topic": "api"},
        suggested_action=None,
        dedup_key="slow_lane:api",
        detected_at=datetime(2026, 4, 23, tzinfo=UTC),
        acknowledged_by=None,
        acknowledged_at=None,
        resolved_at=None,
    )

    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = [row]
    db.query.return_value = q

    monkeypatch.setattr("app.routers.signals._get_db", lambda: db)

    user = SimpleNamespace(organization_id="org-1", id="u-1")
    request = MagicMock()

    result = await list_signals(request=request, status="open", limit=50, user=user)

    assert result["count"] == 1
    assert result["signals"][0]["id"] == "s-1"
    assert result["signals"][0]["dedup_key"] == "slow_lane:api"
