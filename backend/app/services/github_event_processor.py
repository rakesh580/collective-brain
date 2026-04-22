"""Process GitHub webhook events into the Collective Brain knowledge graph."""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ingestion.base import ParsedChunk
from app.ingestion.topic_extractor import (
    canonicalize_list,
    extract_topics_from_commit,
    extract_topics_from_labels,
)
from app.models.artifact import ArtifactRecord
from app.models.contribution import ContributionRecord
from app.models.member import MemberRecord
from app.models.work_item import WorkItem
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


# Topic extraction lives in app.ingestion.topic_extractor; call sites below
# use extract_topics_from_commit / extract_topics_from_labels directly.


def _upsert_work_item(
    db: Session,
    *,
    source: str,
    external_id: str,
    repo: str,
    title: str,
    state: str,
    author_member_id: str | None,
    created_at: datetime | None,
    completed_at: datetime | None,
    labels: list[str],
    topics: list[str],
) -> WorkItem:
    """Idempotently upsert a work item. Computes cycle_time_hours on close.

    Webhooks re-deliver: we look up by (source, external_id, repo) and patch
    existing rows rather than creating duplicates. Terminal states (merged,
    closed) set completed_at once and compute cycle time from created_at.
    """
    existing = (
        db.query(WorkItem)
        .filter(
            WorkItem.source == source,
            WorkItem.external_id == external_id,
            WorkItem.repo == repo,
        )
        .first()
    )

    if existing is None:
        wi = WorkItem(
            id=str(uuid4()),
            source=source,
            external_id=external_id,
            repo=repo,
            title=title,
            state=state,
            author_member_id=author_member_id,
            created_at=created_at or datetime.now(UTC),
            labels=labels,
            topics=topics,
        )
        if state in ("merged", "closed"):
            wi.completed_at = completed_at or datetime.now(UTC)
            wi.cycle_time_hours = _hours_between(wi.created_at, wi.completed_at)
        db.add(wi)
        return wi

    # Update existing row. Only move to a terminal state once.
    existing.title = title or existing.title
    existing.labels = labels or existing.labels
    existing.topics = topics or existing.topics
    if author_member_id and not existing.author_member_id:
        existing.author_member_id = author_member_id

    if state in ("merged", "closed") and existing.state not in ("merged", "closed"):
        existing.state = state
        existing.completed_at = completed_at or datetime.now(UTC)
        existing.cycle_time_hours = _hours_between(existing.created_at, existing.completed_at)
    elif state == "open" and existing.state in ("merged", "closed"):
        # Reopen: clear terminal state, keep history by not deleting cycle_time.
        existing.state = "open"
        existing.completed_at = None
    elif existing.state not in ("merged", "closed"):
        existing.state = state

    return existing


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    delta = end - start
    return round(delta.total_seconds() / 3600.0, 2)


def _pr_state(action: str, merged: bool, raw_state: str) -> str:
    """Map a GitHub PR webhook action to a WorkItem state."""
    if action == "closed":
        return "merged" if merged else "closed"
    if action in ("opened", "reopened", "synchronize"):
        return "open"
    return raw_state or "open"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _mark_work_item_reviewed(
    db: Session,
    *,
    repo: str,
    pr_external_id: str,
    review_submitted_at: datetime | None,
) -> WorkItem | None:
    """Move an open PR WorkItem to ``in_progress`` on its first review.

    Idempotent: if the WorkItem is already in a terminal (merged/closed) or
    ``in_progress`` state, only ``started_at`` gets back-filled to the earlier
    of the current value and the review timestamp. Never un-merges.
    """
    wi = (
        db.query(WorkItem)
        .filter(
            WorkItem.source == "github_pr",
            WorkItem.external_id == pr_external_id,
            WorkItem.repo == repo,
        )
        .first()
    )
    if wi is None:
        return None

    submitted = review_submitted_at or datetime.now(UTC)
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=UTC)

    # Earliest review wins for started_at.
    if wi.started_at is None:
        wi.started_at = submitted
    else:
        existing = wi.started_at if wi.started_at.tzinfo else wi.started_at.replace(tzinfo=UTC)
        if submitted < existing:
            wi.started_at = submitted

    if wi.state == "open":
        wi.state = "in_progress"

    return wi


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

            topics = extract_topics_from_commit(message, all_files)

            # Build chunk text
            file_summary = ""
            if all_files:
                file_summary = f"\nFiles: {', '.join(all_files[:10])}"
                if len(all_files) > 10:
                    file_summary += f" (+{len(all_files) - 10} more)"

            text = f"[{repo_name}:{branch}] {message}{file_summary}"

            chunks.append(
                ParsedChunk(
                    text=text,
                    source_type="github_push",
                    source_ref=sha,
                    author=author_name,
                    author_aliases=[author_email] if author_email else [],
                    timestamp=ts,
                    topics=topics,
                    chunk_metadata={"commit_hash": sha, "repo": repo_name, "branch": branch},
                )
            )

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

        # Extract topics from title and labels — canonicalized through the allowlist
        label_names = [label.get("name", "") for label in pr.get("labels", [])]
        topics = canonicalize_list(
            extract_topics_from_labels(label_names) + extract_topics_from_commit(pr_title, []),
        )

        status_text = "merged" if merged else state
        text = f"[PR #{pr_number}] {pr_title} ({status_text})\nAuthor: {author}\nRepository: {repo_name}\n"
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
        author_member_id: str | None = None
        if author:
            member = _resolve_github_member(self.db, author)
            if member:
                author_member_id = member.id
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

        # Upsert WorkItem for cycle-time analysis.
        pr_state = _pr_state(action, merged, state)
        created_at = _parse_ts(pr.get("created_at"))
        completed_at = _parse_ts(pr.get("closed_at")) if pr_state in ("merged", "closed") else None
        _upsert_work_item(
            self.db,
            source="github_pr",
            external_id=str(pr_number),
            repo=repo_name,
            title=pr_title,
            state=pr_state,
            author_member_id=author_member_id,
            created_at=created_at,
            completed_at=completed_at,
            labels=label_names,
            topics=topics,
        )

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

        label_names = [label.get("name", "") for label in issue.get("labels", []) if label.get("name")]
        topics = canonicalize_list(
            extract_topics_from_labels(label_names) + extract_topics_from_commit(title, []),
        )

        text = f"[Issue #{issue_number}] {title} ({action})\nAuthor: {author}\n\n{body[:500]}"

        chunk = ParsedChunk(
            text=text,
            source_type="github_issue",
            source_ref=f"issue-{issue_number}",
            author=author,
            timestamp=ts,
            topics=topics,
        )

        member_ids: set[str] = set()
        author_member_id: str | None = None
        if author:
            member = _resolve_github_member(self.db, author)
            if member:
                author_member_id = member.id
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

        issue_state = "closed" if action == "closed" else "open"
        created_at = _parse_ts(issue.get("created_at"))
        completed_at = _parse_ts(issue.get("closed_at")) if issue_state == "closed" else None
        _upsert_work_item(
            self.db,
            source="github_issue",
            external_id=str(issue_number),
            repo=repo_name,
            title=title,
            state=issue_state,
            author_member_id=author_member_id,
            created_at=created_at,
            completed_at=completed_at,
            labels=label_names,
            topics=topics,
        )

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

        # Mark the PR's WorkItem as "in_progress" on the first review submitted.
        # Later reviews don't reset started_at — it's the earliest review timestamp.
        _mark_work_item_reviewed(
            self.db,
            repo=repo_name,
            pr_external_id=str(pr_number),
            review_submitted_at=ts,
        )

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
