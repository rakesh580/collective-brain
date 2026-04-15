"""Unit tests for InsightEngine — weekly summaries, pattern detection, LLM parsing."""

from unittest.mock import AsyncMock

import pytest

from app.services.insight_engine import InsightEngine


@pytest.fixture()
def engine(db_session, mock_llm):
    return InsightEngine(db=db_session, llm=mock_llm)


class TestWeeklySummary:
    @pytest.mark.asyncio
    async def test_empty_contributions(self, engine):
        engine.llm.generate = AsyncMock(
            return_value="No significant activity this week.\n\nAccomplishments:\n- No contributions\n\nRecommendations:\n- Increase activity"
        )
        result = await engine.generate_weekly_summary()
        assert result is not None
        assert result.insight_type == "weekly_summary"

    @pytest.mark.asyncio
    async def test_with_contributions(self, engine, seed_members, seed_artifacts):
        engine.llm.generate = AsyncMock(
            return_value="Great week!\n\nAccomplishments:\n- Alice committed 3 changes\n- Bob fixed bugs\n\nRecommendations:\n- Continue the momentum"
        )
        result = await engine.generate_weekly_summary()
        assert result.title is not None
        assert result.body is not None


class TestPatternDetection:
    @pytest.mark.asyncio
    async def test_returns_patterns_list(self, engine, seed_members, seed_artifacts):
        engine.llm.generate = AsyncMock(
            return_value='```json\n[{"title": "Bus Factor Risk", "description": "Only one person knows auth", "severity": "high", "affected_members": ["alice"]}]\n```'
        )
        patterns = await engine.detect_patterns()
        assert isinstance(patterns, list)

    @pytest.mark.asyncio
    async def test_handles_llm_json_failure(self, engine, seed_members, seed_artifacts):
        engine.llm.generate = AsyncMock(return_value="This is not JSON at all.")
        patterns = await engine.detect_patterns()
        # Should still return graph-based patterns, not crash
        assert isinstance(patterns, list)


class TestHelpers:
    def test_extract_list_section(self, engine):
        # _extract_list_section requires ":" or "#" in the section header line
        text = "Some intro.\n\nHighlights:\n- Item one\n- Item two\n\nOther section:"
        items = engine._extract_list_section(text, "highlights")
        assert len(items) == 2
        assert "Item one" in items[0]

    def test_extract_list_section_missing(self, engine):
        text = "No sections here"
        items = engine._extract_list_section(text, "highlights")
        assert items == []

    def test_parse_llm_insights_valid_json(self, engine):
        response = '```json\n[{"title": "Test", "description": "Desc"}]\n```'
        parsed = engine._parse_llm_insights(response)
        assert len(parsed) == 1
        assert parsed[0]["title"] == "Test"

    def test_parse_llm_insights_bare_json(self, engine):
        response = '[{"title": "Test", "description": "Desc"}]'
        parsed = engine._parse_llm_insights(response)
        assert len(parsed) == 1

    def test_parse_llm_insights_invalid(self, engine):
        parsed = engine._parse_llm_insights("not json at all")
        assert parsed == []
