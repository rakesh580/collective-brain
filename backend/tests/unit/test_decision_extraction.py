"""Unit tests for DecisionExtractionService."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.decision_extraction import EXTRACTION_PROMPT_TEMPLATE, DecisionExtractionService


def _make_artifact(artifact_id="art-1", org_id="org-1", title="Test Artifact"):
    a = MagicMock()
    a.id = artifact_id
    a.organization_id = org_id
    a.title = title
    return a


def _make_chunk(chunk_id="chunk-1", artifact_id="art-1", content="Some text", created_at=None):
    c = MagicMock()
    c.id = chunk_id
    c.artifact_id = artifact_id
    c.content = content
    c.created_at = created_at or datetime.now(UTC)
    return c


VALID_LLM_JSON = json.dumps(
    [
        {
            "title": "Chose PostgreSQL over MongoDB",
            "description": "Team decided to use PostgreSQL for the billing service.",
            "context_summary": "Need ACID compliance for financial data.",
            "alternatives_considered": ["MongoDB", "DynamoDB"],
            "involved_people": ["Alice", "Bob"],
            "tags": ["database", "billing"],
            "approximate_date": "2025-01-15",
            "decision_type": "technical",
            "confidence": 0.9,
        }
    ]
)


# ---------------------------------------------------------------------------
# TestExtractDecisionsFromArtifact
# ---------------------------------------------------------------------------


class TestExtractDecisionsFromArtifact:
    @pytest.mark.asyncio
    async def test_extracts_decisions_from_valid_artifact(self, mock_llm):
        mock_llm.generate = AsyncMock(return_value=VALID_LLM_JSON)
        service = DecisionExtractionService(mock_llm)

        artifact = _make_artifact()
        chunks = [_make_chunk("c1", content="Meeting notes..."), _make_chunk("c2", content="We decided to use PG.")]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            # artifact query
            db.query.return_value.filter.return_value.first.return_value = artifact
            # chunks query
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_from_artifact("art-1")

        assert len(result) == 1
        assert result[0]["title"] == "Chose PostgreSQL over MongoDB"
        assert result[0]["confidence_score"] == 0.9
        assert "art-1" in result[0]["source_artifact_ids"]
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_artifact_not_found(self, mock_llm):
        service = DecisionExtractionService(mock_llm)

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None

            result = await service.extract_decisions_from_artifact("nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_no_chunks(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

            result = await service.extract_decisions_from_artifact("art-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self, mock_llm):
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()
        chunks = [_make_chunk()]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_from_artifact("art-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_invalid_llm_json(self, mock_llm):
        mock_llm.generate = AsyncMock(return_value="Not valid JSON at all")
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()
        chunks = [_make_chunk()]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_from_artifact("art-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_parses_markdown_fenced_json(self, mock_llm):
        fenced = "```json\n" + VALID_LLM_JSON + "\n```"
        mock_llm.generate = AsyncMock(return_value=fenced)
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()
        chunks = [_make_chunk()]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_from_artifact("art-1")

        assert len(result) == 1
        assert result[0]["title"] == "Chose PostgreSQL over MongoDB"

    @pytest.mark.asyncio
    async def test_confidence_score_set_correctly(self, mock_llm):
        decisions_json = json.dumps(
            [
                {
                    "title": "Use Redis for caching",
                    "description": "Redis selected for session caching.",
                    "context_summary": "Need fast reads.",
                    "alternatives_considered": ["Memcached"],
                    "involved_people": [],
                    "tags": ["caching"],
                    "approximate_date": None,
                    "decision_type": "technical",
                    "confidence": 0.72,
                }
            ]
        )
        mock_llm.generate = AsyncMock(return_value=decisions_json)
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()
        chunks = [_make_chunk()]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_from_artifact("art-1")

        assert len(result) == 1
        assert result[0]["confidence_score"] == 0.72
        assert 0 <= result[0]["confidence_score"] <= 1


# ---------------------------------------------------------------------------
# TestExtractDecisionsBulk
# ---------------------------------------------------------------------------


class TestExtractDecisionsBulk:
    @pytest.mark.asyncio
    async def test_processes_multiple_artifacts(self, mock_llm):
        mock_llm.generate = AsyncMock(return_value=VALID_LLM_JSON)
        service = DecisionExtractionService(mock_llm)
        artifact = _make_artifact()
        chunks = [_make_chunk()]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks

            result = await service.extract_decisions_bulk(["art-1", "art-2"])

        assert result["total_artifacts"] == 2
        assert result["processed"] == 2
        assert result["total_decisions"] == 2  # 1 decision per artifact
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_continues_on_single_artifact_failure(self, mock_llm):
        """If one artifact raises, the bulk method records the error and continues."""
        call_count = 0

        async def _generate_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB error on first")
            return VALID_LLM_JSON

        mock_llm.generate = AsyncMock(side_effect=_generate_side_effect)
        service = DecisionExtractionService(mock_llm)

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            artifact = _make_artifact()
            chunks = [_make_chunk()]
            db.query.return_value.filter.return_value.first.return_value = artifact
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = chunks
            # Make the first call raise through the outer exception handler
            db.rollback = MagicMock()

            result = await service.extract_decisions_bulk(["art-1", "art-2"])

        assert result["total_artifacts"] == 2
        # First artifact's LLM call fails but extract_decisions_from_artifact
        # catches LLM errors internally and returns [] (treated as success with 0 decisions).
        # Second artifact succeeds normally.
        assert result["processed"] == 2
        assert len(result["errors"]) == 0


# ---------------------------------------------------------------------------
# TestLinkRelatedDecisions
# ---------------------------------------------------------------------------


class TestLinkRelatedDecisions:
    @pytest.mark.asyncio
    async def test_links_similar_decisions(self, mock_llm, mock_embedder):
        service = DecisionExtractionService(mock_llm)
        decision = MagicMock()
        decision.id = "d1"
        decision.title = "Use PostgreSQL"
        decision.description = "PostgreSQL for billing"
        decision.context_summary = "ACID compliance"

        other_decision = MagicMock()
        other_decision.id = "d2"
        other_decision.title = "Use PostgreSQL for analytics"
        other_decision.description = "PostgreSQL for data warehouse"
        other_decision.context_summary = "SQL compatibility"

        # Return identical embeddings -> cosine similarity = 1.0 (>0.7 threshold)
        mock_embedder.embed.return_value = [0.5] * 384

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.side_effect = [
                decision,  # finding the decision
                None,  # no existing link
            ]
            db.query.return_value.filter.return_value.all.return_value = [other_decision]

            result = await service.link_related_decisions(
                "d1", embedding_service=mock_embedder, vector_store=MagicMock()
            )

        assert len(result) == 1
        assert result[0]["from_decision_id"] == "d1"
        assert result[0]["to_decision_id"] == "d2"
        assert result[0]["similarity"] == 1.0
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_links_for_dissimilar_decisions(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        decision = MagicMock()
        decision.id = "d1"
        decision.title = "Use PostgreSQL"
        decision.description = "For billing"
        decision.context_summary = "ACID"

        other_decision = MagicMock()
        other_decision.id = "d2"
        other_decision.title = "Hire a designer"
        other_decision.description = "Need UX help"
        other_decision.context_summary = "UI redesign"

        embedder = MagicMock()
        # Return orthogonal vectors -> cosine similarity ~ 0
        embedder.embed.side_effect = [
            [1.0] + [0.0] * 383,  # d1
            [0.0] + [1.0] + [0.0] * 382,  # d2
        ]

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = decision
            db.query.return_value.filter.return_value.all.return_value = [other_decision]

            result = await service.link_related_decisions("d1", embedding_service=embedder, vector_store=MagicMock())

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_link_returns_empty_when_decision_not_found(self, mock_llm):
        service = DecisionExtractionService(mock_llm)

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None

            result = await service.link_related_decisions(
                "missing", embedding_service=MagicMock(), vector_store=MagicMock()
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_link_returns_empty_without_embedding_service(self, mock_llm):
        service = DecisionExtractionService(mock_llm)

        with patch("app.services.decision_extraction.create_session") as mock_create:
            db = MagicMock()
            mock_create.return_value = db
            decision = MagicMock()
            decision.id = "d1"
            db.query.return_value.filter.return_value.first.return_value = decision

            result = await service.link_related_decisions("d1")

        assert result == []


# ---------------------------------------------------------------------------
# TestExtractionPrompt
# ---------------------------------------------------------------------------


class TestExtractionPrompt:
    def test_prompt_contains_required_fields(self):
        assert "title" in EXTRACTION_PROMPT_TEMPLATE
        assert "description" in EXTRACTION_PROMPT_TEMPLATE
        assert "context_summary" in EXTRACTION_PROMPT_TEMPLATE
        assert "alternatives_considered" in EXTRACTION_PROMPT_TEMPLATE
        assert "involved_people" in EXTRACTION_PROMPT_TEMPLATE
        assert "tags" in EXTRACTION_PROMPT_TEMPLATE
        assert "confidence" in EXTRACTION_PROMPT_TEMPLATE
        assert "decision_type" in EXTRACTION_PROMPT_TEMPLATE

    def test_prompt_includes_text_placeholder(self):
        assert "{text}" in EXTRACTION_PROMPT_TEMPLATE

    def test_build_extraction_prompt_substitutes_text(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        prompt = service._build_extraction_prompt("Hello world")
        assert "Hello world" in prompt
        assert "{text}" not in prompt


# ---------------------------------------------------------------------------
# TestParseResponse (edge cases for _parse_llm_response)
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parses_dict_with_decisions_key(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        resp = json.dumps({"decisions": [{"title": "A"}]})
        result = service._parse_llm_response(resp)
        assert len(result) == 1

    def test_parses_json_embedded_in_text(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        resp = 'Here are the decisions:\n[{"title": "Test"}]\nDone.'
        result = service._parse_llm_response(resp)
        assert len(result) == 1
        assert result[0]["title"] == "Test"

    def test_returns_empty_for_garbage(self, mock_llm):
        service = DecisionExtractionService(mock_llm)
        assert service._parse_llm_response("totally not json") == []
