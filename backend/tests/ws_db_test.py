#!/usr/bin/env python3
"""Focused WebSocket + DB Write tests that reuse existing users."""

import asyncio
import json
import logging
import random
import statistics
import string
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ws_db_test")


def _rand(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


async def register_user(client, idx):
    uname = f"wsdb_{idx}_{_rand(6)}"
    try:
        resp = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@test.com",
                "password": "Test123!",
                "display_name": f"WSTest {idx}",
            },
            timeout=60.0,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {"token": data["token"], "user_id": data["user"]["id"], "username": uname}
    except Exception as e:
        log.warning("Register %d failed: %s", idx, e)
    return None


async def test_websocket(num_connections: int, tokens: list, room_id: str):
    log.info("=" * 60)
    log.info("WebSocket Test: %d connections to room %s", num_connections, room_id)
    log.info("=" * 60)

    import websockets

    connected = 0
    failed = 0
    messages_sent = 0
    messages_received = 0
    connect_times = []

    async def ws_client(idx):
        nonlocal connected, failed, messages_sent, messages_received
        token = tokens[idx % len(tokens)]
        start = time.monotonic()
        try:
            async with websockets.connect(
                f"{WS_URL}/rooms/ws/{room_id}",
                open_timeout=30,
                close_timeout=5,
            ) as ws:
                ct = (time.monotonic() - start) * 1000
                connect_times.append(ct)
                connected += 1

                await ws.send(json.dumps({"type": "auth", "token": token["token"]}))
                await ws.send(json.dumps({"type": "message", "content": f"ws msg {idx}"}))
                messages_sent += 1

                try:
                    async with asyncio.timeout(3):
                        while True:
                            await ws.recv()
                            messages_received += 1
                except (TimeoutError, Exception):
                    pass
        except Exception:
            failed += 1
            connect_times.append((time.monotonic() - start) * 1000)

    start = time.monotonic()
    batch_size = 50
    tasks = []
    for b in range(0, num_connections, batch_size):
        batch = [asyncio.create_task(ws_client(i)) for i in range(b, min(b + batch_size, num_connections))]
        tasks.extend(batch)
        await asyncio.sleep(0.3)

    await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.monotonic() - start

    p50 = statistics.median(connect_times) if connect_times else 0
    p95 = sorted(connect_times)[int(len(connect_times) * 0.95)] if connect_times else 0
    mx = max(connect_times) if connect_times else 0

    log.info(
        "  Connected: %d/%d (%.1f%%), Failed: %d",
        connected,
        num_connections,
        connected / num_connections * 100 if num_connections else 0,
        failed,
    )
    log.info("  Connect P50: %.0fms, P95: %.0fms, Max: %.0fms", p50, p95, mx)
    log.info("  Messages sent: %d, received: %d", messages_sent, messages_received)
    log.info("  Duration: %.1fs", duration)
    return connected, failed, messages_sent, messages_received


async def test_db_writes(concurrent_writers: int, writes_per_user: int, tokens: list, room_ids: list):
    log.info("=" * 60)
    log.info("DB Write Storm: %d writers x %d writes", concurrent_writers, writes_per_user)
    log.info("=" * 60)

    total = 0
    success = 0
    errors = 0
    latencies = []

    async def writer(idx):
        nonlocal total, success, errors
        token = tokens[idx % len(tokens)]
        room = room_ids[idx % len(room_ids)]
        headers = {"Authorization": f"Bearer {token['token']}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            for j in range(writes_per_user):
                start = time.monotonic()
                try:
                    resp = await client.post(
                        f"{BASE_URL}/rooms/{room}/messages",
                        json={"content": f"write {idx}-{j}: {_rand(30)}"},
                        headers=headers,
                    )
                    elapsed = (time.monotonic() - start) * 1000
                    total += 1
                    latencies.append(elapsed)
                    if 200 <= resp.status_code < 400:
                        success += 1
                    else:
                        errors += 1
                except Exception:
                    total += 1
                    errors += 1

    start = time.monotonic()
    tasks = [asyncio.create_task(writer(i)) for i in range(concurrent_writers)]
    await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.monotonic() - start

    p50 = statistics.median(latencies) if latencies else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    p99 = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
    mx = max(latencies) if latencies else 0
    rps = total / duration if duration else 0

    log.info(
        "  Total: %d, Success: %d (%.1f%%), Errors: %d", total, success, success / total * 100 if total else 0, errors
    )
    log.info("  Throughput: %.0f writes/s", rps)
    log.info("  Latency P50: %.0fms, P95: %.0fms, P99: %.0fms, Max: %.0fms", p50, p95, p99, mx)
    log.info("  Duration: %.1fs", duration)
    return total, success, errors


async def main():
    log.info("Registering test users (one batch, no overlap)...")
    tokens = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Register in smaller batches to avoid overwhelming
        for batch in range(0, 50, 10):
            batch_tasks = [register_user(client, i) for i in range(batch, batch + 10)]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict) and r:
                    tokens.append(r)
            await asyncio.sleep(0.5)

    log.info("Registered %d users", len(tokens))
    if len(tokens) < 5:
        log.error("Not enough users registered. Check server.")
        return

    # Create rooms
    room_ids = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(5):
            headers = {"Authorization": f"Bearer {tokens[i]['token']}", "Content-Type": "application/json"}
            resp = await client.post(
                f"{BASE_URL}/rooms", json={"name": f"Test Room {i}", "description": "load test"}, headers=headers
            )
            if resp.status_code in (200, 201):
                room_ids.append(resp.json()["id"])
    log.info("Created %d rooms", len(room_ids))
    if not room_ids:
        log.error("No rooms created")
        return

    # Add all users to all rooms so they can send messages
    log.info("Adding all users to all rooms...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, room_id in enumerate(room_ids):
            creator = tokens[i]
            # Collect user_ids that aren't the creator
            other_user_ids = [t["user_id"] for t in tokens if t["user_id"] != creator["user_id"]]
            # Add in batches of 20
            for batch_start in range(0, len(other_user_ids), 20):
                batch_ids = other_user_ids[batch_start : batch_start + 20]
                headers = {"Authorization": f"Bearer {creator['token']}", "Content-Type": "application/json"}
                resp = await client.post(
                    f"{BASE_URL}/rooms/{room_id}/members",
                    json={"user_ids": batch_ids},
                    headers=headers,
                )
                if resp.status_code == 200:
                    log.info("  Room %s: added %d members", room_id[:8], resp.json().get("added", 0))
    log.info("All users added to rooms")

    # WebSocket tests
    await test_websocket(100, tokens, room_ids[0])
    await test_websocket(500, tokens, room_ids[0])

    # DB Write tests
    await test_db_writes(50, 20, tokens, room_ids)
    await test_db_writes(100, 20, tokens, room_ids)
    await test_db_writes(200, 10, tokens, room_ids)

    log.info("=" * 60)
    log.info("ALL TESTS COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
