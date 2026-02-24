import json
import re
from datetime import datetime
from pathlib import Path

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy


class DiscordConnector(BaseConnector):
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunker = ChunkingStrategy(chunk_size, chunk_overlap)
        self.time_window_seconds = 300

    def source_type(self) -> str:
        return "discord"

    def parse(self, source_input: str) -> list[ParsedChunk]:
        """Parse a Discord JSON export (DiscordChatExporter format)."""
        file_path = Path(source_input)
        if not file_path.exists():
            raise ValueError(f"File not found: {source_input}")

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # DiscordChatExporter format has a top-level object with channel and messages
        if isinstance(data, dict):
            channel_name = data.get("channel", {}).get("name", "unknown")
            messages = data.get("messages", [])
        elif isinstance(data, list):
            channel_name = "unknown"
            messages = data
        else:
            return []

        # Sort by timestamp
        messages.sort(key=lambda m: m.get("timestamp", ""))

        groups = self._group_messages(messages, channel_name)

        chunks = []
        for group in groups:
            text = (
                f"[#{channel_name}] {group['username']} "
                f"({group['timestamp'].strftime('%Y-%m-%d %H:%M')}):\n"
            )
            text += "\n".join(group["texts"])

            chunks.append(
                ParsedChunk(
                    text=text,
                    source_type="discord",
                    source_ref=f"#{channel_name}",
                    author=group["username"],
                    author_aliases=[group["username"].lower()],
                    timestamp=group["timestamp"],
                    topics=[channel_name.lower().replace("-", " ")],
                    chunk_metadata={"channel": channel_name},
                )
            )

        return chunks

    def extract_members(self, source_input: str) -> list[dict]:
        file_path = Path(source_input)
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            messages = data.get("messages", [])
        elif isinstance(data, list):
            messages = data
        else:
            return []

        members: dict[str, dict] = {}
        for msg in messages:
            author = msg.get("author", {})
            name = author.get("name") or author.get("nickname", "unknown")
            author_id = author.get("id", name)

            if author_id not in members:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                members[author_id] = {
                    "id": slug,
                    "name": name,
                    "aliases": list({name.lower(), slug} - {""}),
                    "email": None,
                }

        return list(members.values())

    def _group_messages(self, messages: list[dict], channel_name: str) -> list[dict]:
        groups = []
        current_group = None

        for msg in messages:
            content = msg.get("content", "").strip()
            if not content:
                continue

            author = msg.get("author", {})
            username = author.get("name") or author.get("nickname", "unknown")
            author_id = author.get("id", username)

            # Parse timestamp
            ts_str = msg.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, AttributeError):
                ts = datetime.now()

            if (
                current_group
                and current_group["author_id"] == author_id
                and (ts - current_group["last_ts"]).total_seconds()
                < self.time_window_seconds
            ):
                current_group["texts"].append(content)
                current_group["last_ts"] = ts
            else:
                if current_group:
                    groups.append(current_group)
                current_group = {
                    "author_id": author_id,
                    "username": username,
                    "timestamp": ts,
                    "last_ts": ts,
                    "texts": [content],
                }

        if current_group:
            groups.append(current_group)

        return groups
