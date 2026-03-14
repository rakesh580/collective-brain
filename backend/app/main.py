from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db.database import init_db
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.llm_service import LLMService
from app.services.redis_service import RedisService
from app.services.task_queue import TaskQueue
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError
import app.models  # noqa: F401 -- ensure all models registered with Base
from app.routers import (
    health, ingest, query, members, insights, graph,
    conversations, artifacts, analytics, search, auth, discussions, rooms, slack,
    github_webhooks, expert_routing,
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("collective_brain")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    # ── Check persistent storage on HuggingFace Spaces ──
    _marker = Path("/data/.cb_persistence_marker")
    if Path("/data").exists():
        if _marker.exists():
            logger.info("Persistent storage verified (/data survives restarts)")
        else:
            logger.warning(
                "First boot with /data — if user data disappears after restart, "
                "enable Persistent Storage in your HF Space Settings"
            )
            try:
                _marker.write_text("ok")
            except OSError:
                pass

    # ── Database (PostgreSQL or SQLite) ──
    init_db(settings=settings)

    # ── Redis (optional — graceful fallback to in-memory) ──
    redis = RedisService(settings.redis_url)
    app.state.redis = redis

    # ── Background Task Queue ──
    task_queue = TaskQueue(max_concurrent=3)
    await task_queue.start()
    app.state.task_queue = task_queue

    # ── Core Services ──
    app.state.embedding_service = EmbeddingService(settings.embedding_model)
    app.state.vector_store = VectorStoreService(settings.chroma_persist_dir)
    app.state.llm_service = LLMService(settings)

    # ── Circuit Breakers for external services ──
    app.state.embedding_breaker = CircuitBreaker(
        "embedding_service", failure_threshold=5, recovery_timeout=60.0
    )

    # ── Initialize Redis references in routers ──
    from app.routers.rooms import init_redis_from_app as rooms_init_redis
    from app.routers.discussions import init_redis_from_app as discussions_init_redis
    rooms_init_redis(app)
    discussions_init_redis(app)

    redis_ok = await redis.ping()
    db_type = "PostgreSQL" if settings.is_postgres else "SQLite"

    # Auto-generate a random JWT secret if none was provided.
    # This is safe for single-worker or single-container deployments.
    # For multi-worker/replica setups, set CB_JWT_SECRET explicitly.
    if not settings.jwt_secret:
        import secrets as _secrets
        # Persist JWT secret to /data so tokens survive container restarts
        _jwt_path = Path("/data/.cb_jwt_secret")
        if _jwt_path.exists():
            settings.jwt_secret = _jwt_path.read_text().strip()
            logger.info("Loaded JWT secret from %s", _jwt_path)
        else:
            settings.jwt_secret = _secrets.token_urlsafe(64)
            try:
                _jwt_path.write_text(settings.jwt_secret)
                logger.info("Generated and persisted JWT secret to %s", _jwt_path)
            except OSError:
                logger.warning(
                    "CB_JWT_SECRET is not set and could not persist to %s — "
                    "JWTs will be invalidated on restart.", _jwt_path
                )

    # Eager-load the embedding model to avoid 5-10s latency on first query
    try:
        _ = app.state.embedding_service.model
        logger.info("Embedding model pre-loaded successfully")
    except Exception as e:
        logger.warning("Failed to pre-load embedding model: %s", e)

    logger.info(
        "Collective Brain started (DB: %s, Redis: %s, LLM: %s/%s, Agent: %s)",
        db_type,
        "connected" if redis_ok else "in-memory fallback",
        settings.llm_provider,
        settings.agent_mode,
        "circuit-protected",
    )

    yield

    # ── Graceful Shutdown ──
    # Flush SQLite WAL to main file before container dies
    if not settings.is_postgres:
        try:
            from app.db.database import get_engine
            eng = get_engine()
            if eng:
                with eng.raw_connection() as raw_conn:
                    raw_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("SQLite WAL flushed on shutdown")
        except Exception as e:
            logger.warning("WAL checkpoint on shutdown failed: %s", e)
    await task_queue.stop()
    await redis.close()
    logger.info("Collective Brain shut down gracefully")


app = FastAPI(title="Collective Brain", version="0.3.0", lifespan=lifespan)

_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
# Allow Render deploy URL via env var
_extra_origin = os.environ.get("CB_CORS_ORIGIN")
if _extra_origin:
    _cors_origins.append(_extra_origin)

# On HuggingFace Spaces the app is served inside an iframe from
# huggingface.co.  SPACE_ID is auto-set by the HF runtime.
_on_hf_spaces = bool(os.environ.get("SPACE_ID"))
if _on_hf_spaces:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _on_hf_spaces,  # credentials not allowed with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request, exc: CircuitBreakerError):
    """Return 503 when a circuit breaker is open."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=503,
        content={
            "detail": f"Service temporarily unavailable: {exc.service_name}",
            "retry_after": round(exc.retry_after),
        },
        headers={"Retry-After": str(round(exc.retry_after))},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# Routers — all under /api prefix so they don't collide with SPA routes
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(members.router, prefix="/api/members", tags=["members"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(artifacts.router, prefix="/api/artifacts", tags=["artifacts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(discussions.router, prefix="/api/discussions", tags=["discussions"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["rooms"])
app.include_router(slack.router, prefix="/api/slack", tags=["slack"])
app.include_router(github_webhooks.router, prefix="/api/github", tags=["github"])
app.include_router(expert_routing.router, prefix="/api/experts", tags=["experts"])

# ── Serve frontend static files in production ──
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    # Serve asset files (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    _static_dir_resolved = _static_dir.resolve()

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        file_path = (_static_dir / full_path).resolve()
        # Prevent path traversal — only serve files within the static dir
        if file_path.is_relative_to(_static_dir_resolved) and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")
