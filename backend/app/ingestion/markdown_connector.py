import os
import re
from datetime import datetime
from pathlib import Path

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy


class MarkdownConnector(BaseConnector):
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunker = ChunkingStrategy(chunk_size, chunk_overlap)

    def source_type(self) -> str:
        return "markdown"

    def parse(self, source_input: str) -> list[ParsedChunk]:
        """Parse all .md files from a directory path."""
        directory = Path(source_input)
        if not directory.is_dir():
            raise ValueError(f"Not a valid directory: {source_input}")

        chunks = []
        for md_file in sorted(directory.rglob("*.md")):
            chunks.extend(self._parse_file(md_file, directory))
        return chunks

    def extract_members(self, source_input: str) -> list[dict]:
        """Try to extract author info from YAML frontmatter."""
        directory = Path(source_input)
        members = {}
        for md_file in directory.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            author = self._extract_frontmatter_author(content)
            if author and author not in members:
                slug = re.sub(r"[^a-z0-9]+", "-", author.lower()).strip("-")
                members[author] = {
                    "name": author,
                    "aliases": [author.lower()],
                    "email": None,
                    "id": slug,
                }
        return list(members.values())

    def _parse_file(self, file_path: Path, base_dir: Path) -> list[ParsedChunk]:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        relative_path = str(file_path.relative_to(base_dir))
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

        # Extract frontmatter author
        author = self._extract_frontmatter_author(content)
        # Strip frontmatter
        content = self._strip_frontmatter(content)

        # Extract topics from path
        topics = self._extract_topics_from_path(relative_path)

        # Split by headings first
        sections = self._split_by_headings(content, title)

        chunks = []
        for section_title, section_text in sections:
            full_text = f"[Document: {title}] [{section_title}]\n{section_text}"
            sub_chunks = self.chunker.split(
                full_text,
                metadata={
                    "source_ref": relative_path,
                    "section": section_title,
                },
            )
            for sc in sub_chunks:
                chunks.append(
                    ParsedChunk(
                        text=sc["text"],
                        source_type="markdown",
                        source_ref=relative_path,
                        author=author,
                        timestamp=datetime.fromtimestamp(os.path.getmtime(file_path)),
                        topics=topics,
                        chunk_metadata=sc["metadata"],
                    )
                )
        return chunks

    def _split_by_headings(self, content: str, doc_title: str) -> list[tuple[str, str]]:
        lines = content.split("\n")
        sections: list[tuple[str, str]] = []
        current_heading = doc_title
        current_lines: list[str] = []

        for line in lines:
            heading_match = re.match(r"^(#{1,4})\s+(.+)", line)
            if heading_match:
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        sections.append((current_heading, text))
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                sections.append((current_heading, text))

        if not sections:
            sections.append((doc_title, content.strip()))

        return sections

    def _extract_frontmatter_author(self, content: str) -> str | None:
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if match:
            frontmatter = match.group(1)
            author_match = re.search(r"author:\s*(.+)", frontmatter)
            if author_match:
                return author_match.group(1).strip().strip("\"'")
        return None

    def _strip_frontmatter(self, content: str) -> str:
        return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, count=1, flags=re.DOTALL)

    def _extract_topics_from_path(self, path: str) -> list[str]:
        parts = Path(path).parts
        topics = []
        for part in parts[:-1]:  # Exclude filename
            cleaned = part.replace("-", " ").replace("_", " ").lower()
            if cleaned and cleaned not in ("docs", "doc", "documents", "notes"):
                topics.append(cleaned)
        # Also add filename-derived topic
        stem = Path(path).stem.replace("-", " ").replace("_", " ").lower()
        if stem:
            topics.append(stem)
        return topics
