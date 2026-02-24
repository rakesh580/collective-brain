from fastapi import APIRouter, Request

from app.schemas.requests import QueryRequest
from app.schemas.responses import QueryResponse
from app.services.rag_pipeline import RAGPipeline
from app.db.database import get_session

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_brain(body: QueryRequest, request: Request):
    from app.dependencies import get_current_user

    user = get_current_user(request)
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
        )
    finally:
        db.close()
