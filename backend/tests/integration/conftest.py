"""Integration test fixtures — uses a real PostgreSQL database.

Requires CB_DATABASE_URL and CB_MIGRATION_DATABASE_URL to be set (CI provides them).
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _db_url() -> str:
    url = os.environ.get("CB_DATABASE_URL", "")
    if not url:
        pytest.skip("CB_DATABASE_URL not set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def db_engine():
    """Single engine for the entire integration test session."""
    engine = create_engine(_db_url(), pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def SessionFactory(db_engine):
    return sessionmaker(bind=db_engine, autocommit=False, autoflush=False)


@pytest.fixture
def db_session(SessionFactory):
    """Per-test database session, rolled back after each test."""
    session = SessionFactory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(db_engine):
    """Run Alembic migrations once before integration tests."""
    import subprocess
    import sys

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Alembic migration failed:\n{result.stdout}\n{result.stderr}")


@pytest.fixture(scope="session")
def app_settings():
    from app.config import Settings

    return Settings(
        jwt_secret="integration-test-secret-32-chars-min",
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
        database_url=_db_url(),
        migration_database_url=os.environ.get("CB_MIGRATION_DATABASE_URL", _db_url()),
        llm_provider="ollama",
        dev_mode=False,
    )


@pytest.fixture(scope="session")
def app_client(app_settings):
    """TestClient with the real FastAPI app connected to the CI database."""
    from unittest.mock import patch

    from app.db.database import init_db
    from app.main import app

    # Patch init_db to skip running migrations again (already done above)
    with patch("app.db.database._run_alembic_migrations"):
        init_db(settings=app_settings)

    # Disable the global per-IP rate limiter for the entire integration
    # session. TestClient uses a single host ("testclient") so all tests
    # share one bucket — without this they'd start 429ing after request
    # 60. The per-route auth limiter (auth.py) is cleared per-test below.
    app.state.rate_limit_enabled = False

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limiters before each test to prevent 429 errors.

    Two separate in-memory buckets exist: one in ``app.routers.auth`` for
    login/password endpoints (per-route, IP-keyed), and one in
    ``app.services.redis_service`` for the global RateLimitMiddleware
    fallback path. Both must be reset so a noisy test doesn't poison the
    next one when Redis isn't running in CI."""
    from app.routers.auth import _memory_rate_limits
    from app.services import redis_service

    _memory_rate_limits.clear()
    if hasattr(redis_service, "_memory_rate"):
        redis_service._memory_rate.clear()
    yield
    _memory_rate_limits.clear()


@pytest.fixture(scope="session")
def registered_user(app_client):
    """Pre-register a test user and return (user_data, auth_token). Session-scoped to avoid rate limits."""
    # Clear rate limits before registration
    from app.routers.auth import _memory_rate_limits

    _memory_rate_limits.clear()

    resp = app_client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@test.example",
            "password": "StrongP@ss1",
            "display_name": "Alice Test",
        },
    )
    # Accept 201 (created) or 409 (already exists from a previous test run)
    assert resp.status_code in (201, 409), f"Unexpected: {resp.status_code} {resp.text}"

    if resp.status_code == 409:
        _memory_rate_limits.clear()
        login = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "StrongP@ss1",
            },
        )
        assert login.status_code == 200, f"Login failed: {login.text}"
        data = login.json()
    else:
        data = resp.json()

    token = data.get("token") or data.get("access_token", "")
    return {"token": token, "user": data.get("user", {})}


@pytest.fixture
def auth_headers(registered_user):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {registered_user['token']}"}


@pytest.fixture(scope="session")
def second_user(app_client):
    """Register a second user for access control tests. Session-scoped."""
    from app.routers.auth import _memory_rate_limits

    _memory_rate_limits.clear()

    resp = app_client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "email": "bob@test.example",
            "password": "StrongP@ss1",
            "display_name": "Bob Test",
        },
    )
    if resp.status_code == 409:
        _memory_rate_limits.clear()
        login = app_client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "StrongP@ss1"},
        )
        assert login.status_code == 200
        data = login.json()
    else:
        assert resp.status_code == 201
        data = resp.json()

    token = data.get("token") or data.get("access_token", "")
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user": data.get("user", {}),
    }
