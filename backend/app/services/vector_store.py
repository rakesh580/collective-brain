import time

import chromadb


class VectorStoreService:
    def __init__(self, persist_dir: str):
        # Retry to handle race condition when multiple Uvicorn workers
        # start simultaneously and both try to create ChromaDB tables.
        for attempt in range(3):
            try:
                self.client = chromadb.PersistentClient(path=persist_dir)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)
        self.collection = self.client.get_or_create_collection(
            name="collective_brain",
            metadata={"hnsw:space": "cosine"},
        )

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

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 8,
        where: dict | None = None,
        room_id: str | None = None,
    ) -> dict:
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

        return self.collection.query(**kwargs)

    def count(self) -> int:
        return self.collection.count()

    def delete_by_artifact(self, artifact_id: str):
        self.collection.delete(where={"artifact_id": artifact_id})

    def delete_by_room(self, room_id: str):
        """Delete all vectors belonging to a specific room."""
        self.collection.delete(where={"room_id": room_id})
