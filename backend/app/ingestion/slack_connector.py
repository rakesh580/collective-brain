import json
import re
from datetime import datetime
from pathlib import Path

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.chunker import ChunkingStrategy


class SlackConnector(BaseConnector):
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunker = ChunkingStrategy(chunk_size, chunk_overlap)
        self.time_window_seconds = 300  # 5 minute grouping

    def source_type(self) -> str:
        return "slack"

    def parse(self, source_input: str) -> list[ParsedChunk]:
        """Parse a Slack export directory."""
        export_dir = Path(source_input)
        if not export_dir.is_dir():
            raise ValueError(f"Not a valid directory: {source_input}")

        # Load user mapping
        users = self._load_users(export_dir)

        # Find channel directories
        chunks = []
        for item in sorted(export_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                channel_chunks = self._parse_channel(item, item.name, users)
                chunks.extend(channel_chunks)

        return chunks

    def extract_members(self, source_input: str) -> list[dict]:
        export_dir = Path(source_input)
        users = self._load_users(export_dir)
        members = []
        for uid, info in users.items():
            name = info.get("real_name") or info.get("display_name") or info.get("name", uid)
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            members.append(
                {
                    "id": slug,
                    "name": name,
                    "aliases": list(
                        {
                            name.lower(),
                            info.get("display_name", "").lower(),
                            info.get("name", "").lower(),
                            slug,
                        }
                        - {""}
                    ),
                    "email": info.get("profile", {}).get("email"),
                }
            )
        return members

    def _load_users(self, export_dir: Path) -> dict:
        users_file = export_dir / "users.json"
        if not users_file.exists():
            return {}
        with open(users_file, encoding="utf-8") as f:
            users_list = json.load(f)
        return {u["id"]: u for u in users_list}

    def _parse_channel(self, channel_dir: Path, channel_name: str, users: dict) -> list[ParsedChunk]:
        messages = []
        for json_file in sorted(channel_dir.glob("*.json")):
            with open(json_file, encoding="utf-8") as f:
                day_messages = json.load(f)
            messages.extend(day_messages)

        # Sort by timestamp
        messages.sort(key=lambda m: float(m.get("ts", 0)))

        # Group consecutive messages by same user within time window
        groups = self._group_messages(messages, users)

        chunks = []
        for group in groups:
            username = group["username"]
            timestamp = group["timestamp"]
            text = f"[#{channel_name}] {username} ({timestamp.strftime('%Y-%m-%d %H:%M')}):\n"
            text += "\n".join(group["texts"])

            chunks.append(
                ParsedChunk(
                    text=text,
                    source_type="slack",
                    source_ref=f"#{channel_name}",
                    author=username,
                    author_aliases=[username.lower()],
                    timestamp=timestamp,
                    topics=self._extract_topics(channel_name, group["texts"]),
                    chunk_metadata={"channel": channel_name},
                )
            )

        return chunks

    def _group_messages(self, messages: list[dict], users: dict) -> list[dict]:
        groups = []
        current_group = None

        for msg in messages:
            # Skip bot messages and system messages
            if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                continue
            if not msg.get("text"):
                continue

            user_id = msg.get("user", "unknown")
            user_info = users.get(user_id, {})
            username = user_info.get("real_name") or user_info.get("display_name") or user_info.get("name", user_id)
            ts = datetime.fromtimestamp(float(msg.get("ts", 0)))
            text = self._clean_message_text(msg["text"], users)

            if (
                current_group
                and current_group["user_id"] == user_id
                and (ts - current_group["last_ts"]).total_seconds() < self.time_window_seconds
            ):
                current_group["texts"].append(text)
                current_group["last_ts"] = ts
            else:
                if current_group:
                    groups.append(current_group)
                current_group = {
                    "user_id": user_id,
                    "username": username,
                    "timestamp": ts,
                    "last_ts": ts,
                    "texts": [text],
                }

        if current_group:
            groups.append(current_group)

        return groups

    def _clean_message_text(self, text: str, users: dict) -> str:
        # Replace <@U123> mentions with display names
        def replace_mention(match):
            uid = match.group(1)
            user = users.get(uid, {})
            name = user.get("real_name") or user.get("name", uid)
            return f"@{name}"

        text = re.sub(r"<@(\w+)>", replace_mention, text)
        # Clean up other Slack formatting
        text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        return text

    def _extract_topics(self, channel_name: str, texts: list[str]) -> list[str]:
        topics = [channel_name.lower().replace("-", " ")]
        return topics[:5]
