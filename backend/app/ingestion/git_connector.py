import re
from datetime import datetime, timedelta

from git import Repo

from app.ingestion.base import BaseConnector, ParsedChunk
from app.ingestion.topic_extractor import extract_topics_from_commit


class GitConnector(BaseConnector):
    def __init__(
        self,
        branch: str = "main",
        since_days: int = 90,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.branch = branch
        self.since_days = since_days

    def source_type(self) -> str:
        return "git"

    def parse(self, source_input: str) -> list[ParsedChunk]:
        repo = Repo(source_input)
        since_date = datetime.now() - timedelta(days=self.since_days)
        chunks = []

        for commit in repo.iter_commits(self.branch, since=since_date):
            # Build diff summary — stats can fail on shallow clones or root commits
            try:
                stats = commit.stats.files
            except Exception:
                stats = {}

            files_changed = []
            for fpath, stat in stats.items():
                files_changed.append(f"  - {fpath} (+{stat['insertions']}, -{stat['deletions']})")
            files_str = "\n".join(files_changed[:20])  # Cap at 20 files
            if len(files_changed) > 20:
                files_str += f"\n  ... and {len(files_changed) - 20} more files"

            text = (
                f"[Commit {commit.hexsha[:7]}] by {commit.author.name} "
                f"<{commit.author.email}> on {commit.committed_datetime.strftime('%Y-%m-%d')}\n"
                f"Message: {commit.message.strip()}\n\n"
                f"Files changed:\n{files_str}"
            )

            # Extract topics from file paths and commit message
            topics = extract_topics_from_commit(commit.message, list(stats.keys()))

            chunks.append(
                ParsedChunk(
                    text=text,
                    source_type="git",
                    source_ref=commit.hexsha[:7],
                    author=commit.author.name,
                    author_aliases=[
                        commit.author.name.lower(),
                        commit.author.email.split("@")[0] if commit.author.email else "",
                    ],
                    timestamp=commit.committed_datetime.replace(tzinfo=None),
                    topics=topics,
                    chunk_metadata={
                        "commit_hash": commit.hexsha,
                        "email": commit.author.email or "",
                        "files_changed": len(stats),
                    },
                )
            )

        return chunks

    def extract_members(self, source_input: str) -> list[dict]:
        repo = Repo(source_input)
        since_date = datetime.now() - timedelta(days=self.since_days)
        members: dict[str, dict] = {}

        for commit in repo.iter_commits(self.branch, since=since_date):
            email = commit.author.email or ""
            name = commit.author.name or ""
            key = email or name.lower()

            if key not in members:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                members[key] = {
                    "id": slug,
                    "name": name,
                    "aliases": list(
                        {
                            name.lower(),
                            email.split("@")[0] if email else "",
                            slug,
                        }
                        - {""}
                    ),
                    "email": email,
                }

        return list(members.values())
