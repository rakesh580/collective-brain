"""Confluence connector — ingests pages from a Confluence Space.

Authentication: CB_CONFLUENCE_URL  (e.g. https://yoursite.atlassian.net/wiki)
                CB_CONFLUENCE_USER (email/username)
                CB_CONFLUENCE_TOKEN (API token or password)

Source input:  dict with keys:
                 "space_key"   — ingest all pages in a space (e.g. "ENG"), OR
                 "page_ids"    — list of specific page IDs

Requires: atlassian-python-api
"""
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy
from app.ingestion.utils import content_hash, extract_topics_from_text

logger = logging.getLogger("collective_brain.ingestion.confluence")


class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-plain-text stripper for Confluence storage format."""
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).strip()


def _html_to_text(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


class ConfluenceConnector(BaseConnector):
    def __init__(
        self,
        url: str,
        username: str,
        token: str,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        cloud: bool = True,
    ):
        try:
            from atlassian import Confluence
        except ImportError:
            raise RuntimeError(
                "atlassian-python-api is not installed. "
                "Run: pip install atlassian-python-api"
            )
        self._confluence = Confluence(
            url=url,
            username=username,
            password=token,  # API token used as password for cloud
            cloud=cloud,
        )
        self._base_url = url.rstrip("/")
        self._chunker = ChunkingStrategy(chunk_size, chunk_overlap)

    def source_type(self) -> str:
        return "confluence"

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse(self, source_input: dict) -> list[ParsedChunk]:
        chunks: list[ParsedChunk] = []
        pages = self._collect_pages(source_input)
        for page in pages:
            try:
                chunks.extend(self._parse_page(page))
            except Exception as exc:
                logger.warning("Failed to parse Confluence page %s: %s", page.get("id"), exc)
        return chunks

    def extract_members(self, source_input: dict) -> list[dict]:
        members: dict[str, dict] = {}
        pages = self._collect_pages(source_input)
        for page in pages:
            version = page.get("version", {})
            by = version.get("by", {})
            username = by.get("username") or by.get("accountId", "")
            display_name = by.get("displayName", username)
            if username and username not in members:
                members[username] = {
                    "id": f"confluence-{username[:20]}",
                    "name": display_name,
                    "aliases": [display_name.lower()],
                }
        return list(members.values())

    # ── Private helpers ────────────────────────────────────────────────────────

    def _collect_pages(self, source_input: dict) -> list[dict]:
        if "page_ids" in source_input:
            return [
                self._confluence.get_page_by_id(pid, expand="body.storage,version")
                for pid in source_input["page_ids"]
            ]
        if "space_key" in source_input:
            return self._get_all_pages(source_input["space_key"])
        raise ValueError("source_input must have 'space_key' or 'page_ids'")

    def _get_all_pages(self, space_key: str) -> list[dict]:
        pages = []
        start = 0
        limit = 50
        while True:
            batch = self._confluence.get_all_pages_from_space(
                space_key,
                start=start,
                limit=limit,
                expand="body.storage,version",
            )
            if not batch:
                break
            pages.extend(batch)
            if len(batch) < limit:
                break
            start += limit
        logger.info("Confluence space %s: found %d pages", space_key, len(pages))
        return pages

    def _parse_page(self, page: dict) -> list[ParsedChunk]:
        page_id = page.get("id", "")
        title = page.get("title", "Untitled")
        body_html = page.get("body", {}).get("storage", {}).get("value", "")
        full_text = _html_to_text(body_html)

        if not full_text.strip():
            return []

        source_url = f"{self._base_url}/pages/{page_id}"
        # Try to get page URL from _links if available
        links = page.get("_links", {})
        if links.get("webui"):
            source_url = self._base_url + links["webui"]

        version = page.get("version", {})
        author_name = version.get("by", {}).get("displayName", "unknown")
        when_str = version.get("when")
        timestamp = None
        if when_str:
            try:
                timestamp = datetime.fromisoformat(when_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        topics = extract_topics_from_text(full_text)
        raw_chunks = self._chunker.split(full_text, metadata={"page_id": page_id})

        parsed: list[ParsedChunk] = []
        for rc in raw_chunks:
            chunk_text = rc["text"]
            parsed.append(ParsedChunk(
                text=chunk_text,
                source_type="confluence",
                source_ref=source_url,
                author=author_name,
                author_aliases=[author_name.lower()],
                timestamp=timestamp,
                topics=topics,
                chunk_metadata={
                    "page_id": page_id,
                    "title": title,
                    "source_url": source_url,
                    "space_key": page.get("space", {}).get("key", ""),
                    "content_hash": content_hash(chunk_text),
                    **rc.get("metadata", {}),
                },
            ))
        return parsed
