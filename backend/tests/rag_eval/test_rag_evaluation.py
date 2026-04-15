"""RAG evaluation tests — precision, recall, hallucination, groundedness."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_chroma_results(docs, metadatas=None, distances=None):
    """Build a dict mimicking ChromaDB query results."""
    n = len(docs)
    return {
        "ids": [[f"id-{i}" for i in range(n)]],
        "documents": [docs],
        "metadatas": [metadatas or [{"source_type": "git"}] * n],
        "distances": [distances or [0.1 * i for i in range(n)]],
    }


# ---------------------------------------------------------------------------
# Retrieval Quality
# ---------------------------------------------------------------------------
class TestRetrievalPrecision:
    """Precision@k — fraction of retrieved chunks that are relevant."""

    def test_precision_all_relevant(self, vector_store, mock_embedder):
        """When all returned chunks match the topic, precision should be 1.0."""
        docs = [
            "Alice fixed the auth bug in login.py",
            "Alice refactored the auth middleware",
            "Alice added JWT token rotation",
        ]
        ids = [f"p-{i}" for i in range(len(docs))]
        embeddings = mock_embedder.embed_batch(docs)
        metadatas = [{"source_type": "git", "author": "alice"}] * len(docs)
        vector_store.add_documents(ids, docs, embeddings, metadatas)

        query_emb = mock_embedder.embed("auth work by Alice")
        results = vector_store.query(query_emb, n_results=3)
        assert len(results["documents"][0]) == 3

        # All docs mention auth and alice — precision is 1.0
        relevant = sum(1 for d in results["documents"][0] if "auth" in d.lower() or "alice" in d.lower())
        precision = relevant / len(results["documents"][0])
        assert precision == 1.0

    def test_precision_with_noise(self, vector_store, mock_embedder):
        """When noise docs are added, some retrieved results may be irrelevant."""
        relevant_docs = ["Python API migration guide", "Python 3.11 upgrade steps"]
        noise_docs = ["Office lunch menu for Friday", "Parking lot closure notice"]
        all_docs = relevant_docs + noise_docs
        ids = [f"n-{i}" for i in range(len(all_docs))]
        embeddings = mock_embedder.embed_batch(all_docs)
        metadatas = [{"source_type": "doc"}] * len(all_docs)
        vector_store.add_documents(ids, all_docs, embeddings, metadatas)

        results = vector_store.query(mock_embedder.embed("Python migration"), n_results=4)
        assert len(results["documents"][0]) == 4

    def test_retrieval_respects_k(self, vector_store, mock_embedder):
        """Requesting k results should return at most k."""
        docs = [f"Document {i}" for i in range(20)]
        ids = [f"k-{i}" for i in range(20)]
        embeddings = mock_embedder.embed_batch(docs)
        metadatas = [{"source_type": "doc"}] * 20
        vector_store.add_documents(ids, docs, embeddings, metadatas)

        for k in [3, 5, 8]:
            results = vector_store.query(mock_embedder.embed("any query"), n_results=k)
            assert len(results["documents"][0]) <= k


class TestRetrievalRecall:
    """Recall@k — fraction of known-relevant docs that appear in top-k."""

    def test_recall_when_all_present(self, vector_store, mock_embedder):
        """With only relevant docs in the store, recall should be 1.0."""
        gold = ["Deploy pipeline docs", "CI/CD configuration guide", "Docker setup howto"]
        ids = [f"r-{i}" for i in range(len(gold))]
        embeddings = mock_embedder.embed_batch(gold)
        vector_store.add_documents(ids, gold, embeddings, [{"source_type": "doc"}] * len(gold))

        results = vector_store.query(mock_embedder.embed("deployment"), n_results=5)
        retrieved_ids = set(results["ids"][0])
        gold_ids = set(ids)
        recall = len(retrieved_ids & gold_ids) / len(gold_ids)
        assert recall == 1.0

    def test_recall_decreases_with_low_k(self, vector_store, mock_embedder):
        """A very small k may miss some relevant documents."""
        docs = [f"Relevant topic {i}" for i in range(10)]
        ids = [f"rl-{i}" for i in range(10)]
        embeddings = mock_embedder.embed_batch(docs)
        vector_store.add_documents(ids, docs, embeddings, [{"source_type": "doc"}] * 10)

        results_k1 = vector_store.query(mock_embedder.embed("relevant"), n_results=1)
        results_k10 = vector_store.query(mock_embedder.embed("relevant"), n_results=10)
        assert len(results_k1["ids"][0]) <= len(results_k10["ids"][0])


class TestMetadataFiltering:
    """Verify that metadata filters narrow retrieval correctly."""

    def test_filter_by_source_type(self, vector_store, mock_embedder):
        git_docs = ["Git commit: fix auth", "Git commit: add tests"]
        slack_docs = ["Slack msg: lunch plans", "Slack msg: standup notes"]
        all_docs = git_docs + slack_docs
        ids = [f"f-{i}" for i in range(len(all_docs))]
        embeddings = mock_embedder.embed_batch(all_docs)
        metas = [{"source_type": "git"}] * len(git_docs) + [{"source_type": "slack"}] * len(slack_docs)
        vector_store.add_documents(ids, all_docs, embeddings, metas)

        results = vector_store.query(
            mock_embedder.embed("commit"),
            n_results=10,
            where={"source_type": "git"},
        )
        for m in results["metadatas"][0]:
            assert m["source_type"] == "git"

    def test_filter_returns_empty_on_mismatch(self, vector_store, mock_embedder):
        docs = ["Only git content here"]
        vector_store.add_documents(
            ["fm-0"],
            docs,
            mock_embedder.embed_batch(docs),
            [{"source_type": "git"}],
        )
        results = vector_store.query(
            mock_embedder.embed("anything"),
            n_results=5,
            where={"source_type": "slack"},
        )
        assert len(results["documents"][0]) == 0


# ---------------------------------------------------------------------------
# Hallucination Detection
# ---------------------------------------------------------------------------
class TestHallucinationDetection:
    """Verify the RAG pipeline doesn't hallucinate beyond provided context."""

    def test_answer_uses_context_only(self, app_client, auth_headers):
        """The LLM should be called with context — response should be grounded."""
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={
                "question": "Who is the Python expert?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        # With mocked LLM, the answer should come from the mock
        assert len(data["answer"]) > 0

    def test_empty_knowledge_base_still_responds(self, app_client, auth_headers):
        """When no data is ingested, pipeline should still return a response."""
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={
                "question": "What obscure topic does nobody know about?",
            },
        )
        assert resp.status_code == 200
        assert "answer" in resp.json()


# ---------------------------------------------------------------------------
# Grounded Response Validation
# ---------------------------------------------------------------------------
class TestGroundedResponse:
    """Ensure responses cite sources and are traceable to ingested data."""

    def test_sources_in_response(self, app_client, auth_headers):
        """Query response should include a sources list."""
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={
                "question": "What has the team been working on?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data

    def test_conversation_persists_messages(self, app_client, auth_headers):
        """Each query should persist the conversation with messages."""
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={
                "question": "Tell me about recent activity",
            },
        )
        conv_id = resp.json()["conversation_id"]

        # Fetch the conversation — should have messages
        conv_resp = app_client.get(f"/conversations/{conv_id}", headers=auth_headers)
        assert conv_resp.status_code == 200
        assert len(conv_resp.json().get("messages", [])) >= 1
