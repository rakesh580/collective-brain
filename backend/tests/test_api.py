import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def _test_db_dir():
    """Create and clean up a temp directory for the test database."""
    d = tempfile.mkdtemp(prefix="cb_test_api_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="module")
def client(_test_db_dir):
    # Force a fresh SQLite database in the temp directory by overriding database_url
    # to something that will fail, triggering the SQLite fallback. But we need to
    # control the fallback path. Instead, patch init_db to use our temp dir.
    import app.db.database as db_mod

    orig_init = db_mod.init_db

    def patched_init_db(settings=None):
        """Force SQLite in the temp directory instead of the default dev.db path."""
        if settings is None:
            from app.config import get_settings

            settings = get_settings()

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import app.models  # noqa: F401

        sqlite_path = os.path.join(_test_db_dir, "test_brain.db")
        sqlite_url = f"sqlite:///{sqlite_path}"
        db_mod._engine = create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        db_mod._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_mod._engine)
        db_mod.Base.metadata.create_all(bind=db_mod._engine)

    # Monkey-patch init_db before the app lifespan runs
    db_mod.init_db = patched_init_db

    os.environ["CB_LLM_PROVIDER"] = "ollama"

    from app.main import app

    with TestClient(app) as c:
        yield c

    # Restore
    db_mod.init_db = orig_init


@pytest.fixture(scope="module")
def auth_token(client):
    """Register a test user and return a valid auth token."""
    from app.routers.auth import _memory_rate_limits

    _memory_rate_limits.clear()

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "testuser@test.example",
            "password": "StrongP@ss1",
            "display_name": "Test User",
        },
    )
    assert resp.status_code == 201, f"Register failed: {resp.status_code} {resp.text}"
    data = resp.json()
    return data.get("token") or data.get("access_token", "")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "embedding_model" in data


class TestIngestEndpoint:
    def test_ingest_markdown(self, client, auth_headers):
        resp = client.post(
            "/api/v1/ingest/markdown",
            json={"directory_path": str(FIXTURES_DIR)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "markdown"
        assert data["status"] == "completed"
        assert data["chunk_count"] > 0


class TestMembersEndpoint:
    def test_list_members(self, client, auth_headers):
        # Ingest first to populate members
        client.post(
            "/api/v1/ingest/markdown",
            json={"directory_path": str(FIXTURES_DIR)},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/members", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Endpoint returns {"members": [...], "total": N}
        assert "members" in data
        assert isinstance(data["members"], list)


class TestGraphEndpoint:
    def test_full_graph(self, client, auth_headers):
        resp = client.get("/api/v1/graph/full", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


class TestDashboardEndpoint:
    def test_dashboard(self, client, auth_headers):
        resp = client.get("/api/v1/insights/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_members" in data
        assert "total_artifacts" in data
        assert "total_chunks" in data
