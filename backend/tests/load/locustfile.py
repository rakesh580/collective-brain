"""
Locust load test for Collective Brain API.

Simulates 50-100 concurrent users performing realistic workflows:
register -> browse dashboard -> query AI -> manage decisions -> search.

Run headless:
    locust -f tests/load/locustfile.py --host http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 60s --headless

Run with Web UI:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Endpoint reference (from main.py router registrations):
    /api/v1/auth/*          - auth.router       (prefix /auth)
    /api/v1/query           - query.router       (no sub-prefix, route is /query)
    /api/v1/insights/*      - insights.router    (prefix /insights)
    /api/v1/decisions/*     - decisions.router    (prefix /decisions)
    /api/v1/search          - search.router       (prefix /search)
    /api/v1/members         - members.router      (prefix /members)
    /api/v1/rooms/*         - rooms.router        (prefix /rooms)
    /api/v1/analytics/*     - analytics.router    (prefix /analytics)
    /api/v1/artifacts       - artifacts.router     (prefix /artifacts)
    /api/v1/risk-radar/*    - risk_radar.router   (prefix /risk-radar)
    /api/v1/continuity/*    - continuity.router   (prefix /continuity)
    /api/v1/graph/*         - graph.router        (prefix /graph)
"""

import logging
import random
import time
import uuid

from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

# ── Shared test data ─────────────────────────────────────────────────────────
_AI_QUESTIONS = [
    "Who is the best Python developer on the team?",
    "What patterns exist in the team's recent code contributions?",
    "Summarize the team's activity this week",
    "Who should review a React pull request?",
    "What are the team's knowledge gaps?",
    "Which decisions are at risk of going stale?",
    "What topics has the team discussed most recently?",
    "Who has expertise in security?",
]

_SEARCH_TERMS = [
    "python",
    "architecture",
    "security",
    "database",
    "API design",
    "testing",
    "deployment",
    "performance",
    "react",
    "kubernetes",
]


# ── Event hooks for custom reporting ─────────────────────────────────────────
_error_counts: dict[str, int] = {}
_start_time: float = 0.0


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global _start_time
    _start_time = time.time()
    logger.info("Load test started against %s", environment.host)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    elapsed = time.time() - _start_time
    stats = environment.stats
    total = stats.total
    logger.info(
        "\n"
        "====================================================================\n"
        "  LOAD TEST SUMMARY\n"
        "====================================================================\n"
        "  Duration:        %.1fs\n"
        "  Total requests:  %d\n"
        "  Failures:        %d (%.2f%%)\n"
        "  Avg response:    %dms\n"
        "  Median:          %dms\n"
        "  p95:             %dms\n"
        "  p99:             %dms\n"
        "  Max:             %dms\n"
        "  Requests/sec:    %.1f\n"
        "====================================================================",
        elapsed,
        total.num_requests,
        total.num_failures,
        (total.num_failures / max(total.num_requests, 1)) * 100,
        total.avg_response_time,
        total.median_response_time or 0,
        total.get_response_time_percentile(0.95) or 0,
        total.get_response_time_percentile(0.99) or 0,
        total.max_response_time,
        total.total_rps,
    )


# ── User class ───────────────────────────────────────────────────────────────
class CollectiveBrainUser(HttpUser):
    """Simulates a typical user session: register -> browse -> query -> manage."""

    wait_time = between(1, 3)
    token: str = ""
    user_id: str = ""

    # Collected IDs for parameterised follow-up requests
    _conv_ids: list[str]
    _room_ids: list[str]
    _decision_ids: list[str]

    def on_start(self):
        """Register a unique user and store the JWT token."""
        self._conv_ids = []
        self._room_ids = []
        self._decision_ids = []

        suffix = uuid.uuid4().hex[:10]
        resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "username": f"loaduser_{suffix}",
                "email": f"load_{suffix}@test.com",
                "password": "LoadT3st!Pass",
                "display_name": f"Load User {suffix}",
            },
            name="/api/v1/auth/register",
        )
        if resp.status_code == 201:
            data = resp.json()
            self.token = data["token"]
            self.user_id = data["user"]["id"]
        else:
            # Fallback: attempt login (user may already exist from a prior run)
            resp = self.client.post(
                "/api/v1/auth/login",
                json={
                    "username": f"loaduser_{suffix}",
                    "password": "LoadT3st!Pass",
                },
                name="/api/v1/auth/login",
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["token"]
                self.user_id = data["user"]["id"]
            else:
                logger.warning(
                    "User setup failed (register=%d, login=%d)",
                    resp.status_code,
                    resp.status_code,
                )

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ── High-frequency tasks (dashboard browsing) ────────────────────────────

    @task(10)
    def view_dashboard(self):
        """GET /api/v1/insights/dashboard  (most common user action)"""
        self.client.get(
            "/api/v1/insights/dashboard",
            headers=self._headers,
            name="/api/v1/insights/dashboard",
        )

    @task(5)
    def list_members(self):
        """GET /api/v1/members"""
        self.client.get(
            "/api/v1/members",
            headers=self._headers,
            name="/api/v1/members",
        )

    @task(5)
    def list_decisions(self):
        """GET /api/v1/decisions"""
        resp = self.client.get(
            "/api/v1/decisions",
            headers=self._headers,
            name="/api/v1/decisions",
        )
        if resp.status_code == 200:
            items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
            for item in items[:3]:
                _id = item.get("id")
                if _id and _id not in self._decision_ids:
                    self._decision_ids.append(_id)

    # ── Medium-frequency tasks ───────────────────────────────────────────────

    @task(3)
    def ai_query(self):
        """POST /api/v1/query  (LLM-backed, rate-limited to 10/min)

        Uses a 30s timeout since LLM calls can be slow.
        Only fires ~3x per user cycle to stay under rate limits.
        """
        resp = self.client.post(
            "/api/v1/query",
            headers=self._headers,
            json={"question": random.choice(_AI_QUESTIONS)},
            name="/api/v1/query",
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            conv_id = body.get("conversation_id")
            if conv_id and conv_id not in self._conv_ids:
                self._conv_ids.append(conv_id)
        # 429 is expected under load — don't count as failure
        elif resp.status_code == 429:
            resp.success()

    @task(3)
    def search_knowledge(self):
        """GET /api/v1/search?q=<term>"""
        q = random.choice(_SEARCH_TERMS)
        self.client.get(
            f"/api/v1/search?q={q}",
            headers=self._headers,
            name="/api/v1/search?q=[term]",
        )

    @task(3)
    def list_rooms(self):
        """GET /api/v1/rooms"""
        resp = self.client.get(
            "/api/v1/rooms",
            headers=self._headers,
            name="/api/v1/rooms",
        )
        if resp.status_code == 200:
            items = resp.json() if isinstance(resp.json(), list) else resp.json().get("rooms", [])
            for item in items[:3]:
                _id = item.get("id")
                if _id and _id not in self._room_ids:
                    self._room_ids.append(_id)

    @task(3)
    def list_conversations(self):
        """GET /api/v1/conversations"""
        self.client.get(
            "/api/v1/conversations",
            headers=self._headers,
            name="/api/v1/conversations",
        )

    # ── Lower-frequency tasks ────────────────────────────────────────────────

    @task(2)
    def view_analytics(self):
        """GET /api/v1/analytics/activity-timeline"""
        self.client.get(
            "/api/v1/analytics/activity-timeline",
            headers=self._headers,
            name="/api/v1/analytics/activity-timeline",
        )

    @task(2)
    def list_artifacts(self):
        """GET /api/v1/artifacts"""
        self.client.get(
            "/api/v1/artifacts",
            headers=self._headers,
            name="/api/v1/artifacts",
        )

    @task(2)
    def get_profile(self):
        """GET /api/v1/auth/me"""
        self.client.get(
            "/api/v1/auth/me",
            headers=self._headers,
            name="/api/v1/auth/me",
        )

    @task(2)
    def view_conversation(self):
        """GET /api/v1/conversations/<id>  (only if we have one)"""
        if self._conv_ids:
            conv_id = random.choice(self._conv_ids)
            self.client.get(
                f"/api/v1/conversations/{conv_id}",
                headers=self._headers,
                name="/api/v1/conversations/[id]",
            )

    @task(2)
    def view_decision(self):
        """GET /api/v1/decisions/<id>  (only if we collected one)"""
        if self._decision_ids:
            did = random.choice(self._decision_ids)
            self.client.get(
                f"/api/v1/decisions/{did}",
                headers=self._headers,
                name="/api/v1/decisions/[id]",
            )

    # ── Rare tasks ───────────────────────────────────────────────────────────

    @task(1)
    def scan_risks(self):
        """POST /api/v1/risk-radar/scan"""
        self.client.post(
            "/api/v1/risk-radar/scan",
            headers=self._headers,
            json={},
            name="/api/v1/risk-radar/scan",
            timeout=15,
        )

    @task(1)
    def get_continuity_dashboard(self):
        """GET /api/v1/continuity/dashboard"""
        self.client.get(
            "/api/v1/continuity/dashboard",
            headers=self._headers,
            name="/api/v1/continuity/dashboard",
        )

    @task(1)
    def get_graph_stats(self):
        """GET /api/v1/graph/stats"""
        self.client.get(
            "/api/v1/graph/stats",
            headers=self._headers,
            name="/api/v1/graph/stats",
        )

    @task(1)
    def get_graph_full(self):
        """GET /api/v1/graph/full"""
        self.client.get(
            "/api/v1/graph/full",
            headers=self._headers,
            name="/api/v1/graph/full",
        )

    @task(1)
    def list_discussions(self):
        """GET /api/v1/discussions"""
        self.client.get(
            "/api/v1/discussions",
            headers=self._headers,
            name="/api/v1/discussions",
        )

    @task(1)
    def get_weekly_summary(self):
        """GET /api/v1/insights/weekly"""
        self.client.get(
            "/api/v1/insights/weekly",
            headers=self._headers,
            name="/api/v1/insights/weekly",
        )

    @task(1)
    def get_expertise_matrix(self):
        """GET /api/v1/analytics/expertise-matrix"""
        self.client.get(
            "/api/v1/analytics/expertise-matrix",
            headers=self._headers,
            name="/api/v1/analytics/expertise-matrix",
        )

    @task(1)
    def get_health(self):
        """GET /api/v1/analytics/health  (team health score)"""
        self.client.get(
            "/api/v1/analytics/health",
            headers=self._headers,
            name="/api/v1/analytics/health",
        )

    @task(1)
    def risk_alerts(self):
        """GET /api/v1/risk-radar/alerts"""
        self.client.get(
            "/api/v1/risk-radar/alerts",
            headers=self._headers,
            name="/api/v1/risk-radar/alerts",
        )
