"""Unit tests for KnowledgeVerificationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.models.artifact import ArtifactRecord
from app.models.insight import InsightRecord
from app.services.knowledge_verification import KnowledgeVerificationService, _ensure_tz


def _make_insight(**kwargs) -> InsightRecord:
    defaults = dict(
        id="ins-1",
        title="Test insight",
        body="Some insight body",
        insight_type="pattern",
        generated_at=datetime.now(UTC) - timedelta(days=5),
        source_artifact_ids=[],
        verification_status="pending",
        staleness_days=None,
        verified_at=None,
        verified_by=None,
        organization_id=None,
        confidence=0.8,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=InsightRecord)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_artifact(ingested_days_ago: int, **kwargs) -> ArtifactRecord:
    obj = MagicMock(spec=ArtifactRecord)
    obj.id = kwargs.get("id", "art-1")
    obj.ingested_at = datetime.now(UTC) - timedelta(days=ingested_days_ago)
    obj.last_synced_at = kwargs.get("last_synced_at")
    return obj


class TestVerifyInsightStaleness:
    def test_fresh_insight_no_artifacts_is_verified(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        insight = _make_insight(
            generated_at=datetime.now(UTC) - timedelta(days=3),
            source_artifact_ids=[],
        )
        result = svc.verify_insight(db, insight)
        assert result.status == "verified"
        assert result.staleness_days == 3

    def test_old_insight_no_artifacts_is_outdated(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        insight = _make_insight(
            generated_at=datetime.now(UTC) - timedelta(days=45),
            source_artifact_ids=[],
        )
        result = svc.verify_insight(db, insight)
        assert result.status == "outdated"
        assert result.staleness_days >= 45

    def test_fresh_artifacts_gives_verified(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        artifact = _make_artifact(ingested_days_ago=5, id="art-1")
        db.query.return_value.filter.return_value.all.return_value = [artifact]
        insight = _make_insight(source_artifact_ids=["art-1"])
        result = svc.verify_insight(db, insight)
        assert result.status == "verified"
        assert result.staleness_days == 5

    def test_stale_artifact_gives_outdated(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        artifact = _make_artifact(ingested_days_ago=60, id="art-1")
        db.query.return_value.filter.return_value.all.return_value = [artifact]
        insight = _make_insight(source_artifact_ids=["art-1"])
        result = svc.verify_insight(db, insight)
        assert result.status == "outdated"
        assert result.staleness_days >= 60

    def test_deleted_artifacts_gives_outdated(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        insight = _make_insight(source_artifact_ids=["art-gone"])
        result = svc.verify_insight(db, insight)
        assert result.status == "outdated"
        assert any("deleted" in r.lower() for r in result.reasons)

    def test_last_synced_at_takes_precedence_over_ingested_at(self):
        """If last_synced_at is recent, artifact should not be stale even if ingested long ago."""
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        artifact = _make_artifact(
            ingested_days_ago=90,
            id="art-1",
            last_synced_at=datetime.now(UTC) - timedelta(days=2),
        )
        db.query.return_value.filter.return_value.all.return_value = [artifact]
        insight = _make_insight(source_artifact_ids=["art-1"])
        result = svc.verify_insight(db, insight)
        assert result.status == "verified"
        assert result.staleness_days == 2

    def test_persists_results_to_insight(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        insight = _make_insight(source_artifact_ids=[])
        svc.verify_insight(db, insight, verifier_user_id="user-1")
        assert insight.verified_at is not None
        assert insight.verified_by == "user-1"
        db.commit.assert_called()


class TestBulkVerify:
    def test_bulk_returns_summary_dict(self):
        svc = KnowledgeVerificationService(staleness_threshold_days=30)
        db = MagicMock()
        # Return 2 pending insights: one fresh, one 45 days old
        fresh = _make_insight(
            id="ins-fresh",
            generated_at=datetime.now(UTC) - timedelta(days=5),
            source_artifact_ids=[],
        )
        stale = _make_insight(
            id="ins-stale",
            generated_at=datetime.now(UTC) - timedelta(days=50),
            source_artifact_ids=[],
        )
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = [fresh, stale]
        summary = svc.bulk_verify(db)
        assert isinstance(summary, dict)
        assert "verified" in summary
        assert "outdated" in summary


class TestEnsureTz:
    def test_naive_datetime_gets_utc(self):
        naive = datetime(2025, 1, 1, 12, 0, 0)
        result = _ensure_tz(naive)
        assert result.tzinfo is not None

    def test_aware_datetime_unchanged(self):
        aware = datetime(2025, 1, 1, tzinfo=UTC)
        result = _ensure_tz(aware)
        assert result == aware

    def test_none_returns_now(self):
        result = _ensure_tz(None)
        assert result is not None
        assert result.tzinfo is not None


class TestIngestRequestSchemas:
    def test_notion_request_with_database_id(self):
        from app.schemas.requests import NotionIngestRequest

        req = NotionIngestRequest(database_id="db-123")
        assert req.to_source_input() == {"database_id": "db-123"}

    def test_notion_request_with_page_id(self):
        from app.schemas.requests import NotionIngestRequest

        req = NotionIngestRequest(page_id="page-456")
        assert req.to_source_input() == {"page_id": "page-456"}

    def test_notion_request_requires_one_field(self):
        from app.schemas.requests import NotionIngestRequest

        req = NotionIngestRequest()
        with pytest.raises(ValueError):
            req.to_source_input()

    def test_google_docs_with_doc_ids(self):
        from app.schemas.requests import GoogleDocsIngestRequest

        req = GoogleDocsIngestRequest(document_ids=["doc-1", "doc-2"])
        assert req.to_source_input() == {"document_ids": ["doc-1", "doc-2"]}

    def test_google_docs_with_folder(self):
        from app.schemas.requests import GoogleDocsIngestRequest

        req = GoogleDocsIngestRequest(folder_id="folder-abc")
        assert req.to_source_input() == {"folder_id": "folder-abc"}

    def test_confluence_with_space_key(self):
        from app.schemas.requests import ConfluenceIngestRequest

        req = ConfluenceIngestRequest(space_key="ENG")
        assert req.to_source_input() == {"space_key": "ENG"}

    def test_confluence_with_page_ids(self):
        from app.schemas.requests import ConfluenceIngestRequest

        req = ConfluenceIngestRequest(page_ids=["123", "456"])
        assert req.to_source_input() == {"page_ids": ["123", "456"]}


class TestConnectorUtils:
    def test_content_hash_is_deterministic(self):
        from app.ingestion.utils import content_hash

        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_content_hash_normalises_whitespace(self):
        from app.ingestion.utils import content_hash

        assert content_hash("hello  world") == content_hash("hello world")

    def test_different_texts_give_different_hashes(self):
        from app.ingestion.utils import content_hash

        assert content_hash("foo") != content_hash("bar")

    def test_extract_topics_finds_tech_terms(self):
        from app.ingestion.utils import extract_topics_from_text

        topics = extract_topics_from_text("We use FastAPI backend with PostgreSQL and Redis")
        assert "backend" in topics
        assert "redis" in topics
        assert "postgresql" in topics

    def test_extract_topics_is_capped(self):
        from app.ingestion.utils import extract_topics_from_text

        long_text = " ".join(
            [
                "api",
                "backend",
                "docker",
                "kubernetes",
                "redis",
                "kafka",
                "python",
                "react",
                "sql",
                "aws",
                "gcp",
                "azure",
            ]
        )
        topics = extract_topics_from_text(long_text, max_topics=5)
        assert len(topics) <= 5

    def test_slugify(self):
        from app.ingestion.utils import slugify

        assert slugify("Hello World!") == "hello-world"
        assert slugify("API Backend") == "api-backend"


class TestNotionBlockParsing:
    """Test the static _block_to_text helper without hitting the API."""

    def _make_block(self, btype: str, text: str, **extra) -> dict:
        block = {
            "type": btype,
            btype: {
                "rich_text": [{"plain_text": text}],
                **extra,
            },
        }
        return block

    def test_paragraph_returns_text(self):
        from app.ingestion.notion_connector import NotionConnector

        block = self._make_block("paragraph", "Hello paragraph")
        # We call the static method directly — no API needed
        result = NotionConnector._block_to_text(block)
        assert result == "Hello paragraph"

    def test_heading_1_prefixed(self):
        from app.ingestion.notion_connector import NotionConnector

        block = self._make_block("heading_1", "Big Title")
        result = NotionConnector._block_to_text(block)
        assert result == "# Big Title"

    def test_heading_3_prefixed(self):
        from app.ingestion.notion_connector import NotionConnector

        block = self._make_block("heading_3", "Small Heading")
        result = NotionConnector._block_to_text(block)
        assert result == "### Small Heading"

    def test_bulleted_list(self):
        from app.ingestion.notion_connector import NotionConnector

        block = self._make_block("bulleted_list_item", "Item one")
        result = NotionConnector._block_to_text(block)
        assert result == "• Item one"

    def test_code_block(self):
        from app.ingestion.notion_connector import NotionConnector

        block = {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "print('hi')"}],
                "language": "python",
            },
        }
        result = NotionConnector._block_to_text(block)
        assert "python" in result
        assert "print('hi')" in result

    def test_unknown_block_returns_empty(self):
        from app.ingestion.notion_connector import NotionConnector

        block = {"type": "image", "image": {}}
        result = NotionConnector._block_to_text(block)
        assert result == ""


class TestGoogleDocToText:
    def test_extracts_paragraphs(self):
        from app.ingestion.google_docs_connector import GoogleDocsConnector

        doc = {
            "title": "Test Doc",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "elements": [{"textRun": {"content": "Hello world"}}],
                        }
                    }
                ]
            },
        }
        text = GoogleDocsConnector._doc_to_text(doc)
        assert "Hello world" in text

    def test_headings_get_hash_prefix(self):
        from app.ingestion.google_docs_connector import GoogleDocsConnector

        doc = {
            "title": "Test",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "HEADING_2"},
                            "elements": [{"textRun": {"content": "Section Title"}}],
                        }
                    }
                ]
            },
        }
        text = GoogleDocsConnector._doc_to_text(doc)
        assert "## Section Title" in text

    def test_empty_paragraphs_skipped(self):
        from app.ingestion.google_docs_connector import GoogleDocsConnector

        doc = {
            "title": "Test",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "elements": [{"textRun": {"content": "   "}}],
                        }
                    }
                ]
            },
        }
        text = GoogleDocsConnector._doc_to_text(doc)
        assert text.strip() == ""


class TestConfluenceHtmlToText:
    def test_strips_html_tags(self):
        from app.ingestion.confluence_connector import _html_to_text

        html = "<h1>Title</h1><p>Some <b>bold</b> text here.</p>"
        result = _html_to_text(html)
        assert "Title" in result
        assert "bold" in result
        assert "<" not in result

    def test_empty_html(self):
        from app.ingestion.confluence_connector import _html_to_text

        assert _html_to_text("") == ""

    def test_code_block_preserved(self):
        from app.ingestion.confluence_connector import _html_to_text

        html = "<pre><code>def foo(): pass</code></pre>"
        result = _html_to_text(html)
        assert "def foo" in result
