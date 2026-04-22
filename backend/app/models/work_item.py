"""ORM model for the work_items table.

Unified view over GitHub PRs, issues, and (later) Slack-flagged tasks. Powers
cycle-time analysis, slow-lane detection, review-bottleneck signals.

Idempotency: unique constraint on (source, external_id, repo) — webhooks
re-deliver frequently and must not create duplicate rows.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)

from app.db.database import Base


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # "github_pr" | "github_issue" | "slack_task"
    source = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=False)  # e.g. "42" for PR number
    repo = Column(String, nullable=True, index=True)  # "owner/repo"
    title = Column(String, nullable=False, default="")
    # open | in_progress | merged | closed
    state = Column(String, nullable=False, default="open", index=True)

    author_member_id = Column(
        String,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_member_id = Column(
        String,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    labels = Column(JSON, default=list)  # ["bug", "backend", ...]
    topics = Column(JSON, default=list)  # canonicalized topics
    cycle_time_hours = Column(Float, nullable=True)  # completed_at - created_at

    __table_args__ = (
        UniqueConstraint("source", "external_id", "repo", name="uq_work_item_source_ext"),
        Index("ix_work_items_state_source", "state", "source"),
    )
