import os
from unittest.mock import MagicMock

import pytest

from app.config import Settings

# Exclude locust/stress tests from normal pytest collection — they require
# external infrastructure and monkey-patch gevent which crashes on Python 3.11+.
collect_ignore = [
    os.path.join(os.path.dirname(__file__), "load_test.py"),
    os.path.join(os.path.dirname(__file__), "stress_test.py"),
    os.path.join(os.path.dirname(__file__), "collaboration_test.py"),
    os.path.join(os.path.dirname(__file__), "ws_db_test.py"),
]


@pytest.fixture
def settings():
    return Settings(
        jwt_secret="test-secret-key-minimum-32-chars-long",
        jwt_algorithm="HS256",
        jwt_expire_minutes=30,
        google_client_id="test-google-client-id",
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_embedder():
    return MagicMock()


@pytest.fixture
def vector_store():
    return MagicMock()
