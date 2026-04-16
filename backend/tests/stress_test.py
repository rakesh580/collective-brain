#!/usr/bin/env python3
"""
Comprehensive Stress Test Runner for Collective Brain
=====================================================
Runs multiple test phases:
  Phase 1: REST API load (100 → 500 → 1000 concurrent users)
  Phase 2: WebSocket connection stress (100 → 500 simultaneous connections)
  Phase 3: Database write storm (concurrent inserts/reads)
  Phase 4: Memory & connection pool saturation

Outputs: detailed log + summary report.
"""

import asyncio
import json
import logging
import os
import random
import statistics
import string
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

# ── Configuration ──────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("tests/stress_test_results.log", mode="w"),
    ],
)
log = logging.getLogger("stress_test")


def _rand(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


@dataclass
class PhaseResult:
    name: str
    total_requests: int = 0
    success: int = 0
    failures: int = 0
    errors: int = 0
    latencies_ms: list = field(default_factory=list)
    status_codes: dict = field(default_factory=dict)
    duration_s: float = 0.0
    peak_rps: float = 0.0
    notes: list = field(default_factory=list)

    @property
    def rps(self):
        return self.total_requests / self.duration_s if self.duration_s > 0 else 0

    @property
    def success_rate(self):
        return (self.success / self.total_requests * 100) if self.total_requests > 0 else 0

    @property
    def p50(self):
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p95(self):
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * 0.95)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def p99(self):
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * 0.99)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    @property
    def max_latency(self):
        return max(self.latencies_ms) if self.latencies_ms else 0


# ── Helper: Register a test user ──────────────────────────
async def register_user(client: httpx.AsyncClient, idx: int) -> dict | None:
    uname = f"stress_{idx}_{_rand(6)}"
    try:
        resp = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@test.com",
                "password": "StressTest123!",
                "display_name": f"Stress User {idx}",
            },
            timeout=30.0,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {"token": data["token"], "user_id": data["user"]["id"], "username": uname}
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════
# Phase 1: REST API Load Test
# ══════════════════════════════════════════════════════════
async def phase1_rest_api(concurrent_users: int, duration_s: int = 30) -> PhaseResult:
    result = PhaseResult(name=f"REST API ({concurrent_users} users, {duration_s}s)")
    log.info("=" * 70)
    log.info("PHASE 1: REST API Load Test — %d concurrent users for %ds", concurrent_users, duration_s)
    log.info("=" * 70)

    endpoints = [
        ("GET", "/health", None),
        ("GET", "/health/detailed", None),
        ("GET", "/api/v1/members", None),
        ("GET", "/api/v1/conversations?limit=20", None),
        ("GET", "/api/v1/rooms?limit=50", None),
        ("GET", "/api/v1/insights/dashboard", None),
        ("GET", "/api/v1/graph/full", None),
        ("GET", "/api/v1/graph/expertise-matrix", None),
        ("GET", "/api/v1/analytics/activity-timeline?days=30", None),
        ("GET", "/api/v1/analytics/source-breakdown", None),
        ("GET", "/api/v1/search?q=python&limit=10", None),
        ("GET", "/api/v1/discussions?limit=20", None),
        ("GET", "/artifacts?limit=50", None),
        ("GET", "/api/v1/auth/me", None),
        ("GET", "/api/v1/auth/users", None),
    ]

    # Pre-register users
    log.info("Registering %d test users...", min(concurrent_users, 200))
    tokens = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [register_user(client, i) for i in range(min(concurrent_users, 200))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r:
                tokens.append(r["token"])
    log.info("Registered %d users", len(tokens))

    if not tokens:
        result.notes.append("CRITICAL: Could not register any users!")
        return result

    # Semaphore limits actual concurrency
    sem = asyncio.Semaphore(concurrent_users)
    stop_event = asyncio.Event()

    async def worker(worker_id: int):
        token = tokens[worker_id % len(tokens)]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            while not stop_event.is_set():
                method, path, body = random.choice(endpoints)
                async with sem:
                    start = time.monotonic()
                    try:
                        if method == "GET":
                            resp = await client.get(f"{BASE_URL}{path}", headers=headers)
                        else:
                            resp = await client.post(f"{BASE_URL}{path}", json=body, headers=headers)
                        elapsed = (time.monotonic() - start) * 1000
                        result.total_requests += 1
                        result.latencies_ms.append(elapsed)
                        code = resp.status_code
                        result.status_codes[code] = result.status_codes.get(code, 0) + 1
                        if 200 <= code < 400:
                            result.success += 1
                        elif code >= 500:
                            result.errors += 1
                        else:
                            result.failures += 1
                    except Exception:
                        elapsed = (time.monotonic() - start) * 1000
                        result.total_requests += 1
                        result.latencies_ms.append(elapsed)
                        result.errors += 1
                        result.status_codes["error"] = result.status_codes.get("error", 0) + 1

                await asyncio.sleep(random.uniform(0.01, 0.1))

    start_time = time.monotonic()
    workers = [asyncio.create_task(worker(i)) for i in range(concurrent_users)]

    await asyncio.sleep(duration_s)
    stop_event.set()
    await asyncio.gather(*workers, return_exceptions=True)
    result.duration_s = time.monotonic() - start_time

    log.info("Phase 1 complete: %d requests in %.1fs (%.0f rps)", result.total_requests, result.duration_s, result.rps)
    log.info(
        "  Success rate: %.1f%% | P50: %.0fms | P95: %.0fms | P99: %.0fms | Max: %.0fms",
        result.success_rate,
        result.p50,
        result.p95,
        result.p99,
        result.max_latency,
    )
    log.info("  Status codes: %s", result.status_codes)
    return result


# ══════════════════════════════════════════════════════════
# Phase 2: WebSocket Connection Stress
# ══════════════════════════════════════════════════════════
async def phase2_websocket(num_connections: int) -> PhaseResult:
    result = PhaseResult(name=f"WebSocket Stress ({num_connections} connections)")
    log.info("=" * 70)
    log.info("PHASE 2: WebSocket Stress — %d simultaneous connections", num_connections)
    log.info("=" * 70)

    try:
        import websockets
    except ImportError:
        log.warning("websockets not installed, trying pip install...")
        os.system(f"{sys.executable} -m pip install websockets -q")
        import websockets

    # Register users + create a room
    tokens = []
    room_id = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [register_user(client, i + 5000) for i in range(min(num_connections, 100))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r:
                tokens.append(r)

        if tokens:
            resp = await client.post(
                f"{BASE_URL}/rooms",
                json={"name": f"WS Stress Room {_rand(6)}"},
                headers={"Authorization": f"Bearer {tokens[0]['token']}", "Content-Type": "application/json"},
                timeout=30.0,
            )
            if resp.status_code == 201:
                room_id = resp.json()["id"]

    if not tokens or not room_id:
        result.notes.append("CRITICAL: Could not set up WebSocket test (no users/room)")
        return result

    log.info("Created room %s, testing with %d WS connections", room_id, num_connections)

    connected = 0
    failed = 0
    messages_sent = 0
    messages_received = 0
    connect_times = []

    async def ws_client(idx: int):
        nonlocal connected, failed, messages_sent, messages_received
        token = tokens[idx % len(tokens)]
        start = time.monotonic()
        try:
            async with websockets.connect(
                f"{WS_URL}/rooms/ws/{room_id}",
                additional_headers={},
                open_timeout=15,
                close_timeout=5,
            ) as ws:
                connect_time = (time.monotonic() - start) * 1000
                connect_times.append(connect_time)
                connected += 1

                # Send auth message
                await ws.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "token": token["token"],
                        }
                    )
                )

                # Send a message
                await ws.send(
                    json.dumps(
                        {
                            "type": "message",
                            "content": f"WS stress msg from {idx}",
                        }
                    )
                )
                messages_sent += 1

                # Listen for messages for a few seconds
                try:
                    async with asyncio.timeout(5):
                        while True:
                            msg = await ws.recv()
                            messages_received += 1
                except (TimeoutError, Exception):
                    pass

        except Exception:
            failed += 1
            connect_times.append((time.monotonic() - start) * 1000)

    start_time = time.monotonic()
    # Ramp up connections in batches
    batch_size = min(50, num_connections)
    ws_tasks = []
    for batch_start in range(0, num_connections, batch_size):
        batch_end = min(batch_start + batch_size, num_connections)
        batch = [asyncio.create_task(ws_client(i)) for i in range(batch_start, batch_end)]
        ws_tasks.extend(batch)
        await asyncio.sleep(0.5)  # stagger batches

    await asyncio.gather(*ws_tasks, return_exceptions=True)
    result.duration_s = time.monotonic() - start_time
    result.total_requests = num_connections
    result.success = connected
    result.failures = failed
    result.latencies_ms = connect_times

    log.info("Phase 2 complete: %d/%d connected, %d failed", connected, num_connections, failed)
    log.info("  Connect P50: %.0fms | P95: %.0fms | Max: %.0fms", result.p50, result.p95, result.max_latency)
    log.info("  Messages sent: %d, received: %d", messages_sent, messages_received)
    result.notes.append(f"Messages sent={messages_sent}, received={messages_received}")
    return result


# ══════════════════════════════════════════════════════════
# Phase 3: Database Write Storm
# ══════════════════════════════════════════════════════════
async def phase3_db_writes(concurrent_writers: int, writes_per_user: int = 20) -> PhaseResult:
    result = PhaseResult(name=f"DB Write Storm ({concurrent_writers} writers × {writes_per_user})")
    log.info("=" * 70)
    log.info("PHASE 3: Database Write Storm — %d writers × %d writes", concurrent_writers, writes_per_user)
    log.info("=" * 70)

    # Register users
    tokens = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [register_user(client, i + 10000) for i in range(min(concurrent_writers, 100))]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r:
                tokens.append(r)

    if not tokens:
        result.notes.append("CRITICAL: No users for DB write test")
        return result

    # Create rooms for writing
    room_ids = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(min(5, len(tokens))):
            resp = await client.post(
                f"{BASE_URL}/rooms",
                json={"name": f"Write Storm {i} {_rand(4)}"},
                headers={"Authorization": f"Bearer {tokens[i]['token']}", "Content-Type": "application/json"},
                timeout=30.0,
            )
            if resp.status_code == 201:
                room_ids.append(resp.json()["id"])

    if not room_ids:
        result.notes.append("CRITICAL: Could not create rooms for write test")
        return result

    log.info("Created %d rooms, starting %d writers...", len(room_ids), concurrent_writers)

    async def writer(idx: int):
        token = tokens[idx % len(tokens)]
        room = room_ids[idx % len(room_ids)]
        headers = {"Authorization": f"Bearer {token['token']}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            for j in range(writes_per_user):
                start = time.monotonic()
                try:
                    resp = await client.post(
                        f"{BASE_URL}/rooms/{room}/messages",
                        json={"content": f"Storm msg {idx}-{j}: {_rand(50)}"},
                        headers=headers,
                    )
                    elapsed = (time.monotonic() - start) * 1000
                    result.total_requests += 1
                    result.latencies_ms.append(elapsed)
                    code = resp.status_code
                    result.status_codes[code] = result.status_codes.get(code, 0) + 1
                    if 200 <= code < 400:
                        result.success += 1
                    else:
                        result.failures += 1
                except Exception:
                    result.total_requests += 1
                    result.errors += 1

    start_time = time.monotonic()
    tasks = [asyncio.create_task(writer(i)) for i in range(concurrent_writers)]
    await asyncio.gather(*tasks, return_exceptions=True)
    result.duration_s = time.monotonic() - start_time

    log.info(
        "Phase 3 complete: %d writes in %.1fs (%.0f writes/s)", result.total_requests, result.duration_s, result.rps
    )
    log.info(
        "  Success: %.1f%% | P50: %.0fms | P95: %.0fms | P99: %.0fms",
        result.success_rate,
        result.p50,
        result.p95,
        result.p99,
    )
    return result


# ══════════════════════════════════════════════════════════
# Phase 4: Connection Pool & Memory Saturation
# ══════════════════════════════════════════════════════════
async def phase4_saturation(burst_size: int = 500) -> PhaseResult:
    result = PhaseResult(name=f"Connection Saturation (burst={burst_size})")
    log.info("=" * 70)
    log.info("PHASE 4: Connection Pool Saturation — %d simultaneous requests", burst_size)
    log.info("=" * 70)

    # Register one user
    token = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        u = await register_user(client, 99999)
        if u:
            token = u["token"]

    if not token:
        result.notes.append("CRITICAL: No user for saturation test")
        return result

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Fire all requests simultaneously (no staggering)
    async def burst_request(idx: int):
        endpoints = [
            "/health",
            "/api/v1/members",
            "/api/v1/graph/full",
            "/api/v1/conversations?limit=5",
            "/api/v1/rooms?limit=5",
            "/api/v1/auth/me",
            "/api/v1/search?q=test",
        ]
        path = endpoints[idx % len(endpoints)]
        async with httpx.AsyncClient(timeout=60.0) as client:
            start = time.monotonic()
            try:
                resp = await client.get(f"{BASE_URL}{path}", headers=headers)
                elapsed = (time.monotonic() - start) * 1000
                result.total_requests += 1
                result.latencies_ms.append(elapsed)
                code = resp.status_code
                result.status_codes[code] = result.status_codes.get(code, 0) + 1
                if 200 <= code < 400:
                    result.success += 1
                elif code == 503:
                    result.failures += 1
                    result.notes.append(f"503 on {path} (circuit breaker / overload)")
                elif code >= 500:
                    result.errors += 1
                else:
                    result.failures += 1
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                result.total_requests += 1
                result.latencies_ms.append(elapsed)
                result.errors += 1
                err_type = type(e).__name__
                result.status_codes[f"error:{err_type}"] = result.status_codes.get(f"error:{err_type}", 0) + 1

    start_time = time.monotonic()
    tasks = [asyncio.create_task(burst_request(i)) for i in range(burst_size)]
    await asyncio.gather(*tasks, return_exceptions=True)
    result.duration_s = time.monotonic() - start_time

    log.info("Phase 4 complete: %d requests in %.1fs", result.total_requests, result.duration_s)
    log.info(
        "  Success: %.1f%% | P50: %.0fms | P95: %.0fms | Max: %.0fms",
        result.success_rate,
        result.p50,
        result.p95,
        result.max_latency,
    )
    log.info("  Status codes: %s", result.status_codes)
    return result


# ══════════════════════════════════════════════════════════
# Report Generator
# ══════════════════════════════════════════════════════════
def generate_report(phases: list[PhaseResult]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("  COLLECTIVE BRAIN — LOAD TEST REPORT")
    lines.append(f"  Generated: {datetime.now().isoformat()}")
    lines.append("=" * 80)
    lines.append("")

    overall_success = 0
    overall_total = 0
    overall_errors = 0

    for phase in phases:
        overall_total += phase.total_requests
        overall_success += phase.success
        overall_errors += phase.errors

        lines.append(f"┌{'─' * 68}┐")
        lines.append(f"│ {phase.name:<66} │")
        lines.append(f"├{'─' * 68}┤")
        lines.append(f"│ Total Requests:    {phase.total_requests:<48}│")
        lines.append(f"│ Success Rate:      {phase.success_rate:.1f}%{' ' * (47 - len(f'{phase.success_rate:.1f}%'))}│")
        lines.append(f"│ Throughput:        {phase.rps:.0f} req/s{' ' * (43 - len(f'{phase.rps:.0f} req/s'))}│")
        lines.append(f"│ Duration:          {phase.duration_s:.1f}s{' ' * (47 - len(f'{phase.duration_s:.1f}s'))}│")
        lines.append(f"│{'─' * 68}│")
        lines.append(f"│ Latency P50:       {phase.p50:.0f}ms{' ' * (46 - len(f'{phase.p50:.0f}ms'))}│")
        lines.append(f"│ Latency P95:       {phase.p95:.0f}ms{' ' * (46 - len(f'{phase.p95:.0f}ms'))}│")
        lines.append(f"│ Latency P99:       {phase.p99:.0f}ms{' ' * (46 - len(f'{phase.p99:.0f}ms'))}│")
        lines.append(f"│ Latency Max:       {phase.max_latency:.0f}ms{' ' * (46 - len(f'{phase.max_latency:.0f}ms'))}│")
        lines.append(f"│{'─' * 68}│")
        lines.append(
            f"│ Successes: {phase.success}  Failures: {phase.failures}  Errors: {phase.errors}{' ' * max(0, 68 - len(f' Successes: {phase.success}  Failures: {phase.failures}  Errors: {phase.errors}') - 1)}│"
        )
        codes_str = str(phase.status_codes)
        if len(codes_str) > 66:
            codes_str = codes_str[:63] + "..."
        lines.append(f"│ Codes: {codes_str}{' ' * max(0, 68 - len(f' Codes: {codes_str}') - 1)}│")
        for note in phase.notes[:3]:
            note_str = note[:64]
            lines.append(f"│ ⚠ {note_str}{' ' * max(0, 68 - len(f' ⚠ {note_str}') - 1)}│")
        lines.append(f"└{'─' * 68}┘")
        lines.append("")

    # Overall verdict
    lines.append("=" * 80)
    lines.append("  OVERALL VERDICT")
    lines.append("=" * 80)
    overall_rate = (overall_success / overall_total * 100) if overall_total > 0 else 0
    lines.append(f"  Total Requests: {overall_total}")
    lines.append(f"  Overall Success Rate: {overall_rate:.1f}%")
    lines.append(f"  Total Errors: {overall_errors}")
    lines.append("")

    # Grading
    if overall_rate >= 99:
        grade = "A+ EXCELLENT"
        verdict = "Application handles load exceptionally well. Production-ready."
    elif overall_rate >= 95:
        grade = "A  GOOD"
        verdict = "Application handles load well with minor issues under extreme stress."
    elif overall_rate >= 90:
        grade = "B  ACCEPTABLE"
        verdict = "Application handles moderate load. Needs optimization for peak traffic."
    elif overall_rate >= 80:
        grade = "C  NEEDS WORK"
        verdict = "Application struggles under load. Significant optimization needed."
    else:
        grade = "D  CRITICAL"
        verdict = "Application cannot handle concurrent users. Major architecture changes needed."

    lines.append(f"  Grade: {grade}")
    lines.append(f"  Verdict: {verdict}")
    lines.append("")

    # Recommendations
    lines.append("  RECOMMENDATIONS:")
    for phase in phases:
        if phase.success_rate < 95:
            lines.append(f"  - {phase.name}: Success rate {phase.success_rate:.1f}% is below target (95%)")
        if phase.p95 > 2000:
            lines.append(f"  - {phase.name}: P95 latency {phase.p95:.0f}ms exceeds 2s target")
        if phase.p99 > 5000:
            lines.append(f"  - {phase.name}: P99 latency {phase.p99:.0f}ms exceeds 5s target")
        if phase.errors > phase.total_requests * 0.05:
            lines.append(f"  - {phase.name}: Error rate {phase.errors / phase.total_requests * 100:.1f}% is high")

    # Architecture notes
    lines.append("")
    lines.append("  ARCHITECTURE NOTES (for scaling beyond test results):")
    lines.append("  - SQLite is single-writer. For >100 concurrent writers, PostgreSQL is required.")
    lines.append("  - WebSocket connections are per-process. Redis pub/sub enables multi-process.")
    lines.append("  - Circuit breaker protects LLM calls. AI endpoints degrade gracefully.")
    lines.append("  - In-memory fallback for Redis means single-process mode only.")
    lines.append("  - Connection pooling (PostgreSQL) handles 10-30 concurrent DB connections.")
    lines.append("=" * 80)

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# Main Runner
# ══════════════════════════════════════════════════════════
async def main():
    log.info("Starting Collective Brain Stress Test Suite")
    log.info("Target: %s", BASE_URL)

    # Verify server is running
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                log.error("Server not healthy: %d", resp.status_code)
                return
            log.info("Server is healthy: %s", resp.json())
    except Exception as e:
        log.error("Cannot reach server at %s: %s", BASE_URL, e)
        log.error("Start the server first: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return

    phases = []

    # Phase 1a: REST API — 100 users (warm-up)
    p1a = await phase1_rest_api(concurrent_users=100, duration_s=15)
    phases.append(p1a)

    # Phase 1b: REST API — 500 users
    p1b = await phase1_rest_api(concurrent_users=500, duration_s=20)
    phases.append(p1b)

    # Phase 1c: REST API — 1000 users
    p1c = await phase1_rest_api(concurrent_users=1000, duration_s=25)
    phases.append(p1c)

    # Phase 2a: WebSocket — 100 connections
    p2a = await phase2_websocket(num_connections=100)
    phases.append(p2a)

    # Phase 2b: WebSocket — 500 connections
    p2b = await phase2_websocket(num_connections=500)
    phases.append(p2b)

    # Phase 3: Database write storm — 100 concurrent writers
    p3 = await phase3_db_writes(concurrent_writers=100, writes_per_user=20)
    phases.append(p3)

    # Phase 4: Connection saturation — 500 simultaneous
    p4 = await phase4_saturation(burst_size=500)
    phases.append(p4)

    # Generate report
    report = generate_report(phases)
    log.info("\n" + report)

    # Save report to file
    with open("tests/LOAD_TEST_REPORT.txt", "w") as f:
        f.write(report)
    log.info("Report saved to tests/LOAD_TEST_REPORT.txt")


if __name__ == "__main__":
    asyncio.run(main())
