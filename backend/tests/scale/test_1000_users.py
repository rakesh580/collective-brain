"""Scale test — verify the application handles 1000+ concurrent users without errors.

This test registers 1000 users and has each perform a realistic session:
  1. Register
  2. Browse members
  3. Ask an AI query
  4. Create a room and send a message
  5. Create a discussion thread
  6. List conversations

It tracks every response and asserts ZERO errors at the end.
"""

import concurrent.futures
import statistics
import time
from dataclasses import dataclass, field

import pytest


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
@dataclass
class UserResult:
    user_id: int
    register_ok: bool = False
    login_ok: bool = False
    members_ok: bool = False
    query_ok: bool = False
    room_create_ok: bool = False
    room_message_ok: bool = False
    discussion_ok: bool = False
    conversations_ok: bool = False
    errors: list = field(default_factory=list)
    latencies: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scale test suite
# ---------------------------------------------------------------------------
NUM_USERS = 1000
# Batch size for concurrent registration waves
BATCH_SIZE = 50
# Max workers for concurrent operations
MAX_WORKERS = 20


class TestThousandUserScale:
    """Verify the application handles 1000 users without errors."""

    @pytest.fixture(autouse=True)
    def _setup(self, app_client):
        """Store client for all test methods."""
        self.client = app_client

    # -- helpers ----------------------------------------------------------

    def _register_user(self, i: int) -> dict:
        """Register user i and return {token, user_id, headers} or {error}."""
        resp = self.client.post("/auth/register", json={
            "username": f"scale_user_{i}",
            "email": f"scale_{i}@test.com",
            "password": "Str0ngPass!",
            "display_name": f"Scale User {i}",
        })
        if resp.status_code == 201:
            data = resp.json()
            return {
                "token": data["token"],
                "user_id": data["user"]["id"],
                "headers": {"Authorization": f"Bearer {data['token']}"},
            }
        return {"error": f"Register user {i}: HTTP {resp.status_code} - {resp.text}"}

    def _user_session(self, i: int, user_info: dict) -> UserResult:
        """Run a realistic session for one user."""
        result = UserResult(user_id=i)
        headers = user_info["headers"]

        # 1. List members
        t0 = time.perf_counter()
        try:
            resp = self.client.get("/members", headers=headers)
            result.members_ok = resp.status_code == 200
            if not result.members_ok:
                result.errors.append(f"members: HTTP {resp.status_code}")
        except Exception as e:
            result.errors.append(f"members: {e}")
        result.latencies["members"] = time.perf_counter() - t0

        # 2. AI query
        t0 = time.perf_counter()
        try:
            resp = self.client.post("/query", headers=headers, json={
                "question": f"What is the team working on? (user {i})",
            })
            result.query_ok = resp.status_code == 200
            if not result.query_ok:
                result.errors.append(f"query: HTTP {resp.status_code}")
        except Exception as e:
            result.errors.append(f"query: {e}")
        result.latencies["query"] = time.perf_counter() - t0

        # 3. Create a room
        t0 = time.perf_counter()
        try:
            resp = self.client.post("/rooms", headers=headers, json={
                "name": f"Room by user {i}",
            })
            result.room_create_ok = resp.status_code in (200, 201)
            if result.room_create_ok:
                room_id = resp.json().get("id")
                # Send a message to the room
                if room_id:
                    msg_resp = self.client.post(
                        f"/rooms/{room_id}/messages",
                        headers=headers,
                        json={"content": f"Hello from user {i}!"},
                    )
                    result.room_message_ok = msg_resp.status_code == 200
                    if not result.room_message_ok:
                        result.errors.append(f"room_msg: HTTP {msg_resp.status_code}")
            else:
                result.errors.append(f"room_create: HTTP {resp.status_code}")
        except Exception as e:
            result.errors.append(f"room: {e}")
        result.latencies["room"] = time.perf_counter() - t0

        # 4. Create a discussion thread
        t0 = time.perf_counter()
        try:
            resp = self.client.post("/discussions", headers=headers, json={
                "title": f"Discussion by user {i}",
                "context_type": "member",
                "context_id": f"scale_user_{i}",
            })
            result.discussion_ok = resp.status_code in (200, 201)
            if not result.discussion_ok:
                result.errors.append(f"discussion: HTTP {resp.status_code}")
        except Exception as e:
            result.errors.append(f"discussion: {e}")
        result.latencies["discussion"] = time.perf_counter() - t0

        # 5. List conversations
        t0 = time.perf_counter()
        try:
            resp = self.client.get("/conversations", headers=headers)
            result.conversations_ok = resp.status_code == 200
            if not result.conversations_ok:
                result.errors.append(f"conversations: HTTP {resp.status_code}")
        except Exception as e:
            result.errors.append(f"conversations: {e}")
        result.latencies["conversations"] = time.perf_counter() - t0

        return result

    # -- main test --------------------------------------------------------

    def test_1000_users_full_session(self):
        """Register 1000 users in batches, then have each run a full session."""
        total_start = time.perf_counter()

        # Phase 1: Register 1000 users in batches
        print(f"\n{'='*60}")
        print(f"PHASE 1: Registering {NUM_USERS} users in batches of {BATCH_SIZE}")
        print(f"{'='*60}")

        registered_users = {}  # i -> user_info
        registration_errors = []
        reg_start = time.perf_counter()

        for batch_start in range(0, NUM_USERS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, NUM_USERS)
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(self._register_user, i): i
                    for i in range(batch_start, batch_end)
                }
                for future in concurrent.futures.as_completed(futures):
                    i = futures[future]
                    try:
                        info = future.result()
                        if "error" in info:
                            registration_errors.append(info["error"])
                        else:
                            registered_users[i] = info
                    except Exception as e:
                        registration_errors.append(f"User {i} exception: {e}")

            # Progress
            done = len(registered_users) + len(registration_errors)
            print(f"  Batch {batch_start}-{batch_end-1}: "
                  f"{len(registered_users)} registered, "
                  f"{len(registration_errors)} errors "
                  f"({done}/{NUM_USERS})")

        reg_elapsed = time.perf_counter() - reg_start
        print(f"\nRegistration complete: {len(registered_users)}/{NUM_USERS} "
              f"in {reg_elapsed:.1f}s")

        # Assert all registrations succeeded
        assert len(registration_errors) == 0, (
            f"{len(registration_errors)} registration errors:\n"
            + "\n".join(registration_errors[:20])  # Show first 20
        )
        assert len(registered_users) == NUM_USERS

        # Phase 2: Run user sessions in batches
        print(f"\n{'='*60}")
        print(f"PHASE 2: Running user sessions ({NUM_USERS} users)")
        print(f"{'='*60}")

        all_results = []
        session_start = time.perf_counter()

        user_items = list(registered_users.items())
        for batch_start in range(0, len(user_items), BATCH_SIZE):
            batch = user_items[batch_start:batch_start + BATCH_SIZE]
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(self._user_session, i, info): i
                    for i, info in batch
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        all_results.append(result)
                    except Exception as e:
                        r = UserResult(user_id=futures[future])
                        r.errors.append(f"Session exception: {e}")
                        all_results.append(r)

            done = len(all_results)
            if done % 200 == 0 or done == NUM_USERS:
                print(f"  Sessions completed: {done}/{NUM_USERS}")

        session_elapsed = time.perf_counter() - session_start
        total_elapsed = time.perf_counter() - total_start

        # Phase 3: Analyze results
        print(f"\n{'='*60}")
        print("PHASE 3: Results Analysis")
        print(f"{'='*60}")

        members_ok = sum(1 for r in all_results if r.members_ok)
        query_ok = sum(1 for r in all_results if r.query_ok)
        room_ok = sum(1 for r in all_results if r.room_create_ok)
        room_msg_ok = sum(1 for r in all_results if r.room_message_ok)
        disc_ok = sum(1 for r in all_results if r.discussion_ok)
        conv_ok = sum(1 for r in all_results if r.conversations_ok)

        print(f"\n  Registration:   {len(registered_users)}/{NUM_USERS} ({100*len(registered_users)/NUM_USERS:.1f}%)")
        print(f"  List Members:   {members_ok}/{NUM_USERS} ({100*members_ok/NUM_USERS:.1f}%)")
        print(f"  AI Query:       {query_ok}/{NUM_USERS} ({100*query_ok/NUM_USERS:.1f}%)")
        print(f"  Room Create:    {room_ok}/{NUM_USERS} ({100*room_ok/NUM_USERS:.1f}%)")
        print(f"  Room Message:   {room_msg_ok}/{NUM_USERS} ({100*room_msg_ok/NUM_USERS:.1f}%)")
        print(f"  Discussion:     {disc_ok}/{NUM_USERS} ({100*disc_ok/NUM_USERS:.1f}%)")
        print(f"  Conversations:  {conv_ok}/{NUM_USERS} ({100*conv_ok/NUM_USERS:.1f}%)")

        # Latency stats
        for op in ["members", "query", "room", "discussion", "conversations"]:
            lats = [r.latencies.get(op, 0) for r in all_results if op in r.latencies]
            if lats:
                print(f"\n  {op} latency:")
                print(f"    p50={statistics.median(lats):.3f}s  "
                      f"p95={sorted(lats)[int(len(lats)*0.95)]:.3f}s  "
                      f"p99={sorted(lats)[int(len(lats)*0.99)]:.3f}s  "
                      f"max={max(lats):.3f}s")

        # Collect all errors
        all_errors = []
        for r in all_results:
            for e in r.errors:
                all_errors.append(f"User {r.user_id}: {e}")

        print(f"\n  Total time:     {total_elapsed:.1f}s")
        print(f"  Registration:   {reg_elapsed:.1f}s")
        print(f"  Sessions:       {session_elapsed:.1f}s")
        print(f"  Total errors:   {len(all_errors)}")

        if all_errors:
            print("\n  Error details (first 30):")
            for e in all_errors[:30]:
                print(f"    - {e}")

        # FINAL ASSERTION: Zero errors
        assert len(all_errors) == 0, (
            f"\n{len(all_errors)} errors across {NUM_USERS} users:\n"
            + "\n".join(all_errors[:50])
        )

    def test_1000_users_data_integrity(self):
        """After 1000 registrations, verify data integrity via the API."""
        # Register 1000 users
        users = {}
        for batch_start in range(0, NUM_USERS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, NUM_USERS)
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(self._register_user, i): i
                    for i in range(batch_start, batch_end)
                }
                for future in concurrent.futures.as_completed(futures):
                    i = futures[future]
                    info = future.result()
                    if "error" not in info:
                        users[i] = info

        assert len(users) == NUM_USERS, f"Only {len(users)}/{NUM_USERS} registered"

        # Pick a sample of users and verify they can log in
        sample_indices = list(range(0, NUM_USERS, NUM_USERS // 20))  # 20 samples
        login_ok = 0
        login_errors = []
        for i in sample_indices:
            resp = self.client.post("/auth/login", json={
                "username": f"scale_user_{i}",
                "password": "Str0ngPass!",
            })
            if resp.status_code == 200:
                login_ok += 1
            else:
                login_errors.append(f"User {i}: HTTP {resp.status_code}")

        print(f"\nLogin verification: {login_ok}/{len(sample_indices)} succeeded")
        assert login_ok == len(sample_indices), (
            "Login failures:\n" + "\n".join(login_errors)
        )

        # Verify each user can see their own profile
        profile_ok = 0
        for i in sample_indices:
            resp = self.client.get("/auth/me", headers=users[i]["headers"])
            if resp.status_code == 200:
                data = resp.json()
                if data.get("username") == f"scale_user_{i}":
                    profile_ok += 1

        print(f"Profile verification: {profile_ok}/{len(sample_indices)} correct")
        assert profile_ok == len(sample_indices)

    def test_concurrent_reads_at_scale(self):
        """1000 concurrent read requests should all succeed."""
        # Register one user
        info = self._register_user(9999)
        assert "error" not in info, info.get("error")
        headers = info["headers"]

        errors = []

        def read_members(idx):
            resp = self.client.get("/members", headers=headers)
            if resp.status_code != 200:
                return f"Request {idx}: HTTP {resp.status_code}"
            return None

        # Fire 1000 concurrent reads in batches
        completed = 0
        for batch_start in range(0, NUM_USERS, BATCH_SIZE * 2):
            batch_end = min(batch_start + BATCH_SIZE * 2, NUM_USERS)
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = [pool.submit(read_members, i) for i in range(batch_start, batch_end)]
                for f in concurrent.futures.as_completed(futures):
                    err = f.result()
                    if err:
                        errors.append(err)
                    completed += 1

        print(f"\nConcurrent reads: {completed - len(errors)}/{completed} succeeded")
        assert len(errors) == 0, (
            f"{len(errors)} read failures:\n" + "\n".join(errors[:20])
        )

    def test_cross_user_isolation_at_scale(self):
        """Each user should only see their own conversations, not others'."""
        # Register 100 users and have each create a conversation
        subset = 100
        users = {}
        for i in range(subset):
            info = self._register_user(i + 10000)  # Offset to avoid collision
            if "error" not in info:
                users[i] = info

        assert len(users) == subset

        # Each user creates a query (which creates a conversation)
        conversation_ids = {}
        for i, info in users.items():
            resp = self.client.post("/query", headers=info["headers"], json={
                "question": f"Private question from user {i}",
            })
            if resp.status_code == 200:
                conv_id = resp.json().get("conversation_id")
                if conv_id:
                    conversation_ids[i] = conv_id

        # Verify each user only sees their own conversations
        isolation_errors = []
        for i, info in list(users.items())[:20]:  # Sample 20
            resp = self.client.get("/conversations", headers=info["headers"])
            if resp.status_code == 200:
                data = resp.json()
                convs = data.get("conversations", data.get("items", []))
                # All conversations should belong to this user
                for conv in convs:
                    owner = conv.get("user_id") or conv.get("owner_id")
                    if owner and owner != info["user_id"]:
                        isolation_errors.append(
                            f"User {i} sees conversation owned by {owner}"
                        )

        print(f"\nIsolation check: {len(isolation_errors)} violations")
        assert len(isolation_errors) == 0, (
            "Data isolation failures:\n" + "\n".join(isolation_errors)
        )
