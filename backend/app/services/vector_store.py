import logging
import time

import chromadb

logger = logging.getLogger("collective_brain.vector_store")


class VectorStoreService:
    def __init__(self, persist_dir: str):
        # Retry with exponential backoff to handle race condition when
        # multiple Uvicorn workers start simultaneously.
        for attempt in range(3):
            try:
                self.client = chromadb.PersistentClient(path=persist_dir)
                break
            except Exception as e:
                if attempt == 2:
                    logger.error("ChromaDB init failed after 3 attempts: %s", e)
                    raise
                wait = 1 * (2 ** attempt)
                logger.warning("ChromaDB init attempt %d failed, retrying in %ds: %s", attempt + 1, wait, e)
                time.sleep(wait)
        self.collection = self.client.get_or_create_collection(
            name="collective_brain",
            metadata={"hnsw:space": "cosine"},
        )
        # Cache collection count to avoid expensive calls per query
        self._cached_count: int | None = None
        self._count_cached_at: float = 0.0
        self._COUNT_CACHE_TTL = 10.0  # seconds

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        # Invalidate count cache after adding documents
        self._cached_count = None

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 8,
        where: dict | None = None,
        room_id: str | None = None,
    ) -> dict:
        empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Use cached count to avoid expensive call per query
        total = self.count()
        if total == 0:
            return empty
        n_results = min(n_results, total)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        # Build combined filter
        filters = []
        if room_id:
            filters.append({"room_id": room_id})
        if where:
            filters.append(where)

        if len(filters) == 1:
            kwargs["where"] = filters[0]
        elif len(filters) > 1:
            kwargs["where"] = {"$and": filters}

        try:
            return self.collection.query(**kwargs)
        except Exception as e:
            logger.warning("ChromaDB query with filter failed: %s (filter=%s)", e, kwargs.get("where"))
            # Retry without filter as fallback — log at error level since
            # this silently degrades search precision
            kwargs.pop("where", None)
            try:
                result = self.collection.query(**kwargs)
                logger.warning("ChromaDB fallback query succeeded without filter — results may include unrelated data")
                return result
            except Exception as e2:
                logger.error("ChromaDB query failed completely: %s", e2)
                return empty

    def count(self) -> int:
        """Return collection count with short-lived cache."""
        now = time.time()
        if self._cached_count is not None and (now - self._count_cached_at) < self._COUNT_CACHE_TTL:
            return self._cached_count
        self._cached_count = self.collection.count()
        self._count_cached_at = now
        return self._cached_count

    def delete_by_artifact(self, artifact_id: str):
        self.collection.delete(where={"artifact_id": artifact_id})
        self._cached_count = None

    def delete_by_room(self, room_id: str):
        """Delete all vectors belonging to a specific room."""
        self.collection.delete(where={"room_id": room_id})
        self._cached_count = None
