"""pgvector: enable extension + knowledge_embeddings table (replaces ChromaDB).

Revision ID: 003_pgvector
Revises: 002_multi_tenancy
Create Date: 2026-04-07
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "003_pgvector"
down_revision: str | None = "002_multi_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match CB_EMBEDDING_DIMENSION (default 384 for all-MiniLM-L6-v2)
VECTOR_DIM = 384


def upgrade() -> None:
    # Enable pgvector — already available on all Supabase projects
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "artifact_id",
            sa.String(),
            sa.ForeignKey("artifacts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("chat_rooms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        # Use raw DDL for the vector column — SQLAlchemy doesn't know this type
        # without pgvector registered; the HNSW index is created separately below.
        sa.Column("embedding", sa.Text(), nullable=True),   # placeholder, altered below
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Alter the placeholder TEXT column to vector(VECTOR_DIM)
    op.execute(f"ALTER TABLE knowledge_embeddings ALTER COLUMN embedding TYPE vector({VECTOR_DIM}) USING embedding::vector({VECTOR_DIM})")

    # Indexes
    op.create_index("ix_knowledge_embeddings_org_id", "knowledge_embeddings", ["organization_id"])
    op.create_index("ix_knowledge_embeddings_artifact_id", "knowledge_embeddings", ["artifact_id"])
    op.create_index("ix_knowledge_embeddings_room_id", "knowledge_embeddings", ["room_id"])

    # HNSW index for fast approximate cosine-similarity search (pgvector ≥ 0.5)
    op.execute("""
        CREATE INDEX ix_knowledge_embeddings_hnsw
        ON knowledge_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embeddings_hnsw")
    op.drop_index("ix_knowledge_embeddings_room_id", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_artifact_id", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_org_id", table_name="knowledge_embeddings")
    op.drop_table("knowledge_embeddings")
    # Do NOT drop the vector extension — other tables/projects may use it
