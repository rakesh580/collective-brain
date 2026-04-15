from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestMarkdownConnector:
    def test_parse_markdown_directory(self):
        from app.ingestion.markdown_connector import MarkdownConnector

        connector = MarkdownConnector(chunk_size=512, chunk_overlap=64)
        chunks = connector.parse(str(FIXTURES_DIR))

        # Should find at least the sample_doc.md
        assert len(chunks) > 0
        assert all(c.source_type == "markdown" for c in chunks)

    def test_extract_author_from_frontmatter(self):
        from app.ingestion.markdown_connector import MarkdownConnector

        connector = MarkdownConnector()
        members = connector.extract_members(str(FIXTURES_DIR))

        # sample_doc.md has author: Alice Smith
        names = [m["name"] for m in members]
        assert "Alice Smith" in names

    def test_heading_based_splitting(self):
        from app.ingestion.markdown_connector import MarkdownConnector

        connector = MarkdownConnector(chunk_size=512, chunk_overlap=64)
        chunks = connector.parse(str(FIXTURES_DIR))

        # Should have multiple chunks from heading splits
        source_refs = [c.source_ref for c in chunks if "sample_doc" in c.source_ref]
        assert len(source_refs) > 1  # Multiple sections


class TestTaskConnector:
    def test_parse_csv_tasks(self):
        from app.ingestion.task_connector import TaskConnector

        connector = TaskConnector()
        csv_path = str(FIXTURES_DIR / "sample_tasks.csv")
        chunks = connector.parse(csv_path)

        assert len(chunks) == 5
        assert all(c.source_type == "tasks" for c in chunks)

    def test_extract_members_from_tasks(self):
        from app.ingestion.task_connector import TaskConnector

        connector = TaskConnector()
        csv_path = str(FIXTURES_DIR / "sample_tasks.csv")
        members = connector.extract_members(csv_path)

        names = {m["name"] for m in members}
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names


class TestDiscordConnector:
    def test_parse_discord_export(self):
        from app.ingestion.discord_connector import DiscordConnector

        connector = DiscordConnector(chunk_size=512, chunk_overlap=64)
        json_path = str(FIXTURES_DIR / "sample_discord_export.json")
        chunks = connector.parse(json_path)

        assert len(chunks) > 0
        assert all(c.source_type == "discord" for c in chunks)

    def test_message_grouping(self):
        from app.ingestion.discord_connector import DiscordConnector

        connector = DiscordConnector()
        json_path = str(FIXTURES_DIR / "sample_discord_export.json")
        chunks = connector.parse(json_path)

        # Alice's two messages within 1 min should be grouped
        alice_chunks = [c for c in chunks if c.author == "Alice"]
        assert len(alice_chunks) == 1  # Grouped into one
        assert "restructure" in alice_chunks[0].text
        assert "splitting" in alice_chunks[0].text

    def test_extract_discord_members(self):
        from app.ingestion.discord_connector import DiscordConnector

        connector = DiscordConnector()
        json_path = str(FIXTURES_DIR / "sample_discord_export.json")
        members = connector.extract_members(json_path)

        names = {m["name"] for m in members}
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names


class TestChunker:
    def test_small_text_no_split(self):
        from app.ingestion.chunker import ChunkingStrategy

        chunker = ChunkingStrategy(chunk_size=512)
        result = chunker.split("Hello world")
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_large_text_splits(self):
        from app.ingestion.chunker import ChunkingStrategy

        chunker = ChunkingStrategy(chunk_size=50, chunk_overlap=10)
        text = "This is a sentence. " * 20  # ~400 chars
        result = chunker.split(text)
        assert len(result) > 1
        assert all(r["text"] for r in result)
