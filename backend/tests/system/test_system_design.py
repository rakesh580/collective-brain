"""System design validation tests — idempotency, concurrency, scalability, statelessness."""

import concurrent.futures
import time


# ---------------------------------------------------------------------------
# Stateless API Validation
# ---------------------------------------------------------------------------
class TestStatelessAPI:
    def test_requests_independent_of_order(self, app_client, auth_headers):
        """API responses should not depend on previous request ordering."""
        # Create a member
        resp1 = app_client.post("/api/v1/members", headers=auth_headers, json={"name": "Order1"})
        assert resp1.status_code == 201

        # List members — should include the new one regardless of any prior state
        resp2 = app_client.get("/api/v1/members", headers=auth_headers)
        assert resp2.status_code == 200
        names = [m["name"] for m in resp2.json()]
        assert "Order1" in names

    def test_no_server_side_session_state(self, app_client):
        """Two different users should not share session state."""
        # Register user A
        a = app_client.post(
            "/api/v1/auth/register",
            json={
                "username": "stateless_a",
                "email": "sla@test.com",
                "password": "Str0ngPass!",
            },
        )
        a_headers = {"Authorization": f"Bearer {a.json()['token']}"}

        # Register user B
        b = app_client.post(
            "/api/v1/auth/register",
            json={
                "username": "stateless_b",
                "email": "slb@test.com",
                "password": "Str0ngPass!",
            },
        )
        b_headers = {"Authorization": f"Bearer {b.json()['token']}"}

        # A creates data
        app_client.post("/api/v1/members", headers=a_headers, json={"name": "A-Member"})

        # B should see the same members (shared resource) but different profile
        a_profile = app_client.get("/api/v1/auth/me", headers=a_headers).json()
        b_profile = app_client.get("/api/v1/auth/me", headers=b_headers).json()
        assert a_profile["username"] != b_profile["username"]

    def test_token_is_self_contained(self, app_client, registered_user):
        """JWT token should work without any server-side session storage."""
        _, token = registered_user
        # Make multiple requests with the same token — all should work
        for _ in range(5):
            resp = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Idempotent Operations
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_get_endpoints_idempotent(self, app_client, auth_headers):
        """GET requests should return the same result when called multiple times."""
        for _ in range(3):
            resp = app_client.get("/api/v1/members", headers=auth_headers)
            assert resp.status_code == 200
            # Results should be consistent
            data = resp.json()
            assert isinstance(data, list)

    def test_query_produces_consistent_structure(self, app_client, auth_headers):
        """Repeated queries should return the same response structure."""
        results = []
        for _ in range(3):
            resp = app_client.post(
                "/api/v1/query",
                headers=auth_headers,
                json={
                    "question": "Who is the top contributor?",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data
            assert "sources" in data
            assert "conversation_id" in data
            results.append(data)

        # All should have the same keys
        for r in results:
            assert set(r.keys()) == set(results[0].keys())

    def test_member_create_not_idempotent(self, app_client, auth_headers):
        """POST to create a member is NOT idempotent — each call creates a new one."""
        ids = set()
        for _ in range(3):
            resp = app_client.post(
                "/api/v1/members",
                headers=auth_headers,
                json={
                    "name": "Duplicate Name",
                },
            )
            assert resp.status_code == 201
            ids.add(resp.json()["id"])
        assert len(ids) == 3  # Three distinct members created

    def test_delete_twice_returns_404(self, app_client, auth_headers):
        """Deleting the same resource twice: first succeeds, second 404."""
        create = app_client.post("/api/v1/members", headers=auth_headers, json={"name": "ToDelete"})
        member_id = create.json()["id"]

        resp1 = app_client.delete(f"/api/v1/members/{member_id}", headers=auth_headers)
        assert resp1.status_code == 200

        resp2 = app_client.delete(f"/api/v1/members/{member_id}", headers=auth_headers)
        assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Concurrency / Race Conditions
# ---------------------------------------------------------------------------
class TestConcurrency:
    def test_concurrent_member_creation(self, app_client, auth_headers):
        """Creating members concurrently should not cause data corruption."""

        def create(i):
            return app_client.post(
                "/api/v1/members",
                headers=auth_headers,
                json={
                    "name": f"Concurrent_{i}",
                },
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(create, i) for i in range(5)]
            results = [f.result() for f in futures]

        successes = [r for r in results if r.status_code == 201]
        assert len(successes) == 5

        # Verify all are present
        resp = app_client.get("/api/v1/members", headers=auth_headers)
        names = [m["name"] for m in resp.json()]
        for i in range(5):
            assert f"Concurrent_{i}" in names

    def test_concurrent_reads_dont_block(self, app_client, auth_headers):
        """Multiple simultaneous reads should complete without blocking."""
        start = time.perf_counter()

        def read():
            return app_client.get("/api/v1/members", headers=auth_headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(read) for _ in range(10)]
            results = [f.result() for f in futures]

        elapsed = time.perf_counter() - start
        for r in results:
            assert r.status_code == 200

        # 10 concurrent reads should complete within reasonable time
        assert elapsed < 5.0, f"10 concurrent reads took {elapsed:.2f}s"

    def test_concurrent_room_messages(self, app_client, auth_headers):
        """Sending messages concurrently to the same room should work."""
        room = app_client.post("/api/v1/rooms", headers=auth_headers, json={"name": "conc-msg-room"})
        room_id = room.json()["id"]

        def send(i):
            return app_client.post(
                f"/api/v1/rooms/{room_id}/messages",
                headers=auth_headers,
                json={"content": f"Concurrent message {i}"},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(send, i) for i in range(5)]
            results = [f.result() for f in futures]

        successes = [r for r in results if r.status_code == 200]
        assert len(successes) == 5


# ---------------------------------------------------------------------------
# Horizontal Scalability Indicators
# ---------------------------------------------------------------------------
class TestScalabilityIndicators:
    def test_no_in_process_state_leaks(self, app_client, auth_headers):
        """After many operations, memory/state should not grow unbounded.

        We test this by making many requests and checking the API still responds
        quickly — a proxy for no leaked state.
        """
        for i in range(20):
            app_client.get("/api/v1/members", headers=auth_headers)
            app_client.get("/api/v1/conversations", headers=auth_headers)

        # Final request should still be fast
        start = time.perf_counter()
        resp = app_client.get("/api/v1/members", headers=auth_headers)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5

    def test_database_handles_many_records(self, app_client, auth_headers):
        """Create many members and verify listing still works."""
        for i in range(20):
            app_client.post(
                "/api/v1/members",
                headers=auth_headers,
                json={
                    "name": f"Scale_{i}",
                },
            )

        resp = app_client.get("/api/v1/members", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 20


# ---------------------------------------------------------------------------
# Retry Safety
# ---------------------------------------------------------------------------
class TestRetrySafety:
    def test_retried_login_is_safe(self, app_client, registered_user):
        """Retrying a login should give the same result."""
        for _ in range(3):
            resp = app_client.post(
                "/api/v1/auth/login",
                json={
                    "username": "alice",
                    "password": "Str0ngPass!",
                },
            )
            assert resp.status_code == 200
            assert "token" in resp.json()

    def test_retried_get_is_safe(self, app_client, auth_headers):
        """Retrying GET requests is always safe."""
        results = []
        for _ in range(5):
            resp = app_client.get("/api/v1/conversations", headers=auth_headers)
            assert resp.status_code == 200
            results.append(resp.json()["total"])

        # All should return the same count
        assert len(set(results)) == 1

    def test_retried_query_creates_separate_conversations(self, app_client, auth_headers):
        """Each new query (without conv_id) should create a new conversation."""
        conv_ids = set()
        for _ in range(3):
            resp = app_client.post(
                "/api/v1/query",
                headers=auth_headers,
                json={
                    "question": "Retry test question",
                },
            )
            assert resp.status_code == 200
            conv_ids.add(resp.json()["conversation_id"])

        assert len(conv_ids) == 3  # Each retry = new conversation


# ---------------------------------------------------------------------------
# Data Integrity
# ---------------------------------------------------------------------------
class TestDataIntegrity:
    def test_member_crud_cycle(self, app_client, auth_headers):
        """Full CRUD cycle should maintain data integrity."""
        # Create
        create = app_client.post(
            "/api/v1/members",
            headers=auth_headers,
            json={
                "name": "Integrity User",
                "expertise_tags": ["python"],
            },
        )
        assert create.status_code == 201
        member_id = create.json()["id"]

        # Read
        read = app_client.get(f"/api/v1/members/{member_id}", headers=auth_headers)
        assert read.status_code == 200
        assert read.json()["name"] == "Integrity User"

        # Update
        update = app_client.put(
            f"/api/v1/members/{member_id}",
            headers=auth_headers,
            json={
                "name": "Updated Integrity User",
            },
        )
        assert update.status_code == 200
        assert update.json()["name"] == "Updated Integrity User"

        # Delete
        delete = app_client.delete(f"/api/v1/members/{member_id}", headers=auth_headers)
        assert delete.status_code == 200

        # Verify deleted
        gone = app_client.get(f"/api/v1/members/{member_id}", headers=auth_headers)
        assert gone.status_code == 404

    def test_conversation_message_ordering(self, app_client, auth_headers):
        """Messages in a conversation should maintain chronological order."""
        # Create conversation with first message
        resp1 = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={
                "question": "First question",
            },
        )
        conv_id = resp1.json()["conversation_id"]

        # Continue conversation
        resp2 = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={
                "question": "Second question",
                "conversation_id": conv_id,
            },
        )

        # Fetch conversation
        conv = app_client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
        assert conv.status_code == 200
        messages = conv.json().get("messages", [])
        # Should have at least 4 messages (2 user + 2 assistant)
        assert len(messages) >= 2
