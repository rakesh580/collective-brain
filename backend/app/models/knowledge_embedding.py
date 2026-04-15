from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text

from app.db.database import Base

try:
    from pgvector.sqlalchemy import Vector

    _PGVECTOR_AVAILABLE = True
except ImportError:
    # Fallback type for environments without pgvector (tests, CI)
    from sqlalchemy import Text as Vector  # type: ignore[assignment]

    _PGVECTOR_AVAILABLE = False


class KnowledgeEmbedding(Base):
    """Stores text chunks with their vector embeddings.

    Replaces ChromaDB — all vectors live in Supabase alongside relational data.
    Each row is one chunk from an ingested artifact, scoped to an organization.
    """

    __tablename__ = "knowledge_embeddings"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    artifact_id = Column(String, ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=True, index=True)
    room_id = Column(String, ForeignKey("chat_rooms.id", ondelete="SET NULL"), nullable=True, index=True)

    # The raw text chunk stored alongside the vector (avoids a join during RAG)
    content = Column(Text, nullable=False)

    # Cosine-similarity search: vector(384) for all-MiniLM-L6-v2
    # Dimension is set by CB_EMBEDDING_DIMENSION (default 384)
    embedding = Column(Vector(384), nullable=True)

    # Rich metadata for filtering — source_type, member_ids, topics, etc.
    metadata_json = Column(JSON, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        # HNSW index for fast approximate nearest-neighbour search (pgvector ≥ 0.5)
        # Created in the Alembic migration after the extension is enabled.
        # Listed here as a comment so the intent is visible in the model.
        # Index("ix_knowledge_embeddings_hnsw", "embedding",
        #       postgresql_using="hnsw",
        #       postgresql_with={"m": 16, "ef_construction": 64},
        #       postgresql_ops={"embedding": "vector_cosine_ops"}),
        {},  # placeholder so __table_args__ is a non-empty tuple
    )
