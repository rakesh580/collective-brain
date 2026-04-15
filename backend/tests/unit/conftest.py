"""Unit test fixtures — no real DB required for most tests.

VectorStoreService tests use a real PostgreSQL connection when CB_DATABASE_URL
is set (CI environment). If not set, those tests are skipped automatically.
"""

import os
from unittest.mock import MagicMock

import pytest

from app.config import Settings


@pytest.fixture
def settings():
    return Settings(
        jwt_secret="unit-test-secret-key-minimum-32-chars",
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
        google_client_id="test-google-client-id",
        database_url=os.environ.get("CB_DATABASE_URL", "postgresql://unused:unused@localhost/unused"),
    )


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory for tests that need filesystem isolation."""
    return str(tmp_path)


# ── VectorStore fixtures ──────────────────────────────────────────────────────


def _requires_db():
    """Skip if no real database is available."""
    url = os.environ.get("CB_DATABASE_URL", "")
    if not url or "unused" in url:
        pytest.skip("CB_DATABASE_URL not set — skipping database-backed test")


@pytest.fixture
def db_session():
    """Real PostgreSQL session for unit tests — uses nested transaction for isolation."""
    _requires_db()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.environ["CB_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    conn = engine.connect()
    trans = conn.begin()
    Session = sessionmaker(bind=conn)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()  # Roll back everything — each test gets clean slate
        conn.close()
        engine.dispose()


@pytest.fixture
def vector_store(db_session):
    """VectorStoreService backed by a real PostgreSQL session."""
    _requires_db()
    from app.services.vector_store import VectorStoreService

    def _factory():
        from sqlalchemy.orm import sessionmaker

        maker = sessionmaker(bind=db_session.get_bind())
        return maker()

    svc = VectorStoreService(_factory)
    # Clean slate — remove any leftover rows from previous runs
    from sqlalchemy import text

    db_session.execute(text("DELETE FROM knowledge_embeddings"))
    # Ensure parent artifacts exist for FK references in tests
    db_session.execute(
        text(
            "INSERT INTO artifacts (id, source_type, source_path, title, ingested_at, chunk_count, member_ids) "
            "VALUES (:id, :st, :sp, :t, now(), 0, '[]') ON CONFLICT (id) DO NOTHING"
        ),
        [
            {"id": "a1", "st": "test", "sp": "/test/a1", "t": "Test Artifact 1"},
            {"id": "a2", "st": "test", "sp": "/test/a2", "t": "Test Artifact 2"},
            {"id": "a3", "st": "test", "sp": "/test/a3", "t": "Test Artifact 3"},
            {"id": "art-1", "st": "test", "sp": "/test/art1", "t": "Test Artifact Art1"},
            {"id": "art-2", "st": "test", "sp": "/test/art2", "t": "Test Artifact Art2"},
        ],
    )
    db_session.commit()
    svc._cached_count = None
    return svc


# ── Seed data fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def seed_members(db_session):
    """Insert test members into the DB for graph/insight tests."""
    from sqlalchemy import text

    db_session.execute(text("DELETE FROM contributions"))
    db_session.execute(text("DELETE FROM members"))
    for m in [
        {"id": "alice", "name": "Alice", "email": "alice@test.com"},
        {"id": "bob", "name": "Bob", "email": "bob@test.com"},
    ]:
        db_session.execute(
            text(
                "INSERT INTO members (id, name, email, aliases, expertise_tags, expertise_scores, strengths, weaknesses) "
                "VALUES (:id, :name, :email, '[]', '[\"python\",\"api\"]', '{}', '[]', '[]') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            m,
        )
    db_session.commit()
    return ["alice", "bob"]


@pytest.fixture
def seed_artifacts(db_session, seed_members):
    """Insert test artifacts and contributions for graph/insight tests."""
    import json

    from sqlalchemy import text

    db_session.execute(text("DELETE FROM artifacts"))
    for a in [
        {"id": "a1", "st": "git", "sp": "/repo", "t": "API Code", "mids": json.dumps(["alice", "bob"])},
        {"id": "a2", "st": "markdown", "sp": "/docs", "t": "Docs", "mids": json.dumps(["alice"])},
    ]:
        db_session.execute(
            text(
                "INSERT INTO artifacts (id, source_type, source_path, title, ingested_at, chunk_count, member_ids) "
                "VALUES (:id, :st, :sp, :t, now(), 5, :mids) ON CONFLICT (id) DO NOTHING"
            ),
            a,
        )
    # Add contributions
    for c in [
        {
            "id": "c1",
            "mid": "alice",
            "aid": "a1",
            "ct": "git_commit",
            "desc": "Added API endpoints",
            "topics": json.dumps(["python", "api"]),
        },
        {
            "id": "c2",
            "mid": "bob",
            "aid": "a1",
            "ct": "git_commit",
            "desc": "Fixed bugs",
            "topics": json.dumps(["python", "debugging"]),
        },
        {
            "id": "c3",
            "mid": "alice",
            "aid": "a2",
            "ct": "documentation",
            "desc": "Wrote API docs",
            "topics": json.dumps(["api", "docs"]),
        },
    ]:
        db_session.execute(
            text(
                "INSERT INTO contributions (id, member_id, artifact_id, contribution_type, description, topics, timestamp) "
                "VALUES (:id, :mid, :aid, :ct, :desc, :topics, now()) ON CONFLICT (id) DO NOTHING"
            ),
            c,
        )
    db_session.commit()
    return ["a1", "a2"]
