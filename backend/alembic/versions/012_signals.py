"""Phase 9d: pattern-detection signals.

Revision ID: 012_signals
Revises: 011_digest_log
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_signals"
down_revision: str | None = "011_digest_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("signal_type", sa.String(), nullable=False, index=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium", index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("suggested_action", sa.String(), nullable=True),
        sa.Column("dedup_key", sa.String(), nullable=False, index=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_by", sa.String(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_signals_open_lookup",
        "signals",
        ["organization_id", "dedup_key", "resolved_at"],
    )
    op.create_index(
        "ix_signals_type_severity",
        "signals",
        ["signal_type", "severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_type_severity", table_name="signals")
    op.drop_index("ix_signals_open_lookup", table_name="signals")
    op.drop_table("signals")
