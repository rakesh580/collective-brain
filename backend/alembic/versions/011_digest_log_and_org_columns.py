"""Phase 9c: digest_log audit table + org-level digest configuration columns.

Revision ID: 011_digest_log
Revises: 010_contribution_rollups
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_digest_log"
down_revision: str | None = "010_contribution_rollups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Org-level digest configuration.
    op.add_column(
        "organizations",
        sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "organizations",
        sa.Column("digest_timezone", sa.String(), nullable=False, server_default="UTC"),
    )

    # Audit trail: one row per attempted digest delivery, successful or not.
    op.create_table(
        "digest_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=True, index=True),
        sa.Column("channel_id", sa.String(), nullable=True),
        sa.Column("delivery_channel", sa.String(), nullable=False),  # "slack" | "email" | "in_app"
        sa.Column("recipient", sa.String(), nullable=True),  # email or channel
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),  # "sent" | "failed" | "skipped"
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_digest_log_sent_at", "digest_log", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_digest_log_sent_at", table_name="digest_log")
    op.drop_table("digest_log")
    op.drop_column("organizations", "digest_timezone")
    op.drop_column("organizations", "digest_enabled")
