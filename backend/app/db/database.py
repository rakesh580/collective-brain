import logging

from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from typing import Generator

Base = declarative_base()

_engine = None
_SessionLocal = None

logger = logging.getLogger("collective_brain.db")


def init_db(sqlite_url: str = "", settings=None):
    """Initialize database. Supports PostgreSQL (production) and SQLite (dev).

    Args:
        sqlite_url: Legacy param — SQLite connection string.
        settings: Settings object with effective_database_url. Takes priority.
    """
    global _engine, _SessionLocal

    # Determine DB URL
    if settings is not None:
        db_url = settings.effective_database_url
    elif sqlite_url:
        db_url = sqlite_url
    else:
        from app.config import get_settings
        db_url = get_settings().effective_database_url

    is_postgres = db_url.startswith("postgresql")

    if is_postgres:
        logger.info("Using PostgreSQL with connection pooling")
        pool_settings = {}
        if settings:
            pool_settings = {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        else:
            pool_settings = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }

        _engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_pre_ping=True,
            echo=False,
            **pool_settings,
        )
    else:
        logger.info("Using SQLite (development mode)")
        # NullPool: each request gets its own connection — no sharing,
        # no "database is locked" under concurrency.  WAL mode allows
        # concurrent readers while a writer holds the lock.
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=NullPool,
            echo=False,
        )

        # SQLite optimizations — applied per connection
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.close()

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    Base.metadata.create_all(bind=_engine)
    _run_migrations(_engine)

    logger.info("Database initialized (%s)", "PostgreSQL" if is_postgres else "SQLite")


def _run_migrations(engine):
    """Add columns that create_all won't add to existing tables."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.connect() as conn:
        # Conversations: owner_user_id, visibility
        if "conversations" in tables:
            conv_cols = [c["name"] for c in inspector.get_columns("conversations")]
            if "owner_user_id" not in conv_cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN owner_user_id TEXT"))
                logger.info("Migration: added conversations.owner_user_id")
            if "visibility" not in conv_cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN visibility TEXT DEFAULT 'private'"))
                logger.info("Migration: added conversations.visibility")

        # Messages: sender_user_id, sender_name
        if "messages" in tables:
            msg_cols = [c["name"] for c in inspector.get_columns("messages")]
            if "sender_user_id" not in msg_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN sender_user_id TEXT"))
                logger.info("Migration: added messages.sender_user_id")
            if "sender_name" not in msg_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN sender_name TEXT"))
                logger.info("Migration: added messages.sender_name")

        conn.commit()


def get_session() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_engine():
    """Return the SQLAlchemy engine (for health checks)."""
    return _engine
