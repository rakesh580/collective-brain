"""Phase 5: source_url on artifacts, verification fields on insights, content_hash for dedup.

Revision ID: 005_knowledge_verification
Revises: 004_enterprise
Create Date: 2026-04-09
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "005_knowledge_verification"
down_revision: str | None = "004_enterprise"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Artifacts: external source tracking ───────────────────────────────────
    op.add_column("artifacts", sa.Column("source_url", sa.String(2048), nullable=True))
    op.add_column("artifacts", sa.Column("external_id", sa.String(512), nullable=True))
    op.add_column("artifacts", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("artifacts", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_artifacts_external_id", "artifacts", ["external_id"])
    op.create_index("ix_artifacts_content_hash", "artifacts", ["content_hash"])

    # ── Insights: knowledge verification tracking ─────────────────────────────
    op.add_column("insights", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "insights", sa.Column("verified_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    )
    op.add_column("insights", sa.Column("verification_status", sa.String(20), nullable=True, server_default="pending"))
    # "pending" | "verified" | "outdated" | "disputed"
    op.add_column("insights", sa.Column("source_artifact_ids", sa.JSON(), server_default="[]"))
    op.add_column("insights", sa.Column("staleness_days", sa.Integer(), nullable=True))

    op.create_index("ix_insights_verification_status", "insights", ["verification_status"])

    # ── KnowledgeEmbeddings: content hash for deduplication on re-sync ────────
    op.add_column("knowledge_embeddings", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("knowledge_embeddings", sa.Column("source_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_embeddings", "source_url")
    op.drop_column("knowledge_embeddings", "content_hash")

    op.drop_index("ix_insights_verification_status", table_name="insights")
    op.drop_column("insights", "staleness_days")
    op.drop_column("insights", "source_artifact_ids")
    op.drop_column("insights", "verification_status")
    op.drop_column("insights", "verified_by")
    op.drop_column("insights", "verified_at")

    op.drop_index("ix_artifacts_content_hash", table_name="artifacts")
    op.drop_index("ix_artifacts_external_id", table_name="artifacts")
    op.drop_column("artifacts", "last_synced_at")
    op.drop_column("artifacts", "content_hash")
    op.drop_column("artifacts", "external_id")
    op.drop_column("artifacts", "source_url")
