import json
import logging
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

Base = declarative_base()

_engine = None
_SessionLocal = None

logger = logging.getLogger("collective_brain.db")


def init_db(settings=None):
    """Initialize database connection. Uses PostgreSQL (Supabase) if available,
    falls back to local SQLite for development."""
    global _engine, _SessionLocal

    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    db_url = settings.effective_database_url

    # Register all models with Base.metadata
    import app.models  # noqa: F401

    # Try PostgreSQL first
    try:
        from sqlalchemy import text as sa_text

        logger.info("Connecting to PostgreSQL (Supabase)")
        _engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            echo=False,
        )
        # Test connection
        with _engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        # Run Alembic migrations using the direct session URL (not the pooler)
        import os

        if os.environ.get("CB_RUN_MIGRATIONS", "true").lower() == "true":
            _run_alembic_migrations(settings)
        else:
            logger.info("Skipping migrations (CB_RUN_MIGRATIONS=false)")
        logger.info("Database initialized (PostgreSQL/Supabase)")

    except Exception as pg_err:
        logger.warning("PostgreSQL connection failed: %s", str(pg_err)[:150])
        logger.info("Falling back to local SQLite database for development")

        import os

        sqlite_path = os.path.join(os.path.dirname(__file__), "..", "..", "collective_brain_dev.db")
        sqlite_url = f"sqlite:///{os.path.abspath(sqlite_path)}"
        from sqlalchemy.pool import StaticPool

        _engine = create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        # Create all tables directly (skip Alembic for SQLite)
        Base.metadata.create_all(bind=_engine)
        logger.info("Database initialized (SQLite fallback: %s)", sqlite_path)


def _run_alembic_migrations(settings):
    """Run `alembic upgrade head` programmatically at startup.

    Uses CB_MIGRATION_DATABASE_URL (direct port-5432 connection) because
    Alembic needs a session-mode connection, not the transaction pooler.
    """
    try:
        import os

        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config()
        # Locate alembic.ini relative to this file: backend/alembic.ini
        ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
        alembic_cfg.set_main_option("config_file_name", os.path.abspath(ini_path))
        alembic_cfg.set_main_option(
            "script_location",
            os.path.join(os.path.dirname(__file__), "..", "..", "alembic"),
        )
        alembic_cfg.set_main_option("sqlalchemy.url", settings.effective_migration_url)

        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied (head)")
    except Exception as e:
        # Log but don't crash — the DB may already be at head, or the
        # connection may be transiently unreachable. Promoted from warning
        # to error with full traceback so production logs surface broken
        # migrations (they manifest later as 500s on endpoints that expect
        # missing tables/columns).
        logger.error("Alembic migration step raised: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# ORM-based helper functions
# ---------------------------------------------------------------------------


def save_digest_config(
    db: Session,
    workspace_id: str,
    channel_id: str,
    channel_name: str = "",
    schedule_day: int = 0,
    schedule_hour: int = 9,
    enabled: bool = True,
) -> dict:
    from app.models.slack_digest_config import SlackDigestConfig

    existing = (
        db.query(SlackDigestConfig)
        .filter(
            SlackDigestConfig.workspace_id == workspace_id,
            SlackDigestConfig.channel_id == channel_id,
        )
        .first()
    )

    if existing:
        existing.channel_name = channel_name
        existing.schedule_day = schedule_day
        existing.schedule_hour = schedule_hour
        existing.enabled = enabled
        db.commit()
        config_id = existing.id
    else:
        config_id = str(uuid.uuid4())
        new_config = SlackDigestConfig(
            id=config_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            channel_name=channel_name,
            schedule_day=schedule_day,
            schedule_hour=schedule_hour,
            enabled=enabled,
            created_at=datetime.now(UTC),
        )
        db.add(new_config)
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
    from app.models.slack_digest_config import SlackDigestConfig

    rows = (
        db.query(SlackDigestConfig)
        .filter(SlackDigestConfig.workspace_id == workspace_id)
        .order_by(SlackDigestConfig.created_at.desc())
        .all()
    )

    results = []
    for row in rows:
        results.append(
            {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "channel_id": row.channel_id,
                "channel_name": row.channel_name or "",
                "schedule_day": row.schedule_day,
                "schedule_hour": row.schedule_hour,
                "enabled": bool(row.enabled),
                "last_sent_at": row.last_sent_at.isoformat() if row.last_sent_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return results


def update_digest_last_sent(db: Session, config_id: str) -> bool:
    from app.models.slack_digest_config import SlackDigestConfig

    config = db.query(SlackDigestConfig).filter(SlackDigestConfig.id == config_id).first()
    if not config:
        return False

    config.last_sent_at = datetime.now(UTC)
    db.commit()
    return True


def create_help_request(
    db: Session,
    requester_user_id: str,
    expert_member_id: str,
    query: str,
    topics: list[str] | None = None,
) -> dict:
    from app.models.help_request import HelpRequest

    request_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    topics_json = json.dumps(topics or [])

    new_request = HelpRequest(
        id=request_id,
        requester_user_id=requester_user_id,
        expert_member_id=expert_member_id,
        query=query,
        topics=topics_json,
        status="pending",
        created_at=now,
    )
    db.add(new_request)
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
    from sqlalchemy import or_

    from app.models.help_request import HelpRequest

    query = db.query(HelpRequest)
    if linked_member_id:
        query = query.filter(
            or_(
                HelpRequest.requester_user_id == user_id,
                HelpRequest.expert_member_id == linked_member_id,
            )
        )
    else:
        query = query.filter(HelpRequest.requester_user_id == user_id)

    rows = query.order_by(HelpRequest.created_at.desc()).all()

    results = []
    for row in rows:
        topics_raw = row.topics
        if isinstance(topics_raw, str):
            try:
                topics_parsed = json.loads(topics_raw)
            except (json.JSONDecodeError, TypeError):
                topics_parsed = []
        else:
            topics_parsed = topics_raw or []

        results.append(
            {
                "id": row.id,
                "requester_user_id": row.requester_user_id,
                "expert_member_id": row.expert_member_id,
                "query": row.query,
                "topics": topics_parsed,
                "status": row.status,
                "created_at": row.created_at,
                "resolved_at": row.resolved_at,
            }
        )
    return results


def update_help_request_status(db: Session, request_id: str, new_status: str) -> bool:
    from app.models.help_request import HelpRequest

    request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
    if not request:
        return False

    request.status = new_status
    request.resolved_at = datetime.now(UTC) if new_status == "resolved" else None
    db.commit()
    return True


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
    from app.models.health_snapshot import HealthSnapshot

    now = datetime.now(UTC)
    snapshot = HealthSnapshot(
        id=snapshot_id,
        timestamp=now,
        bus_factor_count=bus_factor_count,
        coverage_pct=coverage_pct,
        collab_density=collab_density,
        active_member_pct=active_member_pct,
        avg_breadth=avg_breadth,
        health_score=health_score,
        risk_summary=risk_summary,
        created_at=now,
    )
    db.add(snapshot)
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
    from app.models.health_snapshot import HealthSnapshot

    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(HealthSnapshot)
        .filter(HealthSnapshot.timestamp >= cutoff)
        .order_by(HealthSnapshot.timestamp.asc())
        .all()
    )

    results = []
    for row in rows:
        risk_raw = row.risk_summary
        if isinstance(risk_raw, str):
            try:
                risk_parsed = json.loads(risk_raw)
            except (json.JSONDecodeError, TypeError):
                risk_parsed = {}
        else:
            risk_parsed = risk_raw or {}

        results.append(
            {
                "id": row.id,
                "timestamp": row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
                "bus_factor_count": row.bus_factor_count,
                "coverage_pct": row.coverage_pct,
                "collab_density": row.collab_density,
                "active_member_pct": row.active_member_pct,
                "avg_breadth": row.avg_breadth,
                "health_score": row.health_score,
                "risk_summary": risk_parsed,
            }
        )
    return results


def get_latest_health_snapshot(db: Session) -> dict | None:
    from app.models.health_snapshot import HealthSnapshot

    row = db.query(HealthSnapshot).order_by(HealthSnapshot.timestamp.desc()).first()

    if not row:
        return None

    risk_raw = row.risk_summary
    if isinstance(risk_raw, str):
        try:
            risk_parsed = json.loads(risk_raw)
        except (json.JSONDecodeError, TypeError):
            risk_parsed = {}
    else:
        risk_parsed = risk_raw or {}

    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
        "bus_factor_count": row.bus_factor_count,
        "coverage_pct": row.coverage_pct,
        "collab_density": row.collab_density,
        "active_member_pct": row.active_member_pct,
        "avg_breadth": row.avg_breadth,
        "health_score": row.health_score,
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


def create_session() -> Session:
    """Create a new database session (non-generator)."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()


def get_engine():
    """Return the SQLAlchemy engine (for health checks)."""
    return _engine


def get_session_factory():
    """Return the session factory (used by VectorStoreService)."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal
