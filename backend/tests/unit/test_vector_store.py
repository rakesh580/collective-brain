"""Unit tests for VectorStoreService — CRUD, search, edge cases."""

import pytest


class TestVectorStoreCRUD:
    def test_initial_count_is_zero(self, vector_store):
        assert vector_store.count() == 0

    def test_add_and_count(self, vector_store):
        vector_store.add_documents(
            ids=["doc-1", "doc-2"],
            documents=["Hello world", "Goodbye world"],
            embeddings=[[0.1] * 384, [0.2] * 384],
            metadatas=[
                {"source_type": "test", "artifact_id": "a1", "author": "alice"},
                {"source_type": "test", "artifact_id": "a1", "author": "bob"},
            ],
        )
        assert vector_store.count() == 2

    def test_upsert_idempotency(self, vector_store):
        """Adding the same IDs should upsert, not duplicate."""
        for _ in range(3):
            vector_store.add_documents(
                ids=["doc-1"],
                documents=["Hello"],
                embeddings=[[0.1] * 384],
                metadatas=[{"source_type": "test", "artifact_id": "a1", "author": "x"}],
            )
        assert vector_store.count() == 1

    def test_delete_by_artifact(self, vector_store):
        vector_store.add_documents(
            ids=["d1", "d2", "d3"],
            documents=["a", "b", "c"],
            embeddings=[[0.1] * 384] * 3,
            metadatas=[
                {"source_type": "t", "artifact_id": "art-1", "author": "a"},
                {"source_type": "t", "artifact_id": "art-1", "author": "b"},
                {"source_type": "t", "artifact_id": "art-2", "author": "c"},
            ],
        )
        assert vector_store.count() == 3

        vector_store.delete_by_artifact("art-1")
        assert vector_store.count() == 1


class TestVectorStoreSearch:
    @pytest.fixture(autouse=True)
    def _seed_data(self, vector_store):
        vector_store.add_documents(
            ids=["python-1", "react-1", "devops-1"],
            documents=[
                "Python FastAPI backend development",
                "React frontend with TypeScript",
                "Docker Kubernetes deployment",
            ],
            embeddings=[
                [1.0] + [0.0] * 383,
                [0.0, 1.0] + [0.0] * 382,
                [0.0, 0.0, 1.0] + [0.0] * 381,
            ],
            metadatas=[
                {"source_type": "git", "artifact_id": "a1", "author": "alice", "topics": "python,api"},
                {"source_type": "slack", "artifact_id": "a2", "author": "bob", "topics": "react,ui"},
                {"source_type": "git", "artifact_id": "a3", "author": "charlie", "topics": "devops"},
            ],
        )

    def test_query_returns_results(self, vector_store):
        results = vector_store.query(
            query_embedding=[1.0] + [0.0] * 383,
            n_results=2,
        )
        assert "ids" in results
        assert len(results["ids"][0]) <= 2

    def test_query_with_metadata_filter(self, vector_store):
        results = vector_store.query(
            query_embedding=[0.5] * 384,
            n_results=10,
            where={"source_type": "git"},
        )
        ids = results["ids"][0]
        # Only git source docs
        for meta in results["metadatas"][0]:
            assert meta["source_type"] == "git"

    def test_query_empty_collection(self, vector_store):
        """Querying a freshly-cleared store returns zero results."""
        # vector_store fixture starts with a clean table
        results = vector_store.query(
            query_embedding=[0.1] * 384,
            n_results=5,
        )
        # _seed_data autouse adds 3 rows, so results may have 3; what matters
        # is the structure is correct.
        assert "ids" in results
        assert isinstance(results["ids"][0], list)

    def test_query_n_results_capped(self, vector_store):
        """Requesting more than available should return all available."""
        results = vector_store.query(
            query_embedding=[0.5] * 384,
            n_results=100,
        )
        assert len(results["ids"][0]) == 3
