from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.requests import QueryRequest
from app.schemas.responses import QueryResponse
from app.services.rag_pipeline import RAGPipeline
from app.db.database import get_session

router = APIRouter()


async def _rate_limit_ai(request: Request, user_id: str):
    """10 AI queries per minute per user."""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return
    allowed, _ = await redis.check_rate_limit(f"ai:query:{user_id}", 10, 60)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI query rate limit exceeded. Please wait a moment.",
        )


@router.post("/query", response_model=QueryResponse)
async def query_brain(body: QueryRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
    await _rate_limit_ai(request, user.id)
    db = next(get_session())
    settings = request.app.state.settings
    try:
        if settings.agent_mode == "langgraph":
            from app.services.agent_pipeline import AgentPipeline
            pipeline = AgentPipeline(
                db=db,
                settings=settings,
                embedder=request.app.state.embedding_service,
                vector_store=request.app.state.vector_store,
            )
        else:
            pipeline = RAGPipeline(
                llm=request.app.state.llm_service,
                embedder=request.app.state.embedding_service,
                vector_store=request.app.state.vector_store,
                db=db,
            )
        return await pipeline.answer(
            question=body.question,
            conversation_id=body.conversation_id,
            filters=body.filters,
            sender_user_id=user.id,
            sender_name=user.display_name or user.username,
            room_id=body.room_id,
        )
    finally:
        db.close()
