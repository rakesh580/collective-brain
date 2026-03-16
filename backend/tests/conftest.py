"""Shared test fixtures for the Collective Brain test suite."""

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# ---------------------------------------------------------------------------
# Environment: force test settings before any app import
# ---------------------------------------------------------------------------
os.environ.setdefault("CB_LLM_PROVIDER", "ollama")
os.environ.setdefault("CB_JWT_SECRET", "test-secret-for-unit-tests")
os.environ.setdefault("CB_JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("CB_REDIS_URL", "")  # force in-memory fallback


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def tmp_dir():
    """Provide a temporary directory, cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="cb_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def db_session(tmp_dir):
    """Create an isolated SQLite database session for testing."""
    from app.db.database import Base

    db_path = os.path.join(tmp_dir, "test.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def db_engine(tmp_dir):
    """Return a raw engine for migration / DDL tests."""
    from app.db.database import Base

    db_path = os.path.join(tmp_dir, "test_engine.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# Settings fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def settings():
    """Return a Settings instance pointed at test defaults."""
    from app.config import Settings

    return Settings(
        llm_provider="ollama",
        jwt_secret="test-secret-for-unit-tests",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        redis_url="",
        database_url="",
        sqlite_url="sqlite:///./data/test_cb.db",
        chunk_size=128,
        chunk_overlap=16,
        google_client_id="",
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def auth_service(settings):
    from app.services.auth_service import AuthService

    return AuthService(settings)


@pytest.fixture()
def sample_user(db_session, auth_service):
    """Register a sample user and return the UserRecord."""
    user = auth_service.register(
        db_session, "testuser", "test@example.com", "Password123!", "Test User"
    )
    return user


@pytest.fixture()
def auth_token(auth_service, sample_user):
    """Return a valid JWT token for the sample user."""
    return auth_service.create_token(sample_user.id)


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_llm():
    """Mock LLM service that returns a deterministic response."""
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value="Based on the team's data, Alice is the best person for this task."
    )
    llm.is_available = MagicMock(return_value=True)
    return llm


@pytest.fixture()
def mock_embedder():
    """Mock embedding service that returns fixed-dimension vectors."""
    embedder = MagicMock()
    embedder.embed = MagicMock(return_value=[0.1] * 384)
    embedder.embed_batch = MagicMock(
        side_effect=lambda texts, **kw: [[0.1] * 384 for _ in texts]
    )
    return embedder


@pytest.fixture()
def vector_store(tmp_dir):
    """Real ChromaDB vector store in a temp directory."""
    from app.services.vector_store import VectorStoreService

    return VectorStoreService(os.path.join(tmp_dir, "chroma"))


@pytest.fixture()
def redis_service():
    """In-memory Redis service (no actual Redis required)."""
    from app.services.redis_service import RedisService

    return RedisService(redis_url="")


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture()
def app_client(tmp_dir, mock_llm, mock_embedder):
    """
    Full FastAPI TestClient with mocked heavy services.

    The database is a temp SQLite; LLM and embedder are mocked so tests
    don't need GPU or network access.
    """
    db_path = os.path.join(tmp_dir, "app_test.db")
    chroma_dir = os.path.join(tmp_dir, "chroma")

    os.environ["CB_SQLITE_URL"] = f"sqlite:///{db_path}"
    os.environ["CB_CHROMA_PERSIST_DIR"] = chroma_dir
    os.environ["CB_DATABASE_URL"] = ""
    os.environ["CB_REDIS_URL"] = ""
    os.environ["CB_JWT_SECRET"] = "test-secret-for-unit-tests"

    from app.config import Settings

    # Reset cached settings
    import app.config as cfg
    cfg._settings = None

    from app.db.database import init_db, Base
    from app.services.vector_store import VectorStoreService
    from app.services.redis_service import RedisService
    from app.main import app

    settings = Settings(
        database_url="",
        sqlite_url=f"sqlite:///{db_path}",
        chroma_persist_dir=chroma_dir,
        redis_url="",
        jwt_secret="test-secret-for-unit-tests",
        rate_limit_requests=10000,
        rate_limit_ai_requests=10000,
        google_client_id="",
    )
    cfg._settings = settings
    init_db(settings=settings)

    # Use context manager to ensure proper lifespan start/stop between tests
    with TestClient(app, raise_server_exceptions=False) as client:
        # Override app state AFTER lifespan has run
        app.state.settings = settings
        app.state.embedding_service = mock_embedder
        app.state.vector_store = VectorStoreService(chroma_dir)
        app.state.llm_service = mock_llm
        # Set redis to None to disable rate limiting in tests.
        # Tests that specifically need rate-limit behaviour should set
        # app.state.redis = RedisService("") themselves.
        app.state.redis = None

        yield client

    # Cleanup
    cfg._settings = None


@pytest.fixture()
def registered_user(app_client):
    """Register a user via the API and return (user_dict, token)."""
    resp = app_client.post(
        "/auth/register",
        json={
            "username": "alice",
            "email": "alice@test.com",
            "password": "Str0ngPass!",
            "display_name": "Alice",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["user"], data["token"]


@pytest.fixture()
def auth_headers(registered_user):
    """Return Authorization headers for the registered user."""
    _, token = registered_user
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Seed data helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def seed_members(db_session):
    """Insert sample members into the database."""
    from app.models.member import MemberRecord

    members = []
    for name in ["alice", "bob", "charlie"]:
        m = MemberRecord(
            id=name,
            name=name.capitalize(),
            aliases=[name, f"{name}@company.com"],
            email=f"{name}@company.com",
            expertise_tags=["python", "fastapi"] if name == "alice" else ["react", "typescript"],
            total_contributions=10,
            last_active=datetime.now(timezone.utc) - timedelta(days=5),
        )
        db_session.add(m)
        members.append(m)
    db_session.commit()
    return members


@pytest.fixture()
def seed_artifacts(db_session, seed_members):
    """Insert sample artifacts and contributions."""
    from app.models.artifact import ArtifactRecord
    from app.models.contribution import ContributionRecord

    artifacts = []
    for i in range(3):
        a = ArtifactRecord(
            id=f"art-{i}",
            source_type="git",
            source_path=f"/repo/commit-{i}",
            title=f"Commit {i}",
            chunk_count=5,
            member_ids=["alice", "bob"],
            status="completed",
        )
        db_session.add(a)
        artifacts.append(a)

        # Add contributions
        for member_id in ["alice", "bob"]:
            c = ContributionRecord(
                id=str(uuid4()),
                member_id=member_id,
                artifact_id=a.id,
                contribution_type="git_content",
                timestamp=datetime.now(timezone.utc) - timedelta(days=i * 10),
                description=f"Commit {i} by {member_id}",
                topics=["python", "api"],
            )
            db_session.add(c)

    db_session.commit()
    return artifacts
