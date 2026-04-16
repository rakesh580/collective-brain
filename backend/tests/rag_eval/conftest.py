"""RAG evaluation test fixtures.

Precision/recall tests use a real VectorStoreService (requires CB_DATABASE_URL).
Hallucination/groundedness tests use the full app via app_client.
"""

import os
from unittest.mock import MagicMock

import pytest

# Integration fixtures for tests that need app_client, auth_headers, etc.
from tests.integration.conftest import (  # noqa: F401
    SessionFactory,
    _clear_rate_limits,
    _run_migrations,
    app_client,
    app_settings,
    auth_headers,
    db_engine,
    db_session,
    registered_user,
    second_user,
)


def _requires_db():
    url = os.environ.get("CB_DATABASE_URL", "")
    if not url or "unused" in url:
        pytest.skip("CB_DATABASE_URL not set — skipping database-backed test")


@pytest.fixture
def mock_embedder():
    """Mock embedder that returns valid 384-dimensional embeddings."""
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 384
    embedder.embed_batch.return_value = [[0.1] * 384]
    return embedder


@pytest.fixture
def vector_store():
    """VectorStoreService backed by a real PostgreSQL session."""
    _requires_db()
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.services.vector_store import VectorStoreService

    url = os.environ["CB_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    conn = engine.connect()
    trans = conn.begin()
    Session = sessionmaker(bind=conn)
    session = Session()

    def _factory():
        return sessionmaker(bind=conn)()

    svc = VectorStoreService(_factory)
    session.execute(text("DELETE FROM knowledge_embeddings"))
    session.execute(
        text(
            "INSERT INTO artifacts (id, source_type, source_path, title, ingested_at, chunk_count, member_ids) "
            "VALUES (:id, :st, :sp, :t, now(), 0, '[]') ON CONFLICT (id) DO NOTHING"
        ),
        [
            {"id": "a1", "st": "test", "sp": "/test/a1", "t": "Test Artifact 1"},
            {"id": "a2", "st": "test", "sp": "/test/a2", "t": "Test Artifact 2"},
            {"id": "a3", "st": "test", "sp": "/test/a3", "t": "Test Artifact 3"},
        ],
    )
    session.commit()
    svc._cached_count = None

    yield svc

    session.close()
    trans.rollback()
    conn.close()
    engine.dispose()
