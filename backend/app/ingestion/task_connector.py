import csv
import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path

from app.ingestion.base import BaseConnector, ParsedChunk


class TaskConnector(BaseConnector):
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        pass

    def source_type(self) -> str:
        return "tasks"

    def parse(self, source_input: str) -> list[ParsedChunk]:
        """Parse a JSON or CSV task list file."""
        file_path = Path(source_input)
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        tasks = self._parse_csv(content) if file_path.suffix == ".csv" else self._parse_json(content)

        chunks = []
        for task in tasks:
            text = self._format_task(task)
            assignee = task.get("assignee")
            tags = task.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            # Parse dates
            timestamp = None
            for date_field in ("completed_date", "due_date", "created_date"):
                if task.get(date_field):
                    try:
                        timestamp = datetime.fromisoformat(task[date_field])
                        break
                    except (ValueError, TypeError):
                        pass

            chunks.append(
                ParsedChunk(
                    text=text,
                    source_type="tasks",
                    source_ref=task.get("title", "untitled task"),
                    author=assignee,
                    author_aliases=[assignee.lower()] if assignee else [],
                    timestamp=timestamp,
                    topics=tags,
                    chunk_metadata={
                        "status": task.get("status", "unknown"),
                        "assignee": assignee or "unassigned",
                    },
                )
            )

        return chunks

    def extract_members(self, source_input: str) -> list[dict]:
        file_path = Path(source_input)
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        tasks = self._parse_csv(content) if file_path.suffix == ".csv" else self._parse_json(content)

        members: dict[str, dict] = {}
        for task in tasks:
            assignee = task.get("assignee")
            if assignee and assignee not in members:
                slug = re.sub(r"[^a-z0-9]+", "-", assignee.lower()).strip("-")
                members[assignee] = {
                    "id": slug,
                    "name": assignee,
                    "aliases": [assignee.lower(), slug],
                    "email": None,
                }

        return list(members.values())

    def _parse_json(self, content: str) -> list[dict]:
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tasks" in data:
                return data["tasks"]
            return [data]
        except json.JSONDecodeError:
            return []

    def _parse_csv(self, content: str) -> list[dict]:
        reader = csv.DictReader(StringIO(content))
        tasks = []
        for row in reader:
            task = dict(row)
            # Parse tags from comma-separated string
            if "tags" in task and isinstance(task["tags"], str):
                task["tags"] = [t.strip() for t in task["tags"].split(",") if t.strip()]
            tasks.append(task)
        return tasks

    def _format_task(self, task: dict) -> str:
        title = task.get("title", "Untitled")
        assignee = task.get("assignee", "unassigned")
        status = task.get("status", "unknown")
        tags = task.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        notes = task.get("notes", "")
        due_date = task.get("due_date", "")

        text = f'[Task] "{title}" assigned to {assignee} | Status: {status}'
        if tags_str:
            text += f" | Tags: {tags_str}"
        if due_date:
            text += f" | Due: {due_date}"
        if notes:
            text += f"\nNotes: {notes}"
        return text
