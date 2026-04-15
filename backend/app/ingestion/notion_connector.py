"""Notion connector — ingests pages from a Notion database or page tree.

Authentication: Notion Integration Token (CB_NOTION_TOKEN).
Source input:   dict with keys:
                  "database_id"  — ingest all pages in a database, OR
                  "page_id"      — ingest a single page and its children

The connector walks the block tree, concatenates rich-text content, and
produces one ParsedChunk per logical section (heading → next heading).
"""

import contextlib
import logging
from datetime import datetime

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy
from app.ingestion.utils import content_hash, extract_topics_from_text

logger = logging.getLogger("collective_brain.ingestion.notion")


class NotionConnector(BaseConnector):
    def __init__(self, token: str, chunk_size: int = 512, chunk_overlap: int = 64):
        try:
            from notion_client import Client
        except ImportError:
            raise RuntimeError("notion-client is not installed. Run: pip install notion-client")
        self._client = Client(auth=token)
        self._chunker = ChunkingStrategy(chunk_size, chunk_overlap)

    def source_type(self) -> str:
        return "notion"

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse(self, source_input: dict) -> list[ParsedChunk]:
        chunks: list[ParsedChunk] = []
        page_ids = self._collect_page_ids(source_input)
        for page_id in page_ids:
            try:
                chunks.extend(self._parse_page(page_id))
            except Exception as exc:
                logger.warning("Failed to parse Notion page %s: %s", page_id, exc)
        return chunks

    def extract_members(self, source_input: dict) -> list[dict]:
        """Return unique contributors found across all pages."""
        members: dict[str, dict] = {}
        page_ids = self._collect_page_ids(source_input)
        for page_id in page_ids:
            try:
                page = self._client.pages.retrieve(page_id)
                created_by = page.get("created_by", {})
                name = self._person_name(created_by)
                uid = created_by.get("id", "")
                if uid and uid not in members:
                    members[uid] = {"id": f"notion-{uid[:8]}", "name": name, "aliases": [name.lower()]}
                last_edited_by = page.get("last_edited_by", {})
                name2 = self._person_name(last_edited_by)
                uid2 = last_edited_by.get("id", "")
                if uid2 and uid2 not in members:
                    members[uid2] = {"id": f"notion-{uid2[:8]}", "name": name2, "aliases": [name2.lower()]}
            except Exception:
                pass
        return list(members.values())

    # ── Private helpers ────────────────────────────────────────────────────────

    def _collect_page_ids(self, source_input: dict) -> list[str]:
        if "page_id" in source_input:
            return [source_input["page_id"]]
        if "database_id" in source_input:
            return self._query_database(source_input["database_id"])
        raise ValueError("source_input must have 'page_id' or 'database_id'")

    def _query_database(self, database_id: str) -> list[str]:
        ids = []
        cursor = None
        while True:
            kwargs = {"database_id": database_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self._client.databases.query(**kwargs)
            ids.extend(p["id"] for p in resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        logger.info("Notion database %s: found %d pages", database_id, len(ids))
        return ids

    def _parse_page(self, page_id: str) -> list[ParsedChunk]:
        page = self._client.pages.retrieve(page_id)
        title = self._page_title(page)
        author = self._person_name(page.get("created_by", {}))
        last_edited = page.get("last_edited_time")
        timestamp = None
        if last_edited:
            with contextlib.suppress(ValueError):
                timestamp = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))

        # Walk blocks
        full_text = self._blocks_to_text(page_id)
        if not full_text.strip():
            return []

        topics = extract_topics_from_text(full_text)
        source_url = f"https://notion.so/{page_id.replace('-', '')}"

        raw_chunks = self._chunker.split(full_text, metadata={"page_id": page_id})
        parsed: list[ParsedChunk] = []
        for rc in raw_chunks:
            chunk_text = rc["text"]
            parsed.append(
                ParsedChunk(
                    text=chunk_text,
                    source_type="notion",
                    source_ref=source_url,
                    author=author or None,
                    author_aliases=[author.lower()] if author else [],
                    timestamp=timestamp,
                    topics=topics,
                    chunk_metadata={
                        "page_id": page_id,
                        "title": title,
                        "source_url": source_url,
                        "content_hash": content_hash(chunk_text),
                        **rc.get("metadata", {}),
                    },
                )
            )
        return parsed

    def _blocks_to_text(self, block_id: str, depth: int = 0) -> str:
        if depth > 5:  # prevent infinite recursion on deeply-nested pages
            return ""
        lines: list[str] = []
        cursor = None
        while True:
            kwargs = {"block_id": block_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self._client.blocks.children.list(**kwargs)
            for block in resp.get("results", []):
                text = self._block_to_text(block)
                if text:
                    lines.append(text)
                # Recurse into child blocks
                if block.get("has_children"):
                    child_text = self._blocks_to_text(block["id"], depth + 1)
                    if child_text:
                        lines.append(child_text)
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return "\n".join(lines)

    @staticmethod
    def _block_to_text(block: dict) -> str:
        btype = block.get("type", "")
        data = block.get(btype, {})
        rich_text = data.get("rich_text", [])
        text = "".join(rt.get("plain_text", "") for rt in rich_text)
        if btype in ("heading_1", "heading_2", "heading_3"):
            prefix = "#" * int(btype[-1])
            return f"{prefix} {text}"
        if btype == "code":
            lang = data.get("language", "")
            return f"```{lang}\n{text}\n```"
        if btype == "bulleted_list_item":
            return f"• {text}"
        if btype == "numbered_list_item":
            return f"1. {text}"
        if btype == "to_do":
            checked = "x" if data.get("checked") else " "
            return f"[{checked}] {text}"
        if btype == "quote":
            return f"> {text}"
        if btype in ("paragraph", "callout"):
            return text
        # image, divider, etc. — skip silently
        return ""

    @staticmethod
    def _page_title(page: dict) -> str:
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                rt = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in rt)
        return page.get("id", "Untitled")

    @staticmethod
    def _person_name(person: dict) -> str:
        return person.get("name") or person.get("id", "unknown")[:8]
