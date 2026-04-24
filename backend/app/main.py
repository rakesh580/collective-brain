import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger

import app.models  # noqa: F401 -- ensure all models registered with Base
from app.config import get_settings
from app.db.database import init_db
from app.routers import (
    analytics,
    artifacts,
    auth,
    conversations,
    expert_routing,
    github_webhooks,
    graph,
    health,
    ingest,
    insights,
    members,
    query,
    search,
    slack,
)
from app.routers import continuity as continuity_router_mod
from app.routers import decision_recommender as decision_recommender_mod
from app.routers import decisions as decisions_router_mod
from app.routers import notifications as notifications_mod
from app.routers import risk_radar as risk_radar_router_mod
from app.routers import signals as signals_router_mod
from app.routers.admin import router as admin_router
from app.routers.offboarding import router as offboarding_router
from app.routers.organizations import router as organizations_router
from app.routers.saml import router as saml_router
from app.routers.scim import router as scim_router
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.metrics import APP_INFO
from app.services.redis_service import RedisService
from app.services.scheduler import Scheduler
from app.services.task_queue import TaskQueue
from app.services.telemetry import current_trace_id, setup_telemetry
from app.services.vector_store import VectorStoreService

# ── OpenTelemetry must be set up before any instrumented code runs ──
setup_telemetry(service_name="collective-brain", version="0.6.0")

# ── Log record factory: inject request_id, trace_id, org_id ──────────────────
_old_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    if not hasattr(record, "request_id"):
        record.request_id = "-"
    if not hasattr(record, "trace_id"):
        record.trace_id = current_trace_id()
    if not hasattr(record, "org_id"):
        record.org_id = "-"
    return record


logging.setLogRecordFactory(_record_factory)

# ── Logging format ────────────────────────────────────────────────────────────
_log_level = os.environ.get("CB_LOG_LEVEL", "INFO").upper()
_dev_mode = os.environ.get("CB_DEV_MODE", "") == "1"

if _dev_mode:
    _formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [req=%(request_id)s trace=%(trace_id)s]: %(message)s"
    )
else:
    _formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s %(trace_id)s %(org_id)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )

_handler = logging.StreamHandler()
_handler.setFormatter(_formatter)
logging.basicConfig(level=getattr(logging, _log_level, logging.INFO), handlers=[_handler])

logger = logging.getLogger("collective_brain")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    # ── Database (Supabase/PostgreSQL) + Alembic migrations ──
    init_db(settings=settings)

    # ── Redis (optional — graceful fallback to in-memory) ──
    redis = RedisService(settings.redis_url)
    app.state.redis = redis

    # ── Background Task Queue ──
    task_queue = TaskQueue(max_concurrent=3)
    await task_queue.start()
    app.state.task_queue = task_queue

    # ── Scheduler (APScheduler) ──
    scheduler = Scheduler()
    _register_scheduled_jobs(scheduler)
    await scheduler.start()
    app.state.scheduler = scheduler

    # ── Core Services ──
    from app.db.database import get_session_factory

    app.state.embedding_service = EmbeddingService(settings.embedding_model)
    app.state.vector_store = VectorStoreService(get_session_factory())
    app.state.llm_service = LLMService(settings)

    # ── Circuit Breakers ──
    app.state.embedding_breaker = CircuitBreaker("embedding_service", failure_threshold=5, recovery_timeout=60.0)

    redis_ok = await redis.ping()

    # ── Publish app info to Prometheus ──
    APP_INFO.info(
        {
            "version": "0.6.0",
            "llm_provider": settings.llm_provider,
            "agent_mode": settings.agent_mode,
            "embedding_model": settings.embedding_model,
        }
    )

    # JWT secret — generate if not set
    if not settings.jwt_secret:
        import secrets as _secrets

        _jwt_path = Path("/data/.cb_jwt_secret")
        if _jwt_path.exists():
            settings.jwt_secret = _jwt_path.read_text().strip()
            logger.info("Loaded JWT secret from %s", _jwt_path)
        else:
            settings.jwt_secret = _secrets.token_urlsafe(64)
            try:
                _jwt_path.write_text(settings.jwt_secret)
                _jwt_path.chmod(0o600)
                logger.info("Generated and persisted JWT secret to %s", _jwt_path)
            except OSError:
                logger.warning(
                    "CB_JWT_SECRET is not set and could not persist to %s — JWTs will be invalidated on restart.",
                    _jwt_path,
                )

    if settings.jwt_secret and len(settings.jwt_secret) < 32:
        logger.warning("CB_JWT_SECRET is shorter than 32 characters — use a stronger secret")

    # Eager-load embedding model
    try:
        _ = app.state.embedding_service.model
        logger.info("Embedding model pre-loaded successfully")
    except Exception as e:
        logger.warning("Failed to pre-load embedding model: %s", e)

    logger.info(
        "Collective Brain started (DB: Supabase/PostgreSQL, Redis: %s, LLM: %s/%s, Agent: %s)",
        "connected" if redis_ok else "in-memory fallback",
        settings.llm_provider,
        settings.agent_mode,
        "circuit-protected",
    )

    yield

    # ── Graceful Shutdown ──
    await scheduler.stop()
    await task_queue.stop()
    await redis.close()
    logger.info("Collective Brain shut down gracefully")


def _register_scheduled_jobs(scheduler: Scheduler) -> None:
    """Register every scheduled background job. Called once at lifespan start.

    Keep this list short and intentional — every job is a moving part that can
    fail in production. Each job must be idempotent and safe to re-run.
    """
    from apscheduler.triggers.cron import CronTrigger

    def _nightly_health_snapshot() -> dict:
        from app.db.database import create_session
        from app.services.team_health_service import save_health_snapshot

        db = create_session()
        try:
            return save_health_snapshot(db)
        finally:
            db.close()

    from app.services.contribution_rollup_service import run_contribution_rollup_job

    # ContributionRollup is the "first job" per the roadmap — per-member 7d/30d
    # stats feed deltas, strengths/weaknesses, and silent-area signals.
    scheduler.register(
        name="contribution_rollup",
        func=run_contribution_rollup_job,
        trigger=CronTrigger(hour=2, minute=30),  # 02:30 UTC — runs before health snapshot
        description="Per-member 7d/30d activity rollups (contributions, artifacts, topics).",
    )

    scheduler.register(
        name="nightly_health_snapshot",
        func=_nightly_health_snapshot,
        trigger=CronTrigger(hour=3, minute=15),  # 03:15 UTC daily
        description="Compute and persist org health snapshot (bus factor, coverage, collab).",
    )

    from app.services.digest_dispatcher import run_due_digests_job

    scheduler.register(
        name="weekly_digest_dispatcher",
        func=run_due_digests_job,
        # Runs every hour on the hour (UTC). Each SlackDigestConfig row
        # specifies its own weekday+hour; the dispatcher picks the matches.
        trigger=CronTrigger(minute=0),
        description="Fire weekly Slack digests for every due SlackDigestConfig.",
    )

    from app.services.strengths_weaknesses_service import run_strengths_weaknesses_job

    scheduler.register(
        name="strengths_weaknesses_analyzer",
        func=run_strengths_weaknesses_job,
        # 03:30 UTC — after contribution_rollup (02:30) and health_snapshot (03:15)
        # but before pattern_detection (04:00) so downstream signals can read
        # member.strengths / .weaknesses if needed.
        trigger=CronTrigger(hour=3, minute=30),
        description="Per-member strengths/weaknesses + per-org aggregate snapshot.",
    )

    from app.services.pattern_detection import run_pattern_detection_job

    scheduler.register(
        name="pattern_detection",
        func=run_pattern_detection_job,
        # 04:00 UTC — after contribution_rollup (02:30) and health_snapshot (03:15)
        # so the rollup data is fresh for silent-area / load-skew detection.
        trigger=CronTrigger(hour=4, minute=0),
        description="Detect slow lanes, silent areas, load skew, Friday-land, and review bottlenecks.",
    )


app = FastAPI(title="Collective Brain", version="0.6.0", lifespan=lifespan)

# ── Prometheus /metrics endpoint ─────────────────────────────────────────────
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/api/v1/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ── CORS ─────────────────────────────────────────────────────────────────────
_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
_extra_origin = os.environ.get("CB_CORS_ORIGIN")
if _extra_origin:
    _cors_origins.append(_extra_origin)

_on_hf_spaces = bool(os.environ.get("SPACE_ID"))
if _on_hf_spaces:
    _space_id = os.environ.get("SPACE_ID", "")
    _cors_origins = [
        f"https://{_space_id.replace('/', '-')}.hf.space",
        "https://huggingface.co",
        f"https://huggingface.co/spaces/{_space_id}",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _on_hf_spaces,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# ── Middleware ────────────────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from app.request_context import org_id_var as _org_id_var
from app.request_context import request_id_var as _request_id_var


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if _on_hf_spaces:
            response.headers["X-Frame-Options"] = "ALLOWALL"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://accounts.google.com https://apis.google.com; "
            "style-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "frame-src https://accounts.google.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://accounts.google.com https://www.googleapis.com wss:; "
            "font-src 'self'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class DeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-12-31"
            response.headers["Link"] = '</api/v1/>; rel="successor-version"'
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach request_id + trace_id to every request; propagate org_id from JWT."""

    async def dispatch(self, request: StarletteRequest, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        _request_id_var.set(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        # Expose trace ID so clients can correlate frontend errors with backend traces
        trace_id = current_trace_id()
        if trace_id != "-":
            response.headers["X-Trace-ID"] = trace_id
        return response


# Custom logging filter — injects context vars into every log record
class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = _request_id_var.get("-")
        record.trace_id = current_trace_id()
        record.org_id = _org_id_var.get("-")
        return True


for _h in logging.root.handlers:
    _h.addFilter(RequestContextFilter())

from starlette.middleware.gzip import GZipMiddleware

from app.middleware.access_log import AccessLogMiddleware

# Middleware order (outermost first — Starlette applies in LIFO):
# GZip -> SecurityHeaders -> Deprecation -> RequestID -> AccessLog
# AccessLog is innermost so its latency measurement is closest to handler
# time (excludes GZip compression on large responses).
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(DeprecationMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AccessLogMiddleware)


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request, exc: CircuitBreakerError):
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
    from fastapi.responses import JSONResponse

    # Stable error reference users can quote when reporting a 500. Pairs with
    # the logged traceback for cross-referencing in HF Spaces / Render logs.
    error_ref = uuid.uuid4().hex[:8]
    logger.error(
        "Unhandled error ref=%s path=%s method=%s: %s",
        error_ref,
        getattr(request.url, "path", "?"),
        getattr(request, "method", "?"),
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_ref": error_ref,
            "error_type": type(exc).__name__,
        },
    )


# ── Versioned API (v1) ────────────────────────────────────────────────────────
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router, prefix="/health", tags=["health"])
api_v1.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_v1.include_router(query.router, tags=["query"])
api_v1.include_router(members.router, prefix="/members", tags=["members"])
api_v1.include_router(insights.router, prefix="/insights", tags=["insights"])
api_v1.include_router(graph.router, prefix="/graph", tags=["graph"])
api_v1.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_v1.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
api_v1.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_v1.include_router(search.router, prefix="/search", tags=["search"])
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(slack.router, prefix="/slack", tags=["slack"])
api_v1.include_router(github_webhooks.router, prefix="/github", tags=["github"])
api_v1.include_router(expert_routing.router, prefix="/experts", tags=["experts"])
# Phase 7 — Decision Intelligence
api_v1.include_router(decisions_router_mod.router, prefix="/decisions", tags=["decisions"])
api_v1.include_router(risk_radar_router_mod.router, prefix="/risk-radar", tags=["risk-radar"])
api_v1.include_router(continuity_router_mod.router, prefix="/continuity", tags=["continuity"])
# Phase 8 — Decision Recommender, Notifications
api_v1.include_router(decision_recommender_mod.router, prefix="/decision-recommender", tags=["decision-recommender"])
api_v1.include_router(notifications_mod.router, prefix="/notifications", tags=["notifications"])
# Phase 9 — Pattern-detection signals (Pulse "Signals" tab)
api_v1.include_router(signals_router_mod.router, prefix="/signals", tags=["signals"])
# Phase 4 — Enterprise (organizations, SAML SSO, SCIM provisioning)
api_v1.include_router(organizations_router, tags=["organizations"])
api_v1.include_router(saml_router, tags=["sso"])
api_v1.include_router(scim_router, tags=["scim"])
# Phase 6 — Offboarding (backend kept: Continuity depends on offboarding reports)
api_v1.include_router(offboarding_router, tags=["offboarding"])
api_v1.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(api_v1)

# ── Frontend SPA fallback ─────────────────────────────────────────────────────
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")
    _static_dir_resolved = _static_dir.resolve()

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = (_static_dir / full_path).resolve()
        if file_path.is_relative_to(_static_dir_resolved) and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")
