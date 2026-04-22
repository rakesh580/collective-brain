"""Phase 9: Work Items — unified PR/issue/task model for cycle-time analysis.

Revision ID: 009_work_items
Revises: 008_outcomes_notifs
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_work_items"
down_revision: str | None = "008_outcomes_notifs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("source", sa.String(), nullable=False, index=True),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("repo", sa.String(), nullable=True, index=True),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("state", sa.String(), nullable=False, server_default="open", index=True),
        sa.Column(
            "author_member_id",
            sa.String(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "assignee_member_id",
            sa.String(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("labels", sa.JSON(), server_default="[]"),
        sa.Column("topics", sa.JSON(), server_default="[]"),
        sa.Column("cycle_time_hours", sa.Float(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_work_item_source_ext",
        "work_items",
        ["source", "external_id", "repo"],
    )
    op.create_index("ix_work_items_state_source", "work_items", ["state", "source"])


def downgrade() -> None:
    op.drop_index("ix_work_items_state_source", table_name="work_items")
    op.drop_constraint("uq_work_item_source_ext", "work_items", type_="unique")
    op.drop_table("work_items")
