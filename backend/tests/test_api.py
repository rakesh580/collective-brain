import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    # Use test-specific data directory
    os.environ["CB_SQLITE_URL"] = "sqlite:///./data/test_brain.db"
    os.environ["CB_CHROMA_PERSIST_DIR"] = "./data/test_chroma"
    os.environ["CB_LLM_PROVIDER"] = "ollama"

    from app.main import app

    with TestClient(app) as c:
        yield c

    # Cleanup
    import shutil
    for path in ["./data/test_brain.db", "./data/test_chroma"]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "embedding_model" in data


class TestIngestEndpoint:
    def test_ingest_markdown(self, client):
        resp = client.post(
            "/ingest/markdown",
            json={"directory_path": str(FIXTURES_DIR)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "markdown"
        assert data["status"] == "completed"
        assert data["chunk_count"] > 0


class TestMembersEndpoint:
    def test_list_members(self, client):
        # Ingest first to populate members
        client.post(
            "/ingest/markdown",
            json={"directory_path": str(FIXTURES_DIR)},
        )
        resp = client.get("/members")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestGraphEndpoint:
    def test_full_graph(self, client):
        resp = client.get("/graph/full")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


class TestDashboardEndpoint:
    def test_dashboard(self, client):
        resp = client.get("/insights/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_members" in data
        assert "total_artifacts" in data
        assert "total_chunks" in data
