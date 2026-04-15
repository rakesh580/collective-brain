"""Unit test fixtures — no real DB required for most tests.

VectorStoreService tests use a real PostgreSQL connection when CB_DATABASE_URL
is set (CI environment). If not set, those tests are skipped automatically.
"""
import os
import pytest
from unittest.mock import MagicMock

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
    """Real PostgreSQL session for unit tests that need it."""
    _requires_db()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.environ["CB_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.rollback()   # Roll back after each test — keeps DB clean
    finally:
        session.close()
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
    db_session.commit()
    svc._cached_count = None
    return svc
