"""Process GitHub webhook events into the Collective Brain knowledge graph."""
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ingestion.base import ParsedChunk
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.services.memory_graph import invalidate_graph_cache

logger = logging.getLogger("collective_brain.github")


def _resolve_github_member(db: Session, username: str, email: str | None = None) -> MemberRecord | None:
    """Find or create a MemberRecord for a GitHub user."""
    import re

    if not username:
        return None

    # Try matching by name (case-insensitive)
    member = db.query(MemberRecord).filter(MemberRecord.name.ilike(username)).first()
    if member:
        return member

    # Try partial name match
    member = db.query(MemberRecord).filter(MemberRecord.name.ilike(f"%{username}%")).first()
    if member:
        return member

    # Try email match if available
    if email:
        member = db.query(MemberRecord).filter(MemberRecord.email == email).first()
        if member:
            return member

    # Create new member
    member_id = re.sub(r"[^a-z0-9]+", "-", username.lower()).strip("-")
    existing = db.query(MemberRecord).filter(MemberRecord.id == member_id).first()
    if existing:
        return existing

    member = MemberRecord(
        id=member_id,
        name=username,
        aliases=[username.lower()],
        email=email,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def _extract_topics_from_commit(message: str, files: list[str]) -> list[str]:
    """Extract topics from commit message and file paths."""
    topics: set[str] = set()

    # Conventional commit prefixes
    prefix_map = {
        "feat": "feature", "fix": "bugfix", "refactor": "refactoring",
        "docs": "documentation", "test": "testing", "chore": "maintenance",
        "ci": "ci-cd", "perf": "performance", "style": "code-style",
        "build": "build-system",
    }
    msg_lower = message.lower().strip()
    for prefix, topic in prefix_map.items():
        if msg_lower.startswith(f"{prefix}:") or msg_lower.startswith(f"{prefix}("):
            topics.add(topic)
            # Extract scope: feat(auth): ...
            if "(" in msg_lower and ")" in msg_lower:
                scope = msg_lower.split("(")[1].split(")")[0].strip()
                if scope and len(scope) < 30:
                    topics.add(scope)

    # Topics from file extensions and directories
    ext_topics = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "react",
        ".jsx": "react", ".go": "golang", ".rs": "rust", ".java": "java",
        ".rb": "ruby", ".yml": "devops", ".yaml": "devops", ".tf": "terraform",
        ".sql": "database", ".css": "frontend", ".html": "frontend",
        ".dockerfile": "docker", ".sh": "scripting",
    }
    dir_topics = {
        "api": "api", "auth": "authentication", "test": "testing",
        "deploy": "deployment", "infra": "infrastructure", "docs": "documentation",
        "frontend": "frontend", "backend": "backend", "models": "data-models",
        "migrations": "database",
    }

    for f in files[:20]:  # Limit to avoid huge PRs
        parts = f.lower().split("/")
        for part in parts:
            if part in dir_topics:
                topics.add(dir_topics[part])
        ext = "." + f.rsplit(".", 1)[-1].lower() if "." in f else ""
        if ext in ext_topics:
            topics.add(ext_topics[ext])

    return list(topics)[:10]


class GitHubEventProcessor:
    """Process GitHub webhook events and ingest into the knowledge base."""

    def __init__(self, db: Session, embedder, vector_store, room_id: str | None = None):
        self.db = db
        self.embedder = embedder
        self.vs = vector_store
        self.room_id = room_id

    def _store_chunks(self, chunks: list[ParsedChunk], artifact_id: str, source_path: str):
        """Embed and store chunks, create contributions."""
        if not chunks:
            return

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_batch(texts)

        ids = [f"chunk-{uuid4()}" for _ in chunks]
        metadatas = []
        for c in chunks:
            meta = {
                "source_type": c.source_type,
                "source_ref": c.source_ref,
                "artifact_id": artifact_id,
                "author": c.author or "unknown",
                "timestamp": c.timestamp.isoformat() if c.timestamp else "",
                "topics": ",".join(c.topics),
                "room_id": self.room_id or "",
            }
            metadatas.append(meta)

        self.vs.add_documents(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

        # Create contribution records
        for c in chunks:
            if not c.author:
                continue
            member = _resolve_github_member(self.db, c.author)
            if not member:
                continue

            contrib = ContributionRecord(
                id=str(uuid4()),
                member_id=member.id,
                artifact_id=artifact_id,
                contribution_type=f"{c.source_type}_content",
                timestamp=c.timestamp,
                description=c.text[:200],
                topics=c.topics,
                room_id=self.room_id,
            )
            self.db.add(contrib)

            # Update member stats
            member.total_contributions = (member.total_contributions or 0) + 1
            if c.timestamp and (not member.last_active or c.timestamp > member.last_active):
                member.last_active = c.timestamp
            existing_tags = set(member.expertise_tags or [])
            existing_tags.update(c.topics)
            member.expertise_tags = list(existing_tags)

    def process_push(self, payload: dict) -> dict:
        """Process a push event — extract commits and ingest."""
        repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        commits = payload.get("commits", [])
        ref = payload.get("ref", "refs/heads/main")
        branch = ref.split("/")[-1]

        if not commits:
            return {"status": "skipped", "reason": "no commits"}

        chunks: list[ParsedChunk] = []
        member_ids: set[str] = set()

        for commit in commits:
            author_name = commit.get("author", {}).get("username") or commit.get("author", {}).get("name", "")
            author_email = commit.get("author", {}).get("email")
            message = commit.get("message", "")
            sha = commit.get("id", "")[:7]
            timestamp_str = commit.get("timestamp", "")

            # Parse timestamp
            ts = None
            if timestamp_str:
                try:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    ts = datetime.now(UTC)

            # Files changed
            files_added = commit.get("added", [])
            files_modified = commit.get("modified", [])
            files_removed = commit.get("removed", [])
            all_files = files_added + files_modified + files_removed

            topics = _extract_topics_from_commit(message, all_files)

            # Build chunk text
            file_summary = ""
            if all_files:
                file_summary = f"\nFiles: {', '.join(all_files[:10])}"
                if len(all_files) > 10:
                    file_summary += f" (+{len(all_files) - 10} more)"

            text = f"[{repo_name}:{branch}] {message}{file_summary}"

            chunks.append(ParsedChunk(
                text=text,
                source_type="github_push",
                source_ref=sha,
                author=author_name,
                author_aliases=[author_email] if author_email else [],
                timestamp=ts,
                topics=topics,
                chunk_metadata={"commit_hash": sha, "repo": repo_name, "branch": branch},
            ))

            if author_name:
                member = _resolve_github_member(self.db, author_name, author_email)
                if member:
                    member_ids.add(member.id)

        # Create artifact
        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type="github_push",
            source_path=f"github:{repo_name}",
            title=f"Push to {repo_name}/{branch} ({len(commits)} commits)",
            chunk_count=len(chunks),
            member_ids=list(member_ids),
            status="completed",
            room_id=self.room_id,
        )
        self.db.add(artifact)

        self._store_chunks(chunks, artifact_id, f"github:{repo_name}")
        self.db.commit()
        invalidate_graph_cache(room_id=self.room_id)

        logger.info("Processed push: %s/%s — %d commits", repo_name, branch, len(commits))
        return {"status": "processed", "commits": len(commits), "artifact_id": artifact_id}

    def process_pull_request(self, payload: dict) -> dict:
        """Process a pull_request event."""
        action = payload.get("action", "")
        if action not in ("opened", "closed", "synchronize", "reopened"):
            return {"status": "skipped", "reason": f"PR action '{action}' not tracked"}

        pr = payload.get("pull_request", {})
        repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        pr_number = pr.get("number", 0)
        pr_title = pr.get("title", "")
        pr_body = pr.get("body", "") or ""
        author = pr.get("user", {}).get("login", "")
        merged = pr.get("merged", False)
        state = pr.get("state", "")

        # Extract reviewers
        reviewers = []
        requested = pr.get("requested_reviewers", [])
        for r in requested:
            login = r.get("login", "")
            if login:
                reviewers.append(login)

        ts = None
        ts_str = pr.get("updated_at") or pr.get("created_at", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = datetime.now(UTC)

        # Extract topics from title and labels
        topics: list[str] = []
        for label in pr.get("labels", []):
            label_name = label.get("name", "").lower()
            if label_name and len(label_name) < 30:
                topics.append(label_name)
        topics.extend(_extract_topics_from_commit(pr_title, []))

        status_text = "merged" if merged else state
        text = (
            f"[PR #{pr_number}] {pr_title} ({status_text})\n"
            f"Author: {author}\n"
            f"Repository: {repo_name}\n"
        )
        if reviewers:
            text += f"Reviewers: {', '.join(reviewers)}\n"
        if pr_body:
            text += f"\n{pr_body[:500]}"

        chunk = ParsedChunk(
            text=text,
            source_type="github_pr",
            source_ref=f"PR-{pr_number}",
            author=author,
            timestamp=ts,
            topics=topics,
            chunk_metadata={"pr_number": pr_number, "repo": repo_name, "action": action},
        )

        # Resolve members
        member_ids: set[str] = set()
        if author:
            member = _resolve_github_member(self.db, author)
            if member:
                member_ids.add(member.id)
        for reviewer in reviewers:
            member = _resolve_github_member(self.db, reviewer)
            if member:
                member_ids.add(member.id)

        # Create artifact
        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type="github_pr",
            source_path=f"github:{repo_name}/pull/{pr_number}",
            title=f"PR #{pr_number}: {pr_title[:80]}",
            chunk_count=1,
            member_ids=list(member_ids),
            status="completed",
            room_id=self.room_id,
        )
        self.db.add(artifact)

        self._store_chunks([chunk], artifact_id, f"github:{repo_name}")
        self.db.commit()
        invalidate_graph_cache(room_id=self.room_id)

        logger.info("Processed PR #%d (%s): %s", pr_number, action, pr_title)
        return {"status": "processed", "pr_number": pr_number, "action": action, "artifact_id": artifact_id}

    def process_issue(self, payload: dict) -> dict:
        """Process an issue event."""
        action = payload.get("action", "")
        if action not in ("opened", "closed", "reopened", "labeled"):
            return {"status": "skipped", "reason": f"Issue action '{action}' not tracked"}

        issue = payload.get("issue", {})
        repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        issue_number = issue.get("number", 0)
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        author = issue.get("user", {}).get("login", "")

        ts = None
        ts_str = issue.get("updated_at") or issue.get("created_at", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = datetime.now(UTC)

        topics = [label.get("name", "").lower() for label in issue.get("labels", []) if label.get("name")]

        text = f"[Issue #{issue_number}] {title} ({action})\nAuthor: {author}\n\n{body[:500]}"

        chunk = ParsedChunk(
            text=text,
            source_type="github_issue",
            source_ref=f"issue-{issue_number}",
            author=author,
            timestamp=ts,
            topics=topics[:10],
        )

        member_ids: set[str] = set()
        if author:
            member = _resolve_github_member(self.db, author)
            if member:
                member_ids.add(member.id)

        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type="github_issue",
            source_path=f"github:{repo_name}/issues/{issue_number}",
            title=f"Issue #{issue_number}: {title[:80]}",
            chunk_count=1,
            member_ids=list(member_ids),
            status="completed",
            room_id=self.room_id,
        )
        self.db.add(artifact)

        self._store_chunks([chunk], artifact_id, f"github:{repo_name}")
        self.db.commit()
        invalidate_graph_cache(room_id=self.room_id)

        logger.info("Processed issue #%d (%s): %s", issue_number, action, title)
        return {"status": "processed", "issue_number": issue_number, "artifact_id": artifact_id}

    def process_review(self, payload: dict) -> dict:
        """Process a pull_request_review event — track who reviews whose code."""
        action = payload.get("action", "")
        if action != "submitted":
            return {"status": "skipped", "reason": f"Review action '{action}' not tracked"}

        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        reviewer = review.get("user", {}).get("login", "")
        pr_author = pr.get("user", {}).get("login", "")
        pr_number = pr.get("number", 0)
        review_state = review.get("state", "")  # approved, changes_requested, commented
        review_body = review.get("body", "") or ""

        ts = None
        ts_str = review.get("submitted_at", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = datetime.now(UTC)

        text = (
            f"[Code Review] {reviewer} reviewed PR #{pr_number} by {pr_author} — {review_state}\n"
            f"Repository: {repo_name}\n"
        )
        if review_body:
            text += f"\n{review_body[:300]}"

        chunk = ParsedChunk(
            text=text,
            source_type="github_review",
            source_ref=f"review-{pr_number}-{reviewer}",
            author=reviewer,
            timestamp=ts,
            topics=["code-review"],
        )

        member_ids: set[str] = set()
        if reviewer:
            member = _resolve_github_member(self.db, reviewer)
            if member:
                member_ids.add(member.id)
        if pr_author:
            member = _resolve_github_member(self.db, pr_author)
            if member:
                member_ids.add(member.id)

        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type="github_review",
            source_path=f"github:{repo_name}/pull/{pr_number}/review",
            title=f"Review on PR #{pr_number} by {reviewer}",
            chunk_count=1,
            member_ids=list(member_ids),
            status="completed",
            room_id=self.room_id,
        )
        self.db.add(artifact)

        self._store_chunks([chunk], artifact_id, f"github:{repo_name}")
        self.db.commit()
        invalidate_graph_cache(room_id=self.room_id)

        logger.info("Processed review on PR #%d by %s (%s)", pr_number, reviewer, review_state)
        return {"status": "processed", "reviewer": reviewer, "pr_number": pr_number, "artifact_id": artifact_id}

    def process_issue_comment(self, payload: dict) -> dict:
        """Process issue_comment events (comments on issues and PRs)."""
        action = payload.get("action", "")
        if action != "created":
            return {"status": "skipped", "reason": f"Comment action '{action}' not tracked"}

        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        author = comment.get("user", {}).get("login", "")
        body = comment.get("body", "") or ""
        issue_number = issue.get("number", 0)
        is_pr = "pull_request" in issue

        ts = None
        ts_str = comment.get("created_at", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = datetime.now(UTC)

        entity_type = "PR" if is_pr else "Issue"
        text = f"[Comment on {entity_type} #{issue_number}] by {author}\n\n{body[:500]}"

        chunk = ParsedChunk(
            text=text,
            source_type="github_comment",
            source_ref=f"comment-{issue_number}-{comment.get('id', '')}",
            author=author,
            timestamp=ts,
            topics=[],
        )

        member_ids: set[str] = set()
        if author:
            member = _resolve_github_member(self.db, author)
            if member:
                member_ids.add(member.id)

        artifact_id = str(uuid4())
        artifact = ArtifactRecord(
            id=artifact_id,
            source_type="github_comment",
            source_path=f"github:{repo_name}/issues/{issue_number}/comment",
            title=f"Comment on {entity_type} #{issue_number} by {author}",
            chunk_count=1,
            member_ids=list(member_ids),
            status="completed",
            room_id=self.room_id,
        )
        self.db.add(artifact)

        self._store_chunks([chunk], artifact_id, f"github:{repo_name}")
        self.db.commit()
        invalidate_graph_cache(room_id=self.room_id)

        return {"status": "processed", "issue_number": issue_number, "artifact_id": artifact_id}
