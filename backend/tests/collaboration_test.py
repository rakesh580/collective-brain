"""
Multi-User Collaboration Test
=============================
Tests all collaboration features with a group of simulated users:
  1. User registration & login
  2. Room creation & membership
  3. Real-time room messaging (WebSocket)
  4. Shared AI conversations
  5. Discussion threads & messages

Usage:
    python tests/collaboration_test.py [--base-url http://localhost:8000]
"""

import asyncio
import json
import sys

import httpx
import websockets

BASE_URL = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"

# Test users
USERS = [
    {"username": "alice_test", "email": "alice@test.com", "password": "TestPass123!", "display_name": "Alice"},
    {"username": "bob_test", "email": "bob@test.com", "password": "TestPass123!", "display_name": "Bob"},
    {"username": "charlie_test", "email": "charlie@test.com", "password": "TestPass123!", "display_name": "Charlie"},
]

# Track results
results = {"passed": 0, "failed": 0, "tests": []}


def log(icon, msg):
    print(f"  {icon} {msg}")


def test_result(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    icon = "\033[92m✓\033[0m" if passed else "\033[91m✗\033[0m"
    results["tests"].append({"name": name, "status": status, "detail": detail})
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    log(icon, f"{name}" + (f" — {detail}" if detail else ""))


async def register_users(client: httpx.AsyncClient) -> list[dict]:
    """Register test users and return their tokens + info."""
    print("\n═══ Phase 1: User Registration & Login ═══")
    tokens = []
    for u in USERS:
        # Try register first, fall back to login if already exists
        resp = await client.post(f"{BASE_URL}/auth/register", json=u)
        if resp.status_code == 201:
            data = resp.json()
            tokens.append(
                {
                    "user_id": data["user"]["id"],
                    "username": u["username"],
                    "display_name": u["display_name"],
                    "token": data["token"],
                }
            )
            test_result(f"Register {u['username']}", True)
        elif resp.status_code == 409:
            # Already exists — login instead
            login_resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"username": u["username"], "password": u["password"]},
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                tokens.append(
                    {
                        "user_id": data["user"]["id"],
                        "username": u["username"],
                        "display_name": u["display_name"],
                        "token": data["token"],
                    }
                )
                test_result(f"Login {u['username']} (already registered)", True)
            else:
                test_result(f"Login {u['username']}", False, f"Status {login_resp.status_code}")
        else:
            test_result(f"Register {u['username']}", False, f"Status {resp.status_code}: {resp.text}")

    # Verify /auth/me works for each user
    for t in tokens:
        resp = await client.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {t['token']}"},
        )
        test_result(
            f"Auth /me for {t['username']}",
            resp.status_code == 200 and resp.json()["username"] == t["username"],
        )

    # Verify user list endpoint
    resp = await client.get(
        f"{BASE_URL}/auth/users",
        headers={"Authorization": f"Bearer {tokens[0]['token']}"},
    )
    test_result("List all users", resp.status_code == 200 and len(resp.json()) >= len(USERS))

    return tokens


async def test_rooms(client: httpx.AsyncClient, tokens: list[dict]):
    """Test room creation, membership, and messaging."""
    print("\n═══ Phase 2: Room Collaboration ═══")
    alice, bob, charlie = tokens[0], tokens[1], tokens[2]

    def auth(t):
        return {"Authorization": f"Bearer {t['token']}"}

    # Alice creates a room
    resp = await client.post(
        f"{BASE_URL}/rooms",
        json={"name": "Test Team Room", "description": "For collaboration testing"},
        headers=auth(alice),
    )
    test_result("Alice creates room", resp.status_code == 201)
    room_id = resp.json()["id"]

    # Alice adds Bob and Charlie
    resp = await client.post(
        f"{BASE_URL}/rooms/{room_id}/members",
        json={"user_ids": [bob["user_id"], charlie["user_id"]]},
        headers=auth(alice),
    )
    test_result("Alice adds Bob & Charlie to room", resp.status_code == 200)

    # Bob can see the room
    resp = await client.get(f"{BASE_URL}/rooms/{room_id}", headers=auth(bob))
    test_result("Bob can access the room", resp.status_code == 200)
    room_data = resp.json()
    member_ids = [m["user_id"] for m in room_data.get("members", [])]
    test_result(
        "Room has all 3 members",
        alice["user_id"] in member_ids and bob["user_id"] in member_ids and charlie["user_id"] in member_ids,
        f"Found {len(member_ids)} members",
    )

    # Bob sends a message via REST
    resp = await client.post(
        f"{BASE_URL}/rooms/{room_id}/messages",
        json={"content": "Hello from Bob! Testing room messaging."},
        headers=auth(bob),
    )
    test_result("Bob sends message via REST", resp.status_code == 200 or resp.status_code == 201)

    # Charlie sends a message
    resp = await client.post(
        f"{BASE_URL}/rooms/{room_id}/messages",
        json={"content": "Hey Bob! Charlie here. The room works!"},
        headers=auth(charlie),
    )
    test_result("Charlie sends message via REST", resp.status_code == 200 or resp.status_code == 201)

    # Alice reads messages — should see both
    resp = await client.get(f"{BASE_URL}/rooms/{room_id}", headers=auth(alice))
    messages = resp.json().get("messages", [])
    user_messages = [m for m in messages if m.get("message_type") == "user"]
    test_result(
        "Alice sees all messages",
        len(user_messages) >= 2,
        f"Found {len(user_messages)} user messages",
    )

    # Verify message attribution
    senders = {m.get("sender_name") for m in user_messages}
    test_result("Messages have sender attribution", "Bob" in senders and "Charlie" in senders, f"Senders: {senders}")

    return room_id


async def test_room_websocket(tokens: list[dict], room_id: str):
    """Test real-time WebSocket messaging in rooms."""
    print("\n═══ Phase 3: Real-Time WebSocket ═══")
    alice, bob = tokens[0], tokens[1]

    received_messages = []

    try:
        # Bob connects via WebSocket
        bob_ws = await websockets.connect(f"{WS_BASE}/rooms/ws/{room_id}")
        await bob_ws.send(json.dumps({"token": bob["token"]}))
        test_result("Bob connects WebSocket", True)

        # Give server a moment to register
        await asyncio.sleep(0.5)

        # Alice sends via WebSocket
        alice_ws = await websockets.connect(f"{WS_BASE}/rooms/ws/{room_id}")
        await alice_ws.send(json.dumps({"token": alice["token"]}))
        await asyncio.sleep(0.3)

        alice_ws_msg = {"type": "message", "content": "Real-time message from Alice!"}
        await alice_ws.send(json.dumps(alice_ws_msg))
        test_result("Alice sends WebSocket message", True)

        # Bob should receive it
        try:
            raw = await asyncio.wait_for(bob_ws.recv(), timeout=5.0)
            data = json.loads(raw)
            # Could be a presence update or the message
            attempts = 0
            while data.get("type") != "new_message" and attempts < 5:
                raw = await asyncio.wait_for(bob_ws.recv(), timeout=5.0)
                data = json.loads(raw)
                attempts += 1

            if data.get("type") == "new_message":
                msg = data.get("message", {})
                test_result(
                    "Bob receives real-time message",
                    "Alice" in msg.get("content", "") or "Alice" in msg.get("sender_name", ""),
                    f"Got: {msg.get('content', '')[:50]}",
                )
            else:
                test_result("Bob receives real-time message", False, f"Got event type: {data.get('type')}")
        except TimeoutError:
            test_result("Bob receives real-time message", False, "Timeout waiting for message")

        await alice_ws.close()
        await bob_ws.close()
    except Exception as e:
        test_result("WebSocket connection", False, str(e))


async def test_shared_conversations(client: httpx.AsyncClient, tokens: list[dict]):
    """Test AI conversation sharing between users."""
    print("\n═══ Phase 4: Shared AI Conversations ═══")
    alice, bob = tokens[0], tokens[1]

    def auth(t):
        return {"Authorization": f"Bearer {t['token']}"}

    # Alice starts a conversation with the AI
    resp = await client.post(
        f"{BASE_URL}/query",
        json={"question": "What topics has the team been working on?"},
        headers=auth(alice),
        timeout=60.0,
    )
    if resp.status_code == 200:
        data = resp.json()
        conv_id = data.get("conversation_id")
        test_result("Alice creates AI conversation", True, f"conv_id={conv_id[:8]}...")

        # Alice shares with Bob
        resp = await client.post(
            f"{BASE_URL}/conversations/{conv_id}/share",
            json={"user_ids": [bob["user_id"]]},
            headers=auth(alice),
        )
        test_result("Alice shares conversation with Bob", resp.status_code == 200)

        # Bob can see the conversation
        resp = await client.get(f"{BASE_URL}/conversations/{conv_id}", headers=auth(bob))
        test_result("Bob can access shared conversation", resp.status_code == 200)
        if resp.status_code == 200:
            messages = resp.json().get("messages", [])
            test_result(
                "Shared conversation has messages",
                len(messages) >= 2,
                f"Found {len(messages)} messages",
            )

        # Verify Alice's conversation list shows it
        resp = await client.get(f"{BASE_URL}/conversations?limit=5", headers=auth(alice))
        conv_ids = [c["id"] for c in resp.json().get("conversations", [])]
        test_result("Conversation appears in Alice's list", conv_id in conv_ids)

        # Verify Bob's conversation list shows it (shared)
        resp = await client.get(f"{BASE_URL}/conversations?limit=50", headers=auth(bob))
        conv_ids = [c["id"] for c in resp.json().get("conversations", [])]
        test_result("Shared conversation appears in Bob's list", conv_id in conv_ids)

        # Check participants
        resp = await client.get(f"{BASE_URL}/conversations/{conv_id}/participants", headers=auth(alice))
        test_result(
            "Participants list includes Bob",
            resp.status_code == 200 and any(p["user_id"] == bob["user_id"] for p in resp.json()),
        )

        # Charlie should NOT have access
        charlie = tokens[2]
        resp = await client.get(f"{BASE_URL}/conversations/{conv_id}", headers=auth(charlie))
        test_result("Charlie CANNOT access (not shared)", resp.status_code == 403)

    else:
        test_result("Alice creates AI conversation", False, f"Status {resp.status_code}: {resp.text[:100]}")
        # Skip dependent tests
        for name in ["Share conversation", "Bob access", "Participant check", "Charlie denied"]:
            test_result(name, False, "Skipped — conversation creation failed")


async def test_discussions(client: httpx.AsyncClient, tokens: list[dict]):
    """Test discussion threads and real-time messaging."""
    print("\n═══ Phase 5: Discussion Threads ═══")
    alice, bob, charlie = tokens[0], tokens[1], tokens[2]

    def auth(t):
        return {"Authorization": f"Bearer {t['token']}"}

    # Alice creates a discussion thread
    resp = await client.post(
        f"{BASE_URL}/discussions",
        json={"title": "Team Architecture Discussion"},
        headers=auth(alice),
    )
    test_result("Alice creates discussion thread", resp.status_code == 200)
    thread_id = resp.json()["id"]

    # Alice posts a message
    resp = await client.post(
        f"{BASE_URL}/discussions/{thread_id}/messages",
        json={"content": "Should we migrate to microservices?"},
        headers=auth(alice),
    )
    test_result("Alice posts message", resp.status_code == 200)
    alice_msg_id = resp.json()["id"]

    # Bob replies
    resp = await client.post(
        f"{BASE_URL}/discussions/{thread_id}/messages",
        json={"content": "I think we should start with a monolith and split later.", "parent_message_id": alice_msg_id},
        headers=auth(bob),
    )
    test_result("Bob replies to Alice", resp.status_code == 200)

    # Charlie adds a message
    resp = await client.post(
        f"{BASE_URL}/discussions/{thread_id}/messages",
        json={"content": "Agree with Bob. Let's keep it simple for now."},
        headers=auth(charlie),
    )
    test_result("Charlie adds message", resp.status_code == 200)
    charlie_msg_id = resp.json()["id"]

    # Get thread with all messages
    resp = await client.get(f"{BASE_URL}/discussions/{thread_id}", headers=auth(alice))
    test_result("Get thread detail", resp.status_code == 200)
    thread_data = resp.json()
    messages = thread_data.get("messages", [])
    test_result("Thread has 3 messages", len(messages) == 3, f"Found {len(messages)} messages")

    # Verify sender info on messages
    usernames = {m.get("username") for m in messages}
    test_result(
        "Messages show correct usernames",
        "alice_test" in usernames and "bob_test" in usernames and "charlie_test" in usernames,
        f"Usernames: {usernames}",
    )

    # Bob edits his message
    resp = await client.put(
        f"{BASE_URL}/discussions/{thread_id}/messages/{messages[1]['id']}",
        json={"content": "Actually, let's start with modular monolith!"},
        headers=auth(bob),
    )
    test_result("Bob edits his message", resp.status_code == 200)
    test_result("Edited message has edited_at", resp.json().get("edited_at") is not None)

    # Alice tries to edit Bob's message — should fail
    resp = await client.put(
        f"{BASE_URL}/discussions/{thread_id}/messages/{messages[1]['id']}",
        json={"content": "Hacked!"},
        headers=auth(alice),
    )
    test_result("Alice CANNOT edit Bob's message", resp.status_code == 403)

    # Charlie deletes his own message
    resp = await client.delete(
        f"{BASE_URL}/discussions/{thread_id}/messages/{charlie_msg_id}",
        headers=auth(charlie),
    )
    test_result("Charlie deletes his message", resp.status_code == 200)

    # Verify message count decreased
    resp = await client.get(f"{BASE_URL}/discussions/{thread_id}", headers=auth(alice))
    remaining = len(resp.json().get("messages", []))
    test_result("Thread now has 2 messages", remaining == 2, f"Found {remaining}")

    # List threads
    resp = await client.get(f"{BASE_URL}/discussions", headers=auth(bob))
    test_result("List threads", resp.status_code == 200 and resp.json()["total"] >= 1)

    return thread_id


async def test_discussion_websocket(tokens: list[dict], thread_id: str):
    """Test real-time WebSocket updates on discussions."""
    print("\n═══ Phase 6: Discussion WebSocket ═══")
    alice, bob = tokens[0], tokens[1]

    try:
        # Bob connects to discussion WebSocket
        bob_ws = await websockets.connect(f"{WS_BASE}/discussions/ws/{thread_id}")
        await bob_ws.send(json.dumps({"token": bob["token"]}))
        test_result("Bob connects to discussion WebSocket", True)
        await asyncio.sleep(0.3)

        # Alice sends a message via REST (should broadcast to Bob via WS)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/discussions/{thread_id}/messages",
                json={"content": "New message — testing WebSocket broadcast!"},
                headers={"Authorization": f"Bearer {alice['token']}"},
            )
            test_result("Alice posts message (triggers WS broadcast)", resp.status_code == 200)

        # Bob should receive it via WebSocket
        try:
            raw = await asyncio.wait_for(bob_ws.recv(), timeout=5.0)
            data = json.loads(raw)
            test_result(
                "Bob receives real-time discussion update",
                data.get("type") == "new_message",
                f"Event: {data.get('type')}",
            )
        except TimeoutError:
            test_result("Bob receives real-time discussion update", False, "Timeout")

        await bob_ws.close()
    except Exception as e:
        test_result("Discussion WebSocket", False, str(e))


async def test_cross_feature(client: httpx.AsyncClient, tokens: list[dict]):
    """Test cross-feature interactions."""
    print("\n═══ Phase 7: Cross-Feature Verification ═══")
    alice = tokens[0]

    def auth(t):
        return {"Authorization": f"Bearer {t['token']}"}

    # Search works
    resp = await client.get(f"{BASE_URL}/search?q=test&limit=5", headers=auth(alice))
    test_result("Search endpoint works", resp.status_code == 200)

    # Knowledge graph works
    resp = await client.get(f"{BASE_URL}/graph/full", headers=auth(alice))
    test_result("Knowledge graph loads", resp.status_code == 200)

    # Analytics work
    resp = await client.get(f"{BASE_URL}/analytics/activity-timeline?days=30", headers=auth(alice))
    test_result("Analytics endpoint works", resp.status_code == 200)

    # Insights dashboard works
    resp = await client.get(f"{BASE_URL}/insights/dashboard", headers=auth(alice))
    test_result("Insights dashboard works", resp.status_code == 200)

    # Members list works
    resp = await client.get(f"{BASE_URL}/members", headers=auth(alice))
    test_result("Members list works", resp.status_code == 200)

    # Rooms list shows rooms user is in
    resp = await client.get(f"{BASE_URL}/rooms", headers=auth(alice))
    rooms_data = resp.json() if resp.status_code == 200 else {}
    room_count = rooms_data.get("total", len(rooms_data.get("rooms", [])))
    test_result("Rooms list works", resp.status_code == 200 and room_count >= 1, f"Found {room_count} rooms")


async def main():
    global BASE_URL, WS_BASE

    if len(sys.argv) > 1 and sys.argv[1] == "--base-url":
        BASE_URL = sys.argv[2]
        WS_BASE = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")

    print("╔══════════════════════════════════════════════╗")
    print("║   Collective Brain — Collaboration Test      ║")
    print(f"║   Server: {BASE_URL:<35s}║")
    print("╚══════════════════════════════════════════════╝")

    # Check server health first
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                print(f"\n\033[91mERROR: Server not healthy (status {resp.status_code})\033[0m")
                sys.exit(1)
            health = resp.json()
            print(f"\n  Server: OK | LLM: {health.get('llm_provider')} | Vectors: {health.get('vector_store_count')}")
        except httpx.ConnectError:
            print(f"\n\033[91mERROR: Cannot connect to {BASE_URL}\033[0m")
            print("  Start the backend: cd backend && .venv/bin/uvicorn app.main:app --port 8000")
            sys.exit(1)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: Register/Login
        tokens = await register_users(client)
        if len(tokens) < 3:
            print("\n\033[91mFATAL: Could not register/login all 3 users\033[0m")
            sys.exit(1)

        # Phase 2: Rooms
        room_id = await test_rooms(client, tokens)

        # Phase 3: Room WebSocket
        await test_room_websocket(tokens, room_id)

        # Phase 4: Shared Conversations
        await test_shared_conversations(client, tokens)

        # Phase 5: Discussion Threads
        thread_id = await test_discussions(client, tokens)

        # Phase 6: Discussion WebSocket
        await test_discussion_websocket(tokens, thread_id)

        # Phase 7: Cross-Feature
        await test_cross_feature(client, tokens)

    # Summary
    total = results["passed"] + results["failed"]
    pct = (results["passed"] / total * 100) if total > 0 else 0

    print("\n╔══════════════════════════════════════════════╗")
    print(f"║   RESULTS: {results['passed']}/{total} passed ({pct:.0f}%)                    ║")
    if results["failed"] == 0:
        print("║   \033[92m★ ALL TESTS PASSED ★\033[0m                        ║")
    else:
        print(f"║   \033[91m✗ {results['failed']} TESTS FAILED\033[0m                           ║")
    print("╚══════════════════════════════════════════════╝")

    if results["failed"] > 0:
        print("\nFailed tests:")
        for t in results["tests"]:
            if t["status"] == "FAIL":
                print(f"  ✗ {t['name']}: {t['detail']}")

    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
