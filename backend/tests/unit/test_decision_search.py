"""Unit tests for DecisionSearchService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.decision_search import DecisionSearchService


def _make_decision(
    decision_id="d1",
    title="Use PostgreSQL",
    description="PG for billing",
    context_summary="ACID needed",
    decision_type="technical",
    status="active",
    confidence_score=0.8,
    source_artifact_ids=None,
    involved_member_ids=None,
    tags=None,
    decided_at=None,
    created_at=None,
    extracted_at=None,
    updated_at=None,
    alternatives_considered=None,
    outcome_summary=None,
    source_chunk_ids=None,
):
    d = MagicMock()
    d.id = decision_id
    d.title = title
    d.description = description
    d.context_summary = context_summary
    d.decision_type = decision_type
    d.status = status
    d.confidence_score = confidence_score
    d.source_artifact_ids = source_artifact_ids or []
    d.source_chunk_ids = source_chunk_ids or []
    d.involved_member_ids = involved_member_ids or []
    d.tags = tags or []
    d.decided_at = decided_at
    d.created_at = created_at or datetime.now(UTC)
    d.extracted_at = extracted_at or datetime.now(UTC)
    d.updated_at = updated_at or datetime.now(UTC)
    d.alternatives_considered = alternatives_considered or []
    d.outcome_summary = outcome_summary
    return d


def _build_service(mock_llm, mock_embedder, mock_vector_store=None):
    mock_llm.generate = AsyncMock(return_value="LLM answer")
    return DecisionSearchService(
        llm_service=mock_llm,
        embedding_service=mock_embedder,
        vector_store=mock_vector_store or MagicMock(),
    )


# ---------------------------------------------------------------------------
# TestSearchDecisions
# ---------------------------------------------------------------------------


class TestSearchDecisions:
    @pytest.mark.asyncio
    async def test_keyword_search_returns_matching_decisions(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)
        decision = _make_decision(title="Use PostgreSQL for billing")

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            # keyword query chain
            query_mock = MagicMock()
            db.query.return_value.filter.return_value = query_mock
            query_mock.order_by.return_value.limit.return_value.all.return_value = [decision]
            # semantic query: return empty to simplify
            query_mock.all.return_value = []

            result = await service.search_decisions("PostgreSQL")

        assert len(result) >= 1
        assert result[0]["title"] == "Use PostgreSQL for billing"

    @pytest.mark.asyncio
    async def test_empty_query_returns_results_or_empty(self, mock_llm, mock_embedder):
        """An empty-string query should not crash."""
        service = _build_service(mock_llm, mock_embedder)

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            query_mock = MagicMock()
            db.query.return_value.filter.return_value = query_mock
            query_mock.order_by.return_value.limit.return_value.all.return_value = []
            query_mock.all.return_value = []

            result = await service.search_decisions("")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_with_no_results(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            query_mock = MagicMock()
            db.query.return_value.filter.return_value = query_mock
            query_mock.order_by.return_value.limit.return_value.all.return_value = []
            query_mock.all.return_value = []

            result = await service.search_decisions("xyznonexistent")

        assert result == []


# ---------------------------------------------------------------------------
# TestWhyDidWe
# ---------------------------------------------------------------------------


class TestWhyDidWe:
    @pytest.mark.asyncio
    async def test_returns_answer_with_decision_trail(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)
        decision = _make_decision(
            source_artifact_ids=["a1"],
            involved_member_ids=["m1"],
        )

        mock_artifact = MagicMock()
        mock_artifact.id = "a1"
        mock_artifact.title = "Architecture Doc"
        mock_artifact.source_type = "markdown"
        mock_artifact.source_path = "/docs/arch.md"
        mock_artifact.ingested_at = datetime.now(UTC)

        mock_member = MagicMock()
        mock_member.id = "m1"
        mock_member.name = "Alice"
        mock_member.expertise_tags = ["python"]

        vector_store = MagicMock()
        vector_store.query.return_value = {"documents": [["Context chunk 1"]]}
        service.vector_store = vector_store

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db

            # search_decisions uses its own session, so patch it too
            with patch.object(service, "search_decisions", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = [
                    {
                        "id": "d1",
                        "title": "Use PostgreSQL",
                        "description": "PG for billing",
                        "context_summary": "ACID",
                        "decision_type": "technical",
                        "status": "active",
                        "confidence_score": 0.85,
                        "source_artifact_ids": ["a1"],
                        "source_chunk_ids": [],
                        "involved_member_ids": ["m1"],
                        "tags": [],
                        "alternatives_considered": ["MongoDB"],
                        "outcome_summary": None,
                        "decided_at": None,
                        "extracted_at": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                ]

                # Links query
                db.query.return_value.filter.return_value.all.return_value = []
                # Artifacts query
                artifacts_query = MagicMock()
                artifacts_query.all.return_value = [mock_artifact]
                # Members query
                members_query = MagicMock()
                members_query.all.return_value = [mock_member]

                # We need the filter calls to chain properly
                filter_results = [[], [mock_artifact], [mock_member]]
                call_idx = [0]

                def _filter_all(*args, **kwargs):
                    m = MagicMock()
                    idx = call_idx[0]
                    call_idx[0] += 1
                    if idx == 0:
                        m.all.return_value = []  # links
                        return m
                    elif idx == 1:
                        m.all.return_value = [mock_artifact]  # artifacts
                        return m
                    else:
                        m.all.return_value = [mock_member]  # members
                        return m

                db.query.return_value.filter.side_effect = _filter_all

                result = await service.why_did_we("Why did we choose PostgreSQL?")

        assert result["question"] == "Why did we choose PostgreSQL?"
        assert "answer" in result
        assert len(result["decision_trail"]) >= 1
        assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_handles_no_matching_decisions(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)

        with patch.object(service, "search_decisions", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            with patch("app.services.decision_search.create_session") as mock_create:
                db = MagicMock()
                mock_create.return_value = db

                result = await service.why_did_we("Why did we use quantum computing?")

        assert result["confidence"] == 0.0
        assert result["decision_trail"] == []
        assert "No relevant decisions" in result["answer"]

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self, mock_llm, mock_embedder):
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        service = DecisionSearchService(
            llm_service=mock_llm,
            embedding_service=mock_embedder,
            vector_store=MagicMock(),
        )

        decision_dict = {
            "id": "d1",
            "title": "Use Redis",
            "description": "For caching",
            "context_summary": "Need speed",
            "decision_type": "technical",
            "status": "active",
            "confidence_score": 0.7,
            "source_artifact_ids": [],
            "source_chunk_ids": [],
            "involved_member_ids": [],
            "tags": [],
            "alternatives_considered": ["Memcached"],
            "outcome_summary": None,
            "decided_at": None,
            "extracted_at": None,
            "created_at": None,
            "updated_at": None,
        }

        with patch.object(service, "search_decisions", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [decision_dict]

            with patch("app.services.decision_search.create_session") as mock_create:
                db = MagicMock()
                mock_create.return_value = db
                db.query.return_value.filter.return_value.all.return_value = []

                result = await service.why_did_we("Why Redis?")

        # Should return a fallback answer, not crash
        assert "answer" in result
        assert "Use Redis" in result["answer"]

    @pytest.mark.asyncio
    async def test_includes_sources_in_response(self, mock_llm, mock_embedder):
        mock_llm.generate = AsyncMock(return_value="Synthesized answer")
        service = DecisionSearchService(
            llm_service=mock_llm,
            embedding_service=mock_embedder,
            vector_store=MagicMock(),
        )

        decision_dict = {
            "id": "d1",
            "title": "Use PostgreSQL",
            "description": "PG for billing",
            "context_summary": "ACID",
            "decision_type": "technical",
            "status": "active",
            "confidence_score": 0.8,
            "source_artifact_ids": ["a1"],
            "source_chunk_ids": [],
            "involved_member_ids": [],
            "tags": [],
            "alternatives_considered": [],
            "outcome_summary": None,
            "decided_at": None,
            "extracted_at": None,
            "created_at": None,
            "updated_at": None,
        }

        mock_artifact = MagicMock()
        mock_artifact.id = "a1"
        mock_artifact.title = "Architecture Doc"
        mock_artifact.source_type = "markdown"
        mock_artifact.source_path = "/docs/arch.md"
        mock_artifact.ingested_at = datetime.now(UTC)

        with patch.object(service, "search_decisions", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [decision_dict]

            with patch("app.services.decision_search.create_session") as mock_create:
                db = MagicMock()
                mock_create.return_value = db

                # links -> empty, artifacts -> [mock_artifact], members -> []
                call_idx = [0]

                def _filter_side(*args, **kwargs):
                    m = MagicMock()
                    idx = call_idx[0]
                    call_idx[0] += 1
                    if idx == 0:
                        m.all.return_value = []
                        return m
                    elif idx == 1:
                        m.all.return_value = [mock_artifact]
                        return m
                    else:
                        m.all.return_value = []
                        return m

                db.query.return_value.filter.side_effect = _filter_side

                result = await service.why_did_we("Why PostgreSQL?")

        assert "sources" in result
        assert len(result["sources"]) == 1
        assert result["sources"][0]["id"] == "a1"

    @pytest.mark.asyncio
    async def test_includes_related_members(self, mock_llm, mock_embedder):
        mock_llm.generate = AsyncMock(return_value="Synthesized answer")
        service = DecisionSearchService(
            llm_service=mock_llm,
            embedding_service=mock_embedder,
            vector_store=MagicMock(),
        )

        decision_dict = {
            "id": "d1",
            "title": "Adopt TypeScript",
            "description": "TS for frontend",
            "context_summary": "Type safety",
            "decision_type": "technical",
            "status": "active",
            "confidence_score": 0.9,
            "source_artifact_ids": [],
            "source_chunk_ids": [],
            "involved_member_ids": ["m1"],
            "tags": [],
            "alternatives_considered": [],
            "outcome_summary": None,
            "decided_at": None,
            "extracted_at": None,
            "created_at": None,
            "updated_at": None,
        }

        mock_member = MagicMock()
        mock_member.id = "m1"
        mock_member.name = "Bob"
        mock_member.expertise_tags = ["typescript", "react"]

        with patch.object(service, "search_decisions", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [decision_dict]

            with patch("app.services.decision_search.create_session") as mock_create:
                db = MagicMock()
                mock_create.return_value = db

                call_idx = [0]

                def _filter_side(*args, **kwargs):
                    m = MagicMock()
                    idx = call_idx[0]
                    call_idx[0] += 1
                    if idx == 0:
                        m.all.return_value = []  # links
                        return m
                    elif idx == 1:
                        m.all.return_value = [mock_member]  # members
                        return m
                    else:
                        m.all.return_value = []
                        return m

                db.query.return_value.filter.side_effect = _filter_side

                result = await service.why_did_we("Why TypeScript?")

        assert "related_members" in result
        assert len(result["related_members"]) == 1
        assert result["related_members"][0]["name"] == "Bob"


# ---------------------------------------------------------------------------
# TestDecisionTimeline
# ---------------------------------------------------------------------------


class TestDecisionTimeline:
    @pytest.mark.asyncio
    async def test_returns_chronological_decisions(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)

        d1 = _make_decision(decision_id="d1", title="First decision", decided_at=datetime(2025, 1, 1, tzinfo=UTC))
        d2 = _make_decision(decision_id="d2", title="Second decision", decided_at=datetime(2025, 6, 1, tzinfo=UTC))

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            query_mock = MagicMock()
            db.query.return_value.filter.return_value = query_mock
            query_mock.order_by.return_value.limit.return_value.all.return_value = [d1, d2]

            result = await service.get_decision_timeline("database")

        assert len(result) == 2
        assert result[0]["title"] == "First decision"
        assert result[1]["title"] == "Second decision"
        # Each entry should have an effective_date field
        assert "effective_date" in result[0]

    @pytest.mark.asyncio
    async def test_empty_topic_returns_empty(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)

        with patch("app.services.decision_search.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            query_mock = MagicMock()
            db.query.return_value.filter.return_value = query_mock
            query_mock.order_by.return_value.limit.return_value.all.return_value = []

            result = await service.get_decision_timeline("nonexistent_topic")

        assert result == []


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_build_fallback_answer_with_decisions(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)
        decisions = [
            {"title": "Use Redis", "context_summary": "Speed", "alternatives_considered": ["Memcached"]},
        ]
        answer = service._build_fallback_answer(decisions)
        assert "Use Redis" in answer
        assert "Speed" in answer
        assert "Memcached" in answer

    def test_build_fallback_answer_empty(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)
        answer = service._build_fallback_answer([])
        assert "No relevant decisions" in answer

    def test_format_decisions_for_prompt_empty(self, mock_llm, mock_embedder):
        service = _build_service(mock_llm, mock_embedder)
        result = service._format_decisions_for_prompt([])
        assert "No decisions found" in result

    def test_cosine_similarity_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert DecisionSearchService._cosine_similarity(a, b) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert DecisionSearchService._cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert DecisionSearchService._cosine_similarity(a, b) == 0.0
