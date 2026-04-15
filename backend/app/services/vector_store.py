"""pgvector-based VectorStoreService with OpenTelemetry spans + Prometheus metrics."""

import logging
import time
from collections.abc import Generator

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("collective_brain.vector_store")


class VectorStoreService:
    """pgvector-backed store with the same API surface as the old ChromaDB wrapper."""

    def __init__(self, db_session_factory):
        self._factory = db_session_factory
        self._cached_count: int | None = None

    def _session(self) -> Generator[Session, None, None]:
        db = self._factory()
        try:
            yield db
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        """Upsert chunks into knowledge_embeddings."""
        from app.services.metrics import INGESTION_CHUNKS_TOTAL
        from app.services.telemetry import get_tracer

        tracer = get_tracer("collective_brain.vector_store")
        org_id = metadatas[0].get("organization_id", "-") if metadatas else "-"

        with tracer.start_as_current_span(
            "vector_store.add_documents",
            attributes={
                "vector_store.count": len(ids),
                "vector_store.org_id": org_id,
            },
        ):
            db = self._factory()
            try:
                for chunk_id, content, embedding, meta in zip(ids, documents, embeddings, metadatas):
                    _org_id = meta.get("organization_id") or meta.get("org_id")
                    artifact_id = meta.get("artifact_id")
                    room_id = meta.get("room_id")

                    db.execute(
                        text("""
                            INSERT INTO knowledge_embeddings
                                (id, organization_id, artifact_id, room_id,
                                 content, embedding, metadata_json, created_at)
                            VALUES
                                (:id, :org_id, :artifact_id, :room_id,
                                 :content, :embedding::vector, :meta::jsonb, now())
                            ON CONFLICT (id) DO UPDATE SET
                                content         = EXCLUDED.content,
                                embedding       = EXCLUDED.embedding,
                                metadata_json   = EXCLUDED.metadata_json,
                                artifact_id     = EXCLUDED.artifact_id,
                                room_id         = EXCLUDED.room_id,
                                organization_id = EXCLUDED.organization_id
                        """),
                        {
                            "id": chunk_id,
                            "org_id": _org_id,
                            "artifact_id": artifact_id,
                            "room_id": room_id,
                            "content": content,
                            "embedding": _to_pg_vector(embedding),
                            "meta": _to_jsonb(meta),
                        },
                    )
                db.commit()
                self._cached_count = None
                INGESTION_CHUNKS_TOTAL.labels(
                    source_type=metadatas[0].get("source_type", "unknown") if metadatas else "unknown",
                    org_id=org_id,
                ).inc(len(ids))
            except Exception as e:
                db.rollback()
                logger.error("VectorStore upsert failed: %s", e)
                raise
            finally:
                db.close()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 8,
        where: dict | None = None,
        room_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict:
        """Cosine-similarity nearest-neighbour search."""
        from app.services.metrics import VECTOR_SEARCH_LATENCY, VECTOR_SEARCH_TOTAL
        from app.services.telemetry import get_tracer

        empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        org_id = organization_id or "-"
        tracer = get_tracer("collective_brain.vector_store")
        t0 = time.perf_counter()

        with tracer.start_as_current_span(
            "vector_store.query",
            attributes={
                "vector_store.n_results": n_results,
                "vector_store.org_id": org_id,
                "vector_store.room_filter": room_id or "",
            },
        ) as span:
            if self.count() == 0:
                return empty

            n_results = min(n_results, self.count())
            conditions = []
            params: dict = {
                "embedding": _to_pg_vector(query_embedding),
                "n": n_results,
            }

            if organization_id:
                conditions.append("organization_id = :org_id")
                params["org_id"] = organization_id
            if room_id:
                conditions.append("room_id = :room_id")
                params["room_id"] = room_id
            for i, (k, v) in enumerate((where or {}).items()):
                conditions.append(f"metadata_json ->> :{f'wk{i}'} = :{f'wv{i}'}")
                params[f"wk{i}"] = k
                params[f"wv{i}"] = str(v)

            where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT id, content, metadata_json,
                       1 - (embedding <=> :embedding::vector) AS similarity
                FROM knowledge_embeddings
                {where_sql}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :n
            """

            db = self._factory()
            try:
                rows = db.execute(text(sql), params).fetchall()
            except Exception as e:
                logger.error("VectorStore query failed: %s", e)
                span.record_exception(e)
                return empty
            finally:
                db.close()

        elapsed = time.perf_counter() - t0
        VECTOR_SEARCH_LATENCY.labels(org_id=org_id).observe(elapsed)
        VECTOR_SEARCH_TOTAL.labels(org_id=org_id).inc()

        ids, documents, metadatas, distances = [], [], [], []
        for row in rows:
            ids.append(row.id)
            documents.append(row.content)
            metadatas.append(row.metadata_json or {})
            distances.append(float(1 - row.similarity))

        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def count(self) -> int:
        if self._cached_count is not None:
            return self._cached_count
        db = self._factory()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM knowledge_embeddings")).scalar()
            self._cached_count = int(result or 0)
            return self._cached_count
        except Exception:
            return 0
        finally:
            db.close()

    def delete_by_artifact(self, artifact_id: str):
        db = self._factory()
        try:
            db.execute(
                text("DELETE FROM knowledge_embeddings WHERE artifact_id = :aid"),
                {"aid": artifact_id},
            )
            db.commit()
            self._cached_count = None
        finally:
            db.close()

    def delete_by_room(self, room_id: str):
        db = self._factory()
        try:
            db.execute(
                text("DELETE FROM knowledge_embeddings WHERE room_id = :rid"),
                {"rid": room_id},
            )
            db.commit()
            self._cached_count = None
        finally:
            db.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _to_pg_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _to_jsonb(d: dict) -> str:
    import json

    return json.dumps(d)
