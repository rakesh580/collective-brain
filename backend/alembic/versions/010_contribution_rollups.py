"""Phase 9b: Contribution Rollups — per-member 7d/30d activity snapshots.

Revision ID: 010_contribution_rollups
Revises: 009_work_items
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_contribution_rollups"
down_revision: str | None = "009_work_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contribution_rollups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "member_id",
            sa.String(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contributions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifacts_touched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distinct_topics", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topic_histogram", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("top_topic", sa.String(), nullable=True),
        sa.Column("type_histogram", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_rollup_member_window_at",
        "contribution_rollups",
        ["member_id", "window_days", "computed_at"],
    )
    op.create_index(
        "ix_rollups_member_window",
        "contribution_rollups",
        ["member_id", "window_days"],
    )
    op.create_index(
        "ix_contribution_rollups_computed_at",
        "contribution_rollups",
        ["computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_contribution_rollups_computed_at", table_name="contribution_rollups")
    op.drop_index("ix_rollups_member_window", table_name="contribution_rollups")
    op.drop_constraint("uq_rollup_member_window_at", "contribution_rollups", type_="unique")
    op.drop_table("contribution_rollups")
