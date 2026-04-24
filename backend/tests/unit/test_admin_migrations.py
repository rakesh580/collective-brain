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
    _verify_bootstrap_token,
    alembic_version,
    apply_migrations,
    bootstrap_migrations,
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


# ── Bootstrap endpoint (token-gated) ──────────────────────────────────────


def test_verify_bootstrap_token_rejects_when_env_unset(monkeypatch):
    """When CB_BOOTSTRAP_TOKEN is unset, the endpoint is disabled (503)."""
    from fastapi import HTTPException

    monkeypatch.delenv("CB_BOOTSTRAP_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _verify_bootstrap_token("anything")
    assert exc.value.status_code == 503
    assert "not enabled" in exc.value.detail.lower()


def test_verify_bootstrap_token_rejects_empty_header(monkeypatch):
    """Env set but caller didn't send the header → 401."""
    from fastapi import HTTPException

    monkeypatch.setenv("CB_BOOTSTRAP_TOKEN", "secret-123")
    with pytest.raises(HTTPException) as exc:
        _verify_bootstrap_token(None)
    assert exc.value.status_code == 401


def test_verify_bootstrap_token_rejects_wrong_token(monkeypatch):
    """Wrong token → 401."""
    from fastapi import HTTPException

    monkeypatch.setenv("CB_BOOTSTRAP_TOKEN", "secret-123")
    with pytest.raises(HTTPException) as exc:
        _verify_bootstrap_token("not-the-secret")
    assert exc.value.status_code == 401


def test_verify_bootstrap_token_accepts_match(monkeypatch):
    """Correct token → no exception."""
    monkeypatch.setenv("CB_BOOTSTRAP_TOKEN", "secret-123")
    _verify_bootstrap_token("secret-123")  # Must not raise


@pytest.mark.asyncio
async def test_bootstrap_migrations_runs_upgrade_when_token_valid(monkeypatch):
    """Happy path: valid token → Alembic runs → revision advances."""
    request = MagicMock()
    request.client.host = "10.0.0.1"

    monkeypatch.setenv("CB_BOOTSTRAP_TOKEN", "secret-xyz")

    revisions = iter(["008_decision_outcomes_notifications", "013_org_strengths_weaknesses"])
    monkeypatch.setattr("app.routers.admin._alembic_current_revision", lambda db: next(revisions))
    monkeypatch.setattr("app.routers.admin._alembic_head_revision", lambda: "013_org_strengths_weaknesses")
    monkeypatch.setattr("app.routers.admin.create_session", lambda: MagicMock())

    with patch("app.db.database._run_alembic_migrations") as runner:
        result = await bootstrap_migrations(request=request, x_bootstrap_token="secret-xyz")
        runner.assert_called_once()

    assert result["status"] == "ok"
    assert result["before"] == "008_decision_outcomes_notifications"
    assert result["after"] == "013_org_strengths_weaknesses"
    assert result["at_head"] is True


@pytest.mark.asyncio
async def test_bootstrap_migrations_rejects_invalid_token(monkeypatch):
    """Invalid token → 401 before any DB work happens."""
    from fastapi import HTTPException

    request = MagicMock()
    monkeypatch.setenv("CB_BOOTSTRAP_TOKEN", "secret-xyz")

    db_called = {"n": 0}

    def tracking_create_session():
        db_called["n"] += 1
        return MagicMock()

    monkeypatch.setattr("app.routers.admin.create_session", tracking_create_session)

    with pytest.raises(HTTPException) as exc:
        await bootstrap_migrations(request=request, x_bootstrap_token="wrong")
    assert exc.value.status_code == 401
    # Guard-rail: DB session must NOT be opened when auth fails.
    assert db_called["n"] == 0


@pytest.mark.asyncio
async def test_bootstrap_migrations_returns_503_when_env_unset(monkeypatch):
    """Env unset → 503 even with a header present. Default-safe."""
    from fastapi import HTTPException

    request = MagicMock()
    monkeypatch.delenv("CB_BOOTSTRAP_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        await bootstrap_migrations(request=request, x_bootstrap_token="whatever")
    assert exc.value.status_code == 503
