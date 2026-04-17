"""Phase 7b: Decision Outcomes & Notifications — outcome tracking, webhook notifications.

Revision ID: 008_outcomes_notifs
Revises: 007_decision_intelligence
Create Date: 2026-04-16
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "008_outcomes_notifs"
down_revision: str | None = "007_decision_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Decision Outcomes ───────────────────────────────────────────────────
    op.create_table(
        "decision_outcomes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "decision_id",
            sa.String(),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("outcome_description", sa.String(), nullable=False),
        sa.Column("outcome_status", sa.String(), server_default="unknown"),
        sa.Column("lessons_learned", sa.JSON(), server_default="[]"),
        sa.Column("recorded_by", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── Notification Webhooks ───────────────────────────────────────────────
    op.create_table(
        "notification_webhooks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("event_types", sa.JSON(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Notification Logs ───────────────────────────────────────────────────
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "webhook_id",
            sa.String(),
            sa.ForeignKey("notification_webhooks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload_summary", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default="false"),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_table("notification_webhooks")
    op.drop_table("decision_outcomes")
