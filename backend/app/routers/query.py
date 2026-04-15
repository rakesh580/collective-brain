from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.db.database import create_session
from app.dependencies import get_current_user
from app.schemas.requests import QueryRequest
from app.schemas.responses import QueryResponse
from app.services.rag_pipeline import RAGPipeline

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
async def query_brain(body: QueryRequest, request: Request, user=Depends(get_current_user)):
    await _rate_limit_ai(request, user.id)
    db = create_session()
    settings = request.app.state.settings
    import logging as _logging
    _logger = _logging.getLogger(__name__)
    try:
        if settings.agent_mode == "langgraph":
            try:
                from app.services.agent_pipeline import AgentPipeline
                pipeline = AgentPipeline(
                    db=db,
                    settings=settings,
                    embedder=request.app.state.embedding_service,
                    vector_store=request.app.state.vector_store,
                )
            except Exception as e:
                _logger.warning("LangGraph agent failed to init, falling back to RAG: %s", e)
                pipeline = RAGPipeline(
                    llm=request.app.state.llm_service,
                    embedder=request.app.state.embedding_service,
                    vector_store=request.app.state.vector_store,
                    db=db,
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
