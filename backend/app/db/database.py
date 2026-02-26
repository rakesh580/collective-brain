import logging
import os

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

        # Ensure the directory for the SQLite file exists (important for
        # HuggingFace Spaces persistent volume at /data).
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "", 1)
            abs_db_path = os.path.abspath(db_path)
            db_dir = os.path.dirname(abs_db_path)
            os.makedirs(db_dir, exist_ok=True)

            # Diagnostic: log whether the database file already exists
            if os.path.exists(abs_db_path):
                size_kb = os.path.getsize(abs_db_path) / 1024
                logger.info("SQLite file found: %s (%.1f KB)", abs_db_path, size_kb)
            else:
                logger.warning("SQLite file does NOT exist yet: %s (will be created)", abs_db_path)

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
            cursor.execute("PRAGMA synchronous=FULL")
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

        # Backfill owner_user_id for legacy conversations (assign from first message sender)
        if "conversations" in tables and "messages" in tables:
            migrated = conn.execute(text(
                "UPDATE conversations SET owner_user_id = ("
                "  SELECT m.sender_user_id FROM messages m"
                "  WHERE m.conversation_id = conversations.id"
                "  AND m.sender_user_id IS NOT NULL"
                "  ORDER BY m.created_at ASC LIMIT 1"
                ") WHERE owner_user_id IS NULL"
            ))
            if migrated.rowcount > 0:
                logger.info("Migration: backfilled owner_user_id for %d legacy conversations", migrated.rowcount)

        # Add unique constraint on conversation_participants(conversation_id, user_id)
        if "conversation_participants" in tables:
            is_pg = engine.url.get_backend_name() == "postgresql"
            existing_constraints = inspector.get_unique_constraints("conversation_participants")
            constraint_names = [c["name"] for c in existing_constraints]
            if "uq_participant_conv_user" not in constraint_names:
                try:
                    if is_pg:
                        conn.execute(text(
                            "ALTER TABLE conversation_participants "
                            "ADD CONSTRAINT uq_participant_conv_user UNIQUE (conversation_id, user_id)"
                        ))
                    else:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_participant_conv_user "
                            "ON conversation_participants (conversation_id, user_id)"
                        ))
                    logger.info("Migration: added unique constraint on conversation_participants(conversation_id, user_id)")
                except Exception as e:
                    logger.warning("Migration: unique constraint already exists or failed: %s", e)

        # Users: google_id, auth_provider, reset_code, reset_code_expires, last_login
        if "users" in tables:
            user_cols = [c["name"] for c in inspector.get_columns("users")]
            if "google_id" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_id TEXT UNIQUE"))
                logger.info("Migration: added users.google_id")
            if "auth_provider" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local'"))
                logger.info("Migration: added users.auth_provider")
            if "reset_code" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_code TEXT"))
                logger.info("Migration: added users.reset_code")
            if "reset_code_expires" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_code_expires TIMESTAMP"))
                logger.info("Migration: added users.reset_code_expires")
            if "last_login" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP"))
                logger.info("Migration: added users.last_login")

        # ChatRooms: is_public
        if "chat_rooms" in tables:
            room_cols = [c["name"] for c in inspector.get_columns("chat_rooms")]
            if "is_public" not in room_cols:
                conn.execute(text("ALTER TABLE chat_rooms ADD COLUMN is_public BOOLEAN DEFAULT 0"))
                logger.info("Migration: added chat_rooms.is_public")

        # Artifacts: room_id
        if "artifacts" in tables:
            art_cols = [c["name"] for c in inspector.get_columns("artifacts")]
            if "room_id" not in art_cols:
                conn.execute(text("ALTER TABLE artifacts ADD COLUMN room_id TEXT"))
                logger.info("Migration: added artifacts.room_id")

        # Contributions: room_id
        if "contributions" in tables:
            contrib_cols = [c["name"] for c in inspector.get_columns("contributions")]
            if "room_id" not in contrib_cols:
                conn.execute(text("ALTER TABLE contributions ADD COLUMN room_id TEXT"))
                logger.info("Migration: added contributions.room_id")

        # Conversations: room_id
        if "conversations" in tables:
            conv_cols2 = [c["name"] for c in inspector.get_columns("conversations")]
            if "room_id" not in conv_cols2:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN room_id TEXT"))
                logger.info("Migration: added conversations.room_id")

        # Discussion threads: room_id
        if "discussion_threads" in tables:
            disc_cols = [c["name"] for c in inspector.get_columns("discussion_threads")]
            if "room_id" not in disc_cols:
                conn.execute(text("ALTER TABLE discussion_threads ADD COLUMN room_id TEXT"))
                logger.info("Migration: added discussion_threads.room_id")

        # Insights: room_id
        if "insights" in tables:
            ins_cols = [c["name"] for c in inspector.get_columns("insights")]
            if "room_id" not in ins_cols:
                conn.execute(text("ALTER TABLE insights ADD COLUMN room_id TEXT"))
                logger.info("Migration: added insights.room_id")

        conn.commit()

    # Flush WAL to main DB file so data survives unclean container shutdowns
    is_sqlite = not engine.url.get_backend_name() == "postgresql"
    if is_sqlite:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            conn.commit()
            logger.info("SQLite WAL checkpoint completed")

    # Log user count to help verify database persistence across restarts
    with engine.connect() as conn:
        if "users" in tables:
            count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if count == 0:
                logger.warning("Database has 0 users — data may have been lost on restart!")
            else:
                logger.info("Database has %d registered user(s) (data persisted OK)", count)


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
