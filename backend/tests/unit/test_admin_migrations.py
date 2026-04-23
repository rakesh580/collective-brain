"""Tests for the Alembic diagnostic + run endpoints on the admin router.

These endpoints exist to work around the Supabase-IPv6 migration issue:
the running HF Space container CAN reach the DB, but GitHub Actions
runners cannot. The admin endpoints let a human (or automation with an
admin token) trigger ``alembic upgrade head`` from inside the live
container.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.routers.admin import (
    _alembic_current_revision,
    alembic_version,
    apply_migrations,
)


def test_alembic_current_revision_reads_table():
    """Happy path: alembic_version table exists and has one row."""
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = ("012_signals",)
    assert _alembic_current_revision(db) == "012_signals"


def test_alembic_current_revision_returns_none_when_table_missing():
    """If alembic_version is absent (pristine DB), return None rather than raise."""
    db = MagicMock()
    db.execute.side_effect = Exception("relation alembic_version does not exist")
    assert _alembic_current_revision(db) is None


def test_alembic_current_revision_returns_none_when_empty_table():
    """If the table exists but has no row, return None (DB never migrated)."""
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    assert _alembic_current_revision(db) is None


@pytest.mark.asyncio
async def test_alembic_version_endpoint_reports_drift(monkeypatch):
    """Endpoint should return current, head, and at_head computed correctly."""
    request = MagicMock()
    request.headers.get.return_value = "Bearer fake"

    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    db = MagicMock()
    db.execute.return_value.fetchone.return_value = ("011_digest_log",)
    monkeypatch.setattr("app.routers.admin.create_session", lambda: db)
    monkeypatch.setattr("app.routers.admin._alembic_head_revision", lambda: "013_org_strengths_weaknesses")

    result = await alembic_version(request=request)

    assert result == {
        "current": "011_digest_log",
        "head": "013_org_strengths_weaknesses",
        "at_head": False,
    }
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_alembic_version_endpoint_at_head(monkeypatch):
    request = MagicMock()
    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    db = MagicMock()
    db.execute.return_value.fetchone.return_value = ("013_org_strengths_weaknesses",)
    monkeypatch.setattr("app.routers.admin.create_session", lambda: db)
    monkeypatch.setattr("app.routers.admin._alembic_head_revision", lambda: "013_org_strengths_weaknesses")

    result = await alembic_version(request=request)
    assert result["at_head"] is True


@pytest.mark.asyncio
async def test_apply_migrations_runs_upgrade_and_reports_success(monkeypatch):
    """Happy path: upgrade completes, current revision advances to head."""
    request = MagicMock()
    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    revisions = iter(["011_digest_log", "013_org_strengths_weaknesses"])

    def fake_current(db):
        return next(revisions)

    monkeypatch.setattr("app.routers.admin._alembic_current_revision", fake_current)
    monkeypatch.setattr("app.routers.admin._alembic_head_revision", lambda: "013_org_strengths_weaknesses")
    monkeypatch.setattr("app.routers.admin.create_session", lambda: MagicMock())

    # Mock out the real Alembic runner so the test is isolated.
    with patch("app.db.database._run_alembic_migrations") as runner:
        result = await apply_migrations(request=request)
        runner.assert_called_once()

    assert result["status"] == "ok"
    assert result["before"] == "011_digest_log"
    assert result["after"] == "013_org_strengths_weaknesses"
    assert result["at_head"] is True
    assert result["error"] is None


@pytest.mark.asyncio
async def test_apply_migrations_reports_error_without_crashing(monkeypatch):
    """If Alembic raises, the endpoint still returns a useful JSON body with
    the error message — it never 500s, because the caller needs to see why."""
    request = MagicMock()
    monkeypatch.setattr(
        "app.routers.admin._require_admin",
        lambda r: SimpleNamespace(id="u-1", role="admin"),
    )

    monkeypatch.setattr("app.routers.admin._alembic_current_revision", lambda db: "011_digest_log")
    monkeypatch.setattr("app.routers.admin._alembic_head_revision", lambda: "013_org_strengths_weaknesses")
    monkeypatch.setattr("app.routers.admin.create_session", lambda: MagicMock())

    def boom(settings):
        raise RuntimeError("connection timeout")

    with patch("app.db.database._run_alembic_migrations", side_effect=boom):
        result = await apply_migrations(request=request)

    assert result["status"] == "error"
    assert "connection timeout" in result["error"]
    assert result["before"] == "011_digest_log"
