"""Phase 7: Decision Intelligence — decisions, decision links, risk alerts, continuity scores.

Revision ID: 007_decision_intelligence
Revises: 006_offboarding_public_kb
Create Date: 2026-04-16
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "007_decision_intelligence"
down_revision: str | None = "006_offboarding_public_kb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Decisions ────────────────────────────────────────────────────────────
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("decision_type", sa.String(), server_default="technical"),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("confidence_score", sa.Float(), server_default="0.0"),
        sa.Column("context_summary", sa.String(), nullable=True),
        sa.Column("alternatives_considered", sa.JSON(), server_default="[]"),
        sa.Column("outcome_summary", sa.String(), nullable=True),
        sa.Column("source_artifact_ids", sa.JSON(), server_default="[]"),
        sa.Column("source_chunk_ids", sa.JSON(), server_default="[]"),
        sa.Column("involved_member_ids", sa.JSON(), server_default="[]"),
        sa.Column("tags", sa.JSON(), server_default="[]"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── Decision Links ───────────────────────────────────────────────────────
    op.create_table(
        "decision_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "from_decision_id",
            sa.String(),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "to_decision_id",
            sa.String(),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("link_type", sa.String(), server_default="related"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── Risk Alerts ──────────────────────────────────────────────────────────
    op.create_table(
        "risk_alerts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), server_default="medium"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("affected_entity_type", sa.String(), nullable=True),
        sa.Column("affected_entity_id", sa.String(), nullable=True),
        sa.Column("metrics", sa.JSON(), server_default="{}"),
        sa.Column("is_acknowledged", sa.Boolean(), server_default="false"),
        sa.Column("is_resolved", sa.Boolean(), server_default="false"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Continuity Scores ────────────────────────────────────────────────────
    op.create_table(
        "continuity_scores",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False, index=True),
        sa.Column("entity_name", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("risk_level", sa.String(), server_default="medium"),
        sa.Column("factors", sa.JSON(), server_default="{}"),
        sa.Column("recommendations", sa.JSON(), server_default="[]"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("continuity_scores")
    op.drop_table("risk_alerts")
    op.drop_table("decision_links")
    op.drop_table("decisions")
