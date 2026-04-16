"""
Locust load test for Collective Brain API.

Run:  locust -f tests/load/locustfile.py --host http://localhost:8000
"""

import random

from locust import HttpUser, between, task


class CollectiveBrainUser(HttpUser):
    """Simulates a typical user session: register → query → browse."""

    wait_time = between(1, 3)
    token: str = ""
    user_id: str = ""
    _conv_ids: list = []
    _room_ids: list = []

    def on_start(self):
        """Register a unique user and store the token."""
        suffix = random.randint(100000, 999999)
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": f"loaduser_{suffix}",
                "email": f"load{suffix}@test.com",
                "password": "LoadT3st!Pass",
                "display_name": f"Load User {suffix}",
            },
        )
        if resp.status_code == 201:
            data = resp.json()
            self.token = data["token"]
            self.user_id = data["user"]["id"]
        else:
            # Fallback: login
            resp = self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": f"loaduser_{suffix}",
                    "password": "LoadT3st!Pass",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["token"]
                self.user_id = data["user"]["id"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ── Core tasks ───────────────────────────────────────────────

    @task(5)
    def ai_query(self):
        """Simulate an AI query — the heaviest operation."""
        questions = [
            "Who is the best Python developer?",
            "What patterns exist in the team's code?",
            "Summarize recent team activity",
            "Who should review a React PR?",
            "What are the team's knowledge gaps?",
        ]
        resp = self.client.post(
            "/api/v1/query",
            headers=self.headers,
            json={"question": random.choice(questions)},
            name="/api/v1/query",
        )
        if resp.status_code == 200:
            conv_id = resp.json().get("conversation_id")
            if conv_id:
                self._conv_ids.append(conv_id)

    @task(3)
    def list_conversations(self):
        self.client.get("/api/v1/conversations", headers=self.headers, name="/api/v1/conversations")

    @task(2)
    def get_conversation(self):
        if self._conv_ids:
            conv_id = random.choice(self._conv_ids)
            self.client.get(
                f"/api/v1/conversations/{conv_id}",
                headers=self.headers,
                name="/api/v1/conversations/[id]",
            )

    @task(3)
    def list_members(self):
        self.client.get("/api/v1/members", headers=self.headers, name="/api/v1/members")

    @task(2)
    def create_room(self):
        suffix = random.randint(1, 99999)
        resp = self.client.post(
            "/api/v1/rooms",
            headers=self.headers,
            json={"name": f"loadroom-{suffix}"},
            name="/api/v1/rooms",
        )
        if resp.status_code == 201:
            self._room_ids.append(resp.json()["id"])

    @task(2)
    def send_room_message(self):
        if self._room_ids:
            room_id = random.choice(self._room_ids)
            self.client.post(
                f"/api/v1/rooms/{room_id}/messages",
                headers=self.headers,
                json={"content": f"Load test message {random.randint(1, 9999)}"},
                name="/api/v1/rooms/[id]/messages",
            )

    @task(1)
    def list_rooms(self):
        self.client.get("/api/v1/rooms", headers=self.headers, name="/api/v1/rooms")

    @task(1)
    def get_profile(self):
        self.client.get("/api/v1/auth/me", headers=self.headers, name="/api/v1/auth/me")

    @task(1)
    def list_discussions(self):
        self.client.get("/api/v1/discussions", headers=self.headers, name="/api/v1/discussions")
