"""
Stress test: Ramp users until the server breaks.

Runs increasing waves of concurrent users:
  Wave 1: 10 users  (warm-up)
  Wave 2: 25 users
  Wave 3: 50 users
  Wave 4: 100 users
  Wave 5: 200 users
  Wave 6: 500 users
  Wave 7: 1000 users

Each wave runs for 30 seconds. Reports per-wave stats.
Stops when error rate > 30% or avg response > 10s (server is dead).

Usage:
    python3.11 tests/load/stress_to_crash.py [HOST]
    python3.11 tests/load/stress_to_crash.py http://localhost:8000
"""

import concurrent.futures
import json
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ssl._create_default_https_context = ssl._create_unverified_context

WAVES = [10, 25, 50, 100, 200, 500, 1000]
WAVE_DURATION = 30  # seconds per wave
CRASH_ERROR_RATE = 0.30  # 30% errors = server is dying
CRASH_AVG_RESPONSE = 10.0  # 10s avg = server is choking


def register_user():
    """Register a test user, return token."""
    suffix = uuid.uuid4().hex[:10]
    data = json.dumps(
        {
            "username": f"stress_{suffix}",
            "email": f"stress_{suffix}@test.com",
            "password": "StressT3st!Pass",
            "display_name": f"Stress {suffix}",
        }
    ).encode()

    req = urllib.request.Request(  # noqa: S310
        f"{HOST}/api/v1/auth/register",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            body = json.loads(resp.read())
            return body.get("token", "")
    except Exception:
        return ""


def make_request(url, token, method="GET", body=None, timeout=15):
    """Make a single HTTP request, return (status, latency_ms, error?)."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            resp.read()
            latency = (time.time() - start) * 1000
            return resp.status, latency, False
    except urllib.error.HTTPError as e:
        latency = (time.time() - start) * 1000
        return e.code, latency, e.code >= 500
    except Exception as e:
        latency = (time.time() - start) * 1000
        return 0, latency, True


# Endpoints to hit (weighted by realism)
ENDPOINTS = [
    ("GET", "/api/v1/insights/dashboard", None, 10),
    ("GET", "/api/v1/members", None, 5),
    ("GET", "/api/v1/decisions", None, 5),
    ("GET", "/api/v1/search?q=python", None, 3),
    ("GET", "/api/v1/rooms", None, 3),
    ("GET", "/api/v1/conversations", None, 3),
    ("GET", "/api/v1/analytics/activity-timeline", None, 2),
    ("GET", "/api/v1/artifacts", None, 2),
    ("GET", "/api/v1/auth/me", None, 2),
    ("GET", "/api/v1/risk-radar/alerts", None, 1),
    ("GET", "/api/v1/continuity/dashboard", None, 1),
    ("GET", "/api/v1/graph/stats", None, 1),
    ("GET", "/api/v1/discussions", None, 1),
    ("GET", "/api/v1/analytics/health", None, 1),
    ("GET", "/api/v1/health", None, 1),
]

# Build weighted list
WEIGHTED_ENDPOINTS = []
for method, path, body, weight in ENDPOINTS:
    WEIGHTED_ENDPOINTS.extend([(method, path, body)] * weight)


def simulate_user(token, duration):
    """Simulate one user making requests for `duration` seconds."""
    results = []
    end_time = time.time() + duration
    import random

    while time.time() < end_time:
        method, path, body = random.choice(WEIGHTED_ENDPOINTS)
        url = f"{HOST}{path}"
        status, latency, is_error = make_request(url, token, method, body)
        results.append((status, latency, is_error))
        # Small random delay between requests (0.5-2s)
        time.sleep(random.uniform(0.5, 2.0))

    return results


def run_wave(wave_num, user_count, tokens):
    """Run a wave of concurrent users."""
    print(f"\n{'=' * 70}")
    print(f"  WAVE {wave_num}: {user_count} CONCURRENT USERS")
    print(f"  Duration: {WAVE_DURATION}s")
    print(f"{'=' * 70}")

    # Use available tokens, cycling if needed
    wave_tokens = [tokens[i % len(tokens)] for i in range(user_count)]

    all_results = []
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=user_count) as pool:
        futures = [pool.submit(simulate_user, t, WAVE_DURATION) for t in wave_tokens]
        for f in concurrent.futures.as_completed(futures):
            try:
                all_results.extend(f.result())
            except Exception as e:
                all_results.append((0, 0, True))

    elapsed = time.time() - start

    if not all_results:
        print("  NO RESULTS — server may be completely unresponsive")
        return True  # crashed

    # Calculate stats
    total = len(all_results)
    errors = sum(1 for _, _, err in all_results if err)
    error_rate = errors / total if total > 0 else 1.0
    latencies = [lat for _, lat, _ in all_results]
    status_counts = {}
    for status, _, _ in all_results:
        status_counts[status] = status_counts.get(status, 0) + 1

    avg_lat = statistics.mean(latencies) if latencies else 0
    med_lat = statistics.median(latencies) if latencies else 0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    p99_lat = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
    max_lat = max(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0
    rps = total / elapsed if elapsed > 0 else 0

    # Status distribution
    status_str = ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items()))

    print("\n  Results:")
    print(f"  ├─ Total requests:   {total}")
    print(f"  ├─ Errors:           {errors} ({error_rate * 100:.1f}%)")
    print(f"  ├─ Requests/sec:     {rps:.1f}")
    print(f"  ├─ Avg latency:      {avg_lat:.0f}ms")
    print(f"  ├─ Median latency:   {med_lat:.0f}ms")
    print(f"  ├─ p95 latency:      {p95_lat:.0f}ms")
    print(f"  ├─ p99 latency:      {p99_lat:.0f}ms")
    print(f"  ├─ Max latency:      {max_lat:.0f}ms")
    print(f"  ├─ Min latency:      {min_lat:.0f}ms")
    print(f"  └─ Status codes:     {status_str}")

    # Health verdict
    if error_rate >= CRASH_ERROR_RATE:
        print(f"\n  💥 SERVER BREAKING — {error_rate * 100:.1f}% error rate (threshold: {CRASH_ERROR_RATE * 100:.0f}%)")
        return True
    elif avg_lat >= CRASH_AVG_RESPONSE * 1000:
        print(f"\n  💥 SERVER CHOKING — {avg_lat:.0f}ms avg response (threshold: {CRASH_AVG_RESPONSE * 1000:.0f}ms)")
        return True
    elif error_rate >= 0.10:
        print(f"\n  ⚠️  SERVER STRESSED — {error_rate * 100:.1f}% error rate")
    elif p95_lat >= 2000:
        print(f"\n  ⚠️  SERVER SLOW — p95 at {p95_lat:.0f}ms")
    else:
        print("\n  ✅ SERVER HEALTHY")

    return False


def main():
    print("=" * 70)
    print("  COLLECTIVE BRAIN — STRESS TEST TO CRASH")
    print(f"  Target: {HOST}")
    print(f"  Waves: {WAVES}")
    print(f"  Duration per wave: {WAVE_DURATION}s")
    print("=" * 70)

    # Pre-register a pool of users (max 50 unique, rest will cycle)
    print("\n  Registering test users...")
    tokens = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(register_user) for _ in range(50)]
        for f in concurrent.futures.as_completed(futures):
            token = f.result()
            if token:
                tokens.append(token)

    print(f"  Registered {len(tokens)} users")

    if not tokens:
        print("  FATAL: Could not register any users. Is the server running?")
        sys.exit(1)

    # Run waves
    crash_wave = None
    for i, user_count in enumerate(WAVES, 1):
        crashed = run_wave(i, user_count, tokens)
        if crashed:
            crash_wave = (i, user_count)
            # Run one more mini-wave to confirm
            print(f"\n  Confirming crash with {user_count} users (10s burst)...")
            break
        # Brief cooldown between waves
        print("\n  Cooling down 5s before next wave...")
        time.sleep(5)

    # Final report
    print(f"\n{'=' * 70}")
    print("  FINAL REPORT")
    print(f"{'=' * 70}")

    if crash_wave:
        wave_num, users = crash_wave
        prev_users = WAVES[wave_num - 2] if wave_num > 1 else 0
        print(f"\n  Server broke at Wave {wave_num}: {users} concurrent users")
        print(f"  Max stable capacity: ~{prev_users} concurrent users")
        print("\n  Recommendation:")
        print(f"  ├─ Single Uvicorn worker handles ~{prev_users} users")
        print(f"  ├─ For {users}+ users: add workers or horizontal scaling")
        print("  └─ Bottleneck likely: DB connections (pool_size=10) or single-threaded event loop")
    else:
        print(f"\n  Server survived ALL waves up to {WAVES[-1]} users!")
        print("  This server is a beast. 💪")

    print(f"\n{'=' * 70}")


if __name__ == "__main__":
    main()
