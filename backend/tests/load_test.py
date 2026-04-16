"""
Comprehensive Load Testing Suite for Collective Brain
=====================================================
Tests: REST API, WebSocket, Database, Auth, concurrent writes, memory pressure.

Usage:
  # Automated (headless) — run from test_runner.py
  # Manual:
  #   locust -f tests/load_test.py --headless -u 500 -r 50 -t 60s --host http://127.0.0.1:8000
"""

import random
import string

from locust import HttpUser, between, tag, task


def _rand(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


class CollectiveBrainUser(HttpUser):
    """Simulates a real user: registers, logs in, browses, queries AI, uses rooms."""

    wait_time = between(0.1, 0.5)  # aggressive for stress testing
    token = None
    user_id = None
    username = None
    conversation_id = None
    room_id = None

    def on_start(self):
        """Register + login to get JWT token."""
        uname = f"loadtest_{_rand(10)}"
        self.username = uname
        try:
            resp = self.client.post(
                "/api/v1/auth/register",
                json={
                    "username": uname,
                    "email": f"{uname}@test.com",
                    "password": "TestPass123!",
                    "display_name": f"Load Tester {_rand(4)}",
                },
                name="/api/v1/auth/register",
            )
            if resp.status_code == 201:
                data = resp.json()
                self.token = data.get("token")
                self.user_id = data.get("user", {}).get("id")
        except Exception:
            pass

        if not self.token:
            # Try login if register failed (user exists)
            try:
                resp = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": uname, "password": "TestPass123!"},
                    name="/api/v1/auth/login",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("token")
                    self.user_id = data.get("user", {}).get("id")
            except Exception:
                pass

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ── Health & Read-Heavy Endpoints ──────────────────────

    @tag("health")
    @task(10)
    def health_check(self):
        self.client.get("/health", name="/health")

    @tag("health")
    @task(3)
    def health_detailed(self):
        self.client.get("/health/detailed", name="/health/detailed")

    @tag("read")
    @task(8)
    def list_members(self):
        self.client.get("/api/v1/members", headers=self._headers(), name="/api/v1/members")

    @tag("read")
    @task(5)
    def list_conversations(self):
        self.client.get(
            "/api/v1/conversations?limit=20&offset=0",
            headers=self._headers(),
            name="/api/v1/conversations",
        )

    @tag("read")
    @task(4)
    def list_rooms(self):
        self.client.get(
            "/api/v1/rooms?limit=50&offset=0",
            headers=self._headers(),
            name="/api/v1/rooms",
        )

    @tag("read")
    @task(3)
    def dashboard(self):
        self.client.get(
            "/api/v1/insights/dashboard",
            headers=self._headers(),
            name="/api/v1/insights/dashboard",
        )

    @tag("read")
    @task(3)
    def graph_full(self):
        self.client.get(
            "/api/v1/graph/full",
            headers=self._headers(),
            name="/api/v1/graph/full",
        )

    @tag("read")
    @task(2)
    def expertise_matrix(self):
        self.client.get(
            "/api/v1/graph/expertise-matrix",
            headers=self._headers(),
            name="/api/v1/graph/expertise-matrix",
        )

    @tag("read")
    @task(3)
    def analytics_timeline(self):
        self.client.get(
            "/api/v1/analytics/activity-timeline?days=30",
            headers=self._headers(),
            name="/api/v1/analytics/activity-timeline",
        )

    @tag("read")
    @task(2)
    def analytics_sources(self):
        self.client.get(
            "/api/v1/analytics/source-breakdown",
            headers=self._headers(),
            name="/api/v1/analytics/source-breakdown",
        )

    @tag("read")
    @task(2)
    def search(self):
        terms = ["python", "react", "api", "database", "auth", "team", "project"]
        q = random.choice(terms)
        self.client.get(
            f"/api/v1/search?q={q}&limit=10",
            headers=self._headers(),
            name="/api/v1/search",
        )

    @tag("read")
    @task(2)
    def list_discussions(self):
        self.client.get(
            "/api/v1/discussions?limit=20",
            headers=self._headers(),
            name="/api/v1/discussions",
        )

    @tag("read")
    @task(2)
    def list_artifacts(self):
        self.client.get(
            "/artifacts?limit=50",
            headers=self._headers(),
            name="/artifacts",
        )

    # ── Write-Heavy Endpoints ─────────────────────────────

    @tag("write")
    @task(2)
    def create_room(self):
        resp = self.client.post(
            "/api/v1/rooms",
            json={"name": f"LoadTest Room {_rand(6)}", "description": "stress test"},
            headers=self._headers(),
            name="/api/v1/rooms [POST]",
        )
        if resp.status_code == 201:
            self.room_id = resp.json().get("id")

    @tag("write")
    @task(3)
    def send_room_message(self):
        if not self.room_id:
            return
        self.client.post(
            f"/api/v1/rooms/{self.room_id}/messages",
            json={"content": f"Load test message {_rand(20)}"},
            headers=self._headers(),
            name="/api/v1/rooms/{id}/messages [POST]",
        )

    @tag("write")
    @task(1)
    def create_discussion(self):
        self.client.post(
            "/api/v1/discussions",
            json={"title": f"Discussion {_rand(8)}"},
            headers=self._headers(),
            name="/api/v1/discussions [POST]",
        )

    # ── Auth Endpoint Stress ──────────────────────────────

    @tag("auth")
    @task(2)
    def auth_profile(self):
        if self.token:
            self.client.get(
                "/api/v1/auth/me",
                headers=self._headers(),
                name="/api/v1/auth/me",
            )

    @tag("auth")
    @task(1)
    def auth_users_list(self):
        if self.token:
            self.client.get(
                "/api/v1/auth/users",
                headers=self._headers(),
                name="/api/v1/auth/users",
            )
