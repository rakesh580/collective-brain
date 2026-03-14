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
    _ensure_help_requests_table(_engine)
    _ensure_slack_digest_config_table(_engine)
    _ensure_health_snapshots_table(_engine)

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
                conn.execute(text("ALTER TABLE users ADD COLUMN google_id TEXT"))
                # SQLite doesn't support ADD COLUMN ... UNIQUE, so create index separately
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)"))
                except Exception:
                    pass  # Index may already exist
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
            if "skills" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN skills TEXT DEFAULT '[]'"))
                logger.info("Migration: added users.skills")
            if "role_title" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role_title TEXT"))
                logger.info("Migration: added users.role_title")
            if "bio" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN bio TEXT"))
                logger.info("Migration: added users.bio")

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


def _ensure_help_requests_table(engine):
    """Create the help_requests table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS help_requests (
                id TEXT PRIMARY KEY,
                requester_user_id TEXT NOT NULL,
                expert_member_id TEXT NOT NULL,
                query TEXT NOT NULL,
                topics TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """))
        conn.commit()
    logger.info("Ensured help_requests table exists")


def _ensure_slack_digest_config_table(engine):
    """Create the slack_digest_config table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS slack_digest_config (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_name TEXT DEFAULT '',
                schedule_day INTEGER DEFAULT 0,
                schedule_hour INTEGER DEFAULT 9,
                enabled INTEGER DEFAULT 1,
                last_sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    logger.info("Ensured slack_digest_config table exists")


def save_digest_config(
    db: Session,
    workspace_id: str,
    channel_id: str,
    channel_name: str = "",
    schedule_day: int = 0,
    schedule_hour: int = 9,
    enabled: bool = True,
) -> dict:
    """Insert or update a digest configuration and return it as a dict."""
    import uuid
    from datetime import datetime

    # Check if config already exists for this workspace + channel
    existing = db.execute(
        text(
            "SELECT id FROM slack_digest_config "
            "WHERE workspace_id = :wid AND channel_id = :cid LIMIT 1"
        ),
        {"wid": workspace_id, "cid": channel_id},
    ).fetchone()

    if existing:
        config_id = existing[0]
        db.execute(
            text(
                "UPDATE slack_digest_config SET "
                "channel_name = :channel_name, "
                "schedule_day = :schedule_day, "
                "schedule_hour = :schedule_hour, "
                "enabled = :enabled "
                "WHERE id = :id"
            ),
            {
                "channel_name": channel_name,
                "schedule_day": schedule_day,
                "schedule_hour": schedule_hour,
                "enabled": 1 if enabled else 0,
                "id": config_id,
            },
        )
        db.commit()
    else:
        config_id = str(uuid.uuid4())
        now = datetime.utcnow()
        db.execute(
            text(
                "INSERT INTO slack_digest_config "
                "(id, workspace_id, channel_id, channel_name, schedule_day, "
                "schedule_hour, enabled, created_at) "
                "VALUES (:id, :workspace_id, :channel_id, :channel_name, "
                ":schedule_day, :schedule_hour, :enabled, :created_at)"
            ),
            {
                "id": config_id,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "schedule_day": schedule_day,
                "schedule_hour": schedule_hour,
                "enabled": 1 if enabled else 0,
                "created_at": now,
            },
        )
        db.commit()

    return {
        "id": config_id,
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "schedule_day": schedule_day,
        "schedule_hour": schedule_hour,
        "enabled": enabled,
    }


def get_digest_config(db: Session, workspace_id: str) -> list[dict]:
    """Fetch all digest configurations for a workspace."""
    rows = db.execute(
        text(
            "SELECT id, workspace_id, channel_id, channel_name, schedule_day, "
            "schedule_hour, enabled, last_sent_at, created_at "
            "FROM slack_digest_config WHERE workspace_id = :wid "
            "ORDER BY created_at DESC"
        ),
        {"wid": workspace_id},
    ).fetchall()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "workspace_id": row[1],
            "channel_id": row[2],
            "channel_name": row[3] or "",
            "schedule_day": row[4],
            "schedule_hour": row[5],
            "enabled": bool(row[6]),
            "last_sent_at": row[7].isoformat() if row[7] else None,
            "created_at": row[8].isoformat() if row[8] else None,
        })
    return results


def update_digest_last_sent(db: Session, config_id: str) -> bool:
    """Update the last_sent_at timestamp for a digest config. Returns True if updated."""
    from datetime import datetime

    now = datetime.utcnow()
    result = db.execute(
        text(
            "UPDATE slack_digest_config SET last_sent_at = :now WHERE id = :id"
        ),
        {"now": now, "id": config_id},
    )
    db.commit()
    return result.rowcount > 0


def create_help_request(
    db: Session,
    requester_user_id: str,
    expert_member_id: str,
    query: str,
    topics: list[str] | None = None,
) -> dict:
    """Insert a new help request and return it as a dict."""
    import json
    import uuid
    from datetime import datetime

    request_id = str(uuid.uuid4())
    now = datetime.utcnow()
    topics_json = json.dumps(topics or [])

    db.execute(
        text(
            "INSERT INTO help_requests (id, requester_user_id, expert_member_id, query, topics, status, created_at) "
            "VALUES (:id, :requester_user_id, :expert_member_id, :query, :topics, :status, :created_at)"
        ),
        {
            "id": request_id,
            "requester_user_id": requester_user_id,
            "expert_member_id": expert_member_id,
            "query": query,
            "topics": topics_json,
            "status": "pending",
            "created_at": now,
        },
    )
    db.commit()

    return {
        "id": request_id,
        "requester_user_id": requester_user_id,
        "expert_member_id": expert_member_id,
        "query": query,
        "topics": topics or [],
        "status": "pending",
        "created_at": now,
        "resolved_at": None,
    }


def get_help_requests(
    db: Session,
    user_id: str,
    linked_member_id: str | None = None,
) -> list[dict]:
    """Fetch help requests where the user is requester or the linked expert."""
    import json

    if linked_member_id:
        rows = db.execute(
            text(
                "SELECT id, requester_user_id, expert_member_id, query, topics, "
                "status, created_at, resolved_at FROM help_requests "
                "WHERE requester_user_id = :uid OR expert_member_id = :mid "
                "ORDER BY created_at DESC"
            ),
            {"uid": user_id, "mid": linked_member_id},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                "SELECT id, requester_user_id, expert_member_id, query, topics, "
                "status, created_at, resolved_at FROM help_requests "
                "WHERE requester_user_id = :uid "
                "ORDER BY created_at DESC"
            ),
            {"uid": user_id},
        ).fetchall()

    results = []
    for row in rows:
        topics_raw = row[4]
        if isinstance(topics_raw, str):
            try:
                topics_parsed = json.loads(topics_raw)
            except (json.JSONDecodeError, TypeError):
                topics_parsed = []
        else:
            topics_parsed = topics_raw or []

        results.append({
            "id": row[0],
            "requester_user_id": row[1],
            "expert_member_id": row[2],
            "query": row[3],
            "topics": topics_parsed,
            "status": row[5],
            "created_at": row[6],
            "resolved_at": row[7],
        })
    return results


def update_help_request_status(db: Session, request_id: str, new_status: str) -> bool:
    """Update the status of a help request. Returns True if a row was updated."""
    from datetime import datetime

    resolved_at = datetime.utcnow() if new_status == "resolved" else None
    result = db.execute(
        text(
            "UPDATE help_requests SET status = :status, resolved_at = :resolved_at "
            "WHERE id = :id"
        ),
        {"status": new_status, "resolved_at": resolved_at, "id": request_id},
    )
    db.commit()
    return result.rowcount > 0


def _ensure_health_snapshots_table(engine):
    """Create the health_snapshots table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS health_snapshots (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bus_factor_count INTEGER DEFAULT 0,
                coverage_pct REAL DEFAULT 0,
                collab_density REAL DEFAULT 0,
                active_member_pct REAL DEFAULT 0,
                avg_breadth REAL DEFAULT 0,
                health_score REAL DEFAULT 0,
                risk_summary TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    logger.info("Ensured health_snapshots table exists")


def save_health_snapshot_record(
    db: Session,
    snapshot_id: str,
    bus_factor_count: int,
    coverage_pct: float,
    collab_density: float,
    active_member_pct: float,
    avg_breadth: float,
    health_score: float,
    risk_summary: str = "{}",
) -> dict:
    """Insert a health snapshot record and return it as a dict."""
    import json
    from datetime import datetime as _dt

    now = _dt.utcnow()
    db.execute(
        text(
            "INSERT INTO health_snapshots "
            "(id, timestamp, bus_factor_count, coverage_pct, collab_density, "
            "active_member_pct, avg_breadth, health_score, risk_summary, created_at) "
            "VALUES (:id, :timestamp, :bus_factor_count, :coverage_pct, :collab_density, "
            ":active_member_pct, :avg_breadth, :health_score, :risk_summary, :created_at)"
        ),
        {
            "id": snapshot_id,
            "timestamp": now,
            "bus_factor_count": bus_factor_count,
            "coverage_pct": coverage_pct,
            "collab_density": collab_density,
            "active_member_pct": active_member_pct,
            "avg_breadth": avg_breadth,
            "health_score": health_score,
            "risk_summary": risk_summary,
            "created_at": now,
        },
    )
    db.commit()
    return {
        "id": snapshot_id,
        "timestamp": now.isoformat(),
        "bus_factor_count": bus_factor_count,
        "coverage_pct": coverage_pct,
        "collab_density": collab_density,
        "active_member_pct": active_member_pct,
        "avg_breadth": avg_breadth,
        "health_score": health_score,
        "risk_summary": json.loads(risk_summary) if isinstance(risk_summary, str) else risk_summary,
    }


def get_health_snapshots(db: Session, days: int = 90) -> list[dict]:
    """Fetch health snapshots from the last N days."""
    import json
    from datetime import datetime as _dt, timedelta as _td

    cutoff = _dt.utcnow() - _td(days=days)
    rows = db.execute(
        text(
            "SELECT id, timestamp, bus_factor_count, coverage_pct, collab_density, "
            "active_member_pct, avg_breadth, health_score, risk_summary "
            "FROM health_snapshots WHERE timestamp >= :cutoff "
            "ORDER BY timestamp ASC"
        ),
        {"cutoff": cutoff},
    ).fetchall()

    results = []
    for row in rows:
        risk_raw = row[8]
        if isinstance(risk_raw, str):
            try:
                risk_parsed = json.loads(risk_raw)
            except (json.JSONDecodeError, TypeError):
                risk_parsed = {}
        else:
            risk_parsed = risk_raw or {}

        results.append({
            "id": row[0],
            "timestamp": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "bus_factor_count": row[2],
            "coverage_pct": row[3],
            "collab_density": row[4],
            "active_member_pct": row[5],
            "avg_breadth": row[6],
            "health_score": row[7],
            "risk_summary": risk_parsed,
        })
    return results


def get_latest_health_snapshot(db: Session) -> dict | None:
    """Fetch the most recent health snapshot."""
    import json

    row = db.execute(
        text(
            "SELECT id, timestamp, bus_factor_count, coverage_pct, collab_density, "
            "active_member_pct, avg_breadth, health_score, risk_summary "
            "FROM health_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
    ).fetchone()

    if not row:
        return None

    risk_raw = row[8]
    if isinstance(risk_raw, str):
        try:
            risk_parsed = json.loads(risk_raw)
        except (json.JSONDecodeError, TypeError):
            risk_parsed = {}
    else:
        risk_parsed = risk_raw or {}

    return {
        "id": row[0],
        "timestamp": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
        "bus_factor_count": row[2],
        "coverage_pct": row[3],
        "collab_density": row[4],
        "active_member_pct": row[5],
        "avg_breadth": row[6],
        "health_score": row[7],
        "risk_summary": risk_parsed,
    }


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
