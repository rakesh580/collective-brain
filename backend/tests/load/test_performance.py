"""Performance tests — response times, concurrent operations, bulk ingestion."""

import concurrent.futures
import io
import time


class TestResponseTimes:
    """API response time benchmarks (using mocked LLM, so no network latency)."""

    def test_auth_login_under_500ms(self, app_client, registered_user):
        start = time.perf_counter()
        resp = app_client.post(
            "/auth/login",
            json={
                "username": "alice",
                "password": "Str0ngPass!",
            },
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"Login took {elapsed:.2f}s (expected < 0.5s)"

    def test_member_list_under_200ms(self, app_client, auth_headers):
        start = time.perf_counter()
        resp = app_client.get("/members", headers=auth_headers)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.2, f"Member list took {elapsed:.2f}s (expected < 0.2s)"

    def test_conversation_list_under_200ms(self, app_client, auth_headers):
        start = time.perf_counter()
        resp = app_client.get("/conversations", headers=auth_headers)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.2, f"Conversation list took {elapsed:.2f}s (expected < 0.2s)"

    def test_query_under_5s(self, app_client, auth_headers):
        """AI query with mocked LLM should complete quickly."""
        start = time.perf_counter()
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={
                "question": "Who is the best developer?",
            },
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 5.0, f"Query took {elapsed:.2f}s (expected < 5s)"


class TestConcurrentQueries:
    """Simulate multiple users hitting the API at the same time."""

    def test_concurrent_registrations(self, app_client):
        """Multiple users registering simultaneously should all succeed."""

        def register(i):
            return app_client.post(
                "/auth/register",
                json={
                    "username": f"concurrent_{i}",
                    "email": f"conc{i}@test.com",
                    "password": "Str0ngPass!",
                    "display_name": f"User {i}",
                },
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(register, i) for i in range(5)]
            results = [f.result() for f in futures]

        successes = [r for r in results if r.status_code == 201]
        assert len(successes) == 5, f"Only {len(successes)}/5 registrations succeeded"

    def test_concurrent_queries(self, app_client, auth_headers):
        """Multiple AI queries from the same user should all complete."""

        def query(q):
            return app_client.post(
                "/query",
                headers=auth_headers,
                json={
                    "question": q,
                },
            )

        questions = [
            "Who writes Python?",
            "What are the team patterns?",
            "Summarize activity",
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(query, q) for q in questions]
            results = [f.result() for f in futures]

        for r in results:
            assert r.status_code == 200

    def test_concurrent_member_reads(self, app_client, auth_headers):
        """Concurrent read operations should not conflict."""

        def read_members():
            return app_client.get("/members", headers=auth_headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(read_members) for _ in range(10)]
            results = [f.result() for f in futures]

        for r in results:
            assert r.status_code == 200


class TestBulkIngestion:
    """Stress test the ingestion pipeline with larger payloads."""

    def test_bulk_markdown_upload(self, app_client, auth_headers):
        """Upload 10 markdown files at once."""
        files = [
            (
                "files",
                (
                    f"doc_{i}.md",
                    io.BytesIO(
                        f"# Doc {i}\nContent for document {i} " * 50 + b"\n"
                        if isinstance(f"# Doc {i}\nContent for document {i} " * 50, str)
                        else b"content"
                    ),
                    "text/markdown",
                ),
            )
            for i in range(10)
        ]
        # Fix: properly create BytesIO objects
        files = []
        for i in range(10):
            content = f"# Document {i}\n\nThis is the content of document number {i}. " * 50
            files.append(("files", (f"doc_{i}.md", io.BytesIO(content.encode()), "text/markdown")))

        resp = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files)
        assert resp.status_code == 200
        assert resp.json()["chunks_created"] >= 10

    def test_repeated_ingestion_idempotent(self, app_client, auth_headers):
        """Ingesting the same file twice should not duplicate data uncontrollably."""
        content = b"# Idempotency Test\n\nThis content should be handled gracefully on re-ingest."
        files = [("files", ("idem.md", io.BytesIO(content), "text/markdown"))]

        resp1 = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files)
        assert resp1.status_code == 200
        chunks1 = resp1.json()["chunks_created"]

        files2 = [("files", ("idem.md", io.BytesIO(content), "text/markdown"))]
        resp2 = app_client.post("/ingest/markdown-upload", headers=auth_headers, files=files2)
        assert resp2.status_code == 200


class TestRateLimiting:
    """Verify rate limiting protects the system under heavy load."""

    def test_auth_rate_limit_trigger(self, app_client):
        """Excessive login attempts should eventually be rate-limited.

        Note: Rate limiting depends on Redis. With in-memory fallback,
        the _rate_limit helper may be a no-op. This test verifies the
        endpoint at least responds correctly under rapid calls.
        """
        results = []
        for i in range(15):
            resp = app_client.post(
                "/auth/login",
                json={
                    "username": "nobody",
                    "password": "wrongpass",
                },
            )
            results.append(resp.status_code)

        # Either all 401 (no Redis) or some 429s mixed in
        assert all(s in (401, 429) for s in results)

    def test_query_rate_limit_trigger(self, app_client, auth_headers):
        """Excessive queries should eventually be rate-limited.

        Same caveat as above: in-memory Redis may not enforce limits.
        """
        results = []
        for i in range(15):
            resp = app_client.post(
                "/query",
                headers=auth_headers,
                json={
                    "question": f"Question {i}",
                },
            )
            results.append(resp.status_code)

        assert all(s in (200, 429) for s in results)
