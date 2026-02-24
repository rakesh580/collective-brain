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
    conversations, artifacts, analytics, search, auth, discussions, rooms,
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
    from app.routers.rooms import init_redis_from_app
    init_redis_from_app(app)

    redis_ok = await redis.ping()
    db_type = "PostgreSQL" if settings.is_postgres else "SQLite"

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
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


# Routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(query.router, tags=["query"])
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
app.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(discussions.router, prefix="/discussions", tags=["discussions"])
app.include_router(rooms.router, prefix="/rooms", tags=["rooms"])

# ── Serve frontend static files in production ──
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    # Serve asset files (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")
