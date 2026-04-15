"""Unit tests for RAGPipeline — intent classification, retrieval, LLM integration."""

from unittest.mock import AsyncMock

import pytest

from app.services.rag_pipeline import RAGPipeline


@pytest.fixture()
def pipeline(mock_llm, mock_embedder, vector_store, db_session):
    # Ensure test user exists for FK constraint on conversations
    from sqlalchemy import text

    db_session.execute(
        text(
            "INSERT INTO users (id, username, email, password_hash, auth_provider, is_active, created_at) "
            "VALUES ('user-1', 'testuser', 'test@test.com', 'x', 'local', true, now()) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    db_session.commit()
    return RAGPipeline(
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=vector_store,
        db=db_session,
    )


class TestIntentClassification:
    def test_member_recommendation(self, pipeline):
        assert pipeline._classify_intent("who should work on the API?") == "member_recommendation"
        assert pipeline._classify_intent("best person for this task") == "member_recommendation"
        assert pipeline._classify_intent("who knows about authentication?") == "member_recommendation"

    def test_pattern_analysis(self, pipeline):
        assert pipeline._classify_intent("are there recurring patterns?") == "pattern_analysis"
        assert pipeline._classify_intent("what bottleneck keeps causing delays?") == "pattern_analysis"

    def test_strategy_generation(self, pipeline):
        assert pipeline._classify_intent("create a strategy for the sprint") == "strategy_generation"
        assert pipeline._classify_intent("what should be our priorities?") == "strategy_generation"

    def test_general_intent(self, pipeline):
        assert pipeline._classify_intent("tell me about the project") == "general"
        assert pipeline._classify_intent("hello") == "general"


class TestAnswer:
    @pytest.mark.asyncio
    async def test_answer_returns_response(self, pipeline):
        result = await pipeline.answer(
            question="Who is the best Python developer?",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        assert result is not None
        assert hasattr(result, "answer")
        assert len(result.answer) > 0

    @pytest.mark.asyncio
    async def test_answer_creates_conversation(self, pipeline):
        result = await pipeline.answer(
            question="Tell me about the project",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        assert result.conversation_id is not None

    @pytest.mark.asyncio
    async def test_answer_with_existing_conversation(self, pipeline, db_session):
        from uuid import uuid4

        from app.models.conversation import ConversationRecord

        conv = ConversationRecord(
            id=str(uuid4()),
            title="Test",
            owner_user_id="user-1",
        )
        db_session.add(conv)
        db_session.commit()

        result = await pipeline.answer(
            question="Follow up question",
            conversation_id=conv.id,
            sender_user_id="user-1",
            sender_name="Test User",
        )
        assert result.conversation_id == conv.id

    @pytest.mark.asyncio
    async def test_answer_with_empty_retrieval(self, pipeline):
        """Should still return an answer even with no vector matches."""
        result = await pipeline.answer(
            question="Something completely unrelated",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        assert result.answer is not None

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_fallback(self, pipeline):
        """When LLM times out, should return a graceful fallback response."""

        pipeline.llm.generate = AsyncMock(side_effect=TimeoutError())
        result = await pipeline.answer(
            question="Test question",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        # Should not raise, should return fallback
        assert result.answer is not None

    @pytest.mark.asyncio
    async def test_llm_error_returns_fallback(self, pipeline):
        pipeline.llm.generate = AsyncMock(side_effect=Exception("LLM down"))
        result = await pipeline.answer(
            question="Test question",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        assert result.answer is not None


class TestSourceExtraction:
    @pytest.mark.asyncio
    async def test_returns_sources_from_retrieval(self, pipeline, vector_store):
        # Seed vector store with data
        vector_store.add_documents(
            ids=["src-1"],
            documents=["Alice is a Python expert"],
            embeddings=[[0.1] * 384],
            metadatas=[{"source_type": "git", "artifact_id": "a1", "author": "alice", "topics": "python"}],
        )

        result = await pipeline.answer(
            question="Who knows Python?",
            sender_user_id="user-1",
            sender_name="Test User",
        )
        # Sources should be populated from retrieval
        assert isinstance(result.sources, list)
