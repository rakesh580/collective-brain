from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.schemas.responses import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(request: Request):
    llm = request.app.state.llm_service
    vs = request.app.state.vector_store
    settings = request.app.state.settings
    llm_available = await llm.is_available()
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        llm_available=llm_available,
        vector_store_count=vs.count(),
        embedding_model=settings.embedding_model,
        agent_mode=settings.agent_mode,
    )


@router.get("/detailed")
async def detailed_health(request: Request):
    """Detailed health check with all dependency statuses.

    Uses lightweight checks (no external HTTP calls) so it can be
    called frequently under load without degrading performance.
    """
    settings = request.app.state.settings
    checks: dict = {}

    # ── Database ──
    try:
        from app.db.database import create_session

        db = create_session()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = {
                "status": "healthy",
                "type": "PostgreSQL" if settings.is_postgres else "SQLite",
            }
        finally:
            db.close()
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # ── Redis ──
    redis = getattr(request.app.state, "redis", None)
    if redis:
        # Lightweight: just check if the client object exists, don't ping
        checks["redis"] = {
            "status": "healthy" if redis.is_connected else "fallback",
            "mode": "connected" if redis.is_connected else "in-memory",
        }
    else:
        checks["redis"] = {"status": "fallback", "mode": "in-memory"}

    # ── LLM Service ──
    llm = request.app.state.llm_service
    # Use circuit breaker state instead of making an HTTP call
    circuit_status = llm.get_circuit_status() if hasattr(llm, "get_circuit_status") else None
    llm_available = circuit_status.get("is_available", True) if circuit_status else True
    checks["llm"] = {
        "status": "healthy" if llm_available else "circuit_open",
        "provider": settings.llm_provider,
        "model": settings.ollama_model if settings.llm_provider == "ollama" else settings.claude_model,
    }
    if circuit_status:
        checks["llm"]["circuit_breaker"] = circuit_status

    # ── Embedding Circuit Breaker ──
    emb_breaker = getattr(request.app.state, "embedding_breaker", None)
    if emb_breaker:
        checks["embedding_service"] = {
            "status": "healthy" if emb_breaker.is_available else "circuit_open",
            **emb_breaker.get_status(),
        }

    # ── Vector Store ──
    vs = request.app.state.vector_store
    try:
        count = vs.count()
        checks["vector_store"] = {"status": "healthy", "document_count": count}
    except Exception as e:
        checks["vector_store"] = {"status": "unhealthy", "error": str(e)}

    # ── Task Queue ──
    tq = getattr(request.app.state, "task_queue", None)
    if tq:
        checks["task_queue"] = {
            "status": "healthy" if tq._running else "stopped",
            "workers": len(tq._workers),
            "pending_results": len(tq._results),
        }

    # Overall status
    all_healthy = all(c.get("status") in ("healthy", "fallback") for c in checks.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
        },
    )
