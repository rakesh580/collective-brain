"""WebSocket tests for discussion threads."""

import json

import pytest
from starlette.websockets import WebSocketDisconnect


class TestDiscussionCRUD:
    def test_create_thread(self, app_client, auth_headers):
        resp = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Architecture Discussion",
            "context_type": "member",
            "context_id": "test-member",
        })
        assert resp.status_code in (200, 201)
        assert resp.json()["title"] == "Architecture Discussion"

    def test_list_threads(self, app_client, auth_headers):
        app_client.post("/discussions", headers=auth_headers, json={
            "title": "Thread 1", "context_type": "member", "context_id": "test-member",
        })
        app_client.post("/discussions", headers=auth_headers, json={
            "title": "Thread 2", "context_type": "member", "context_id": "test-member",
        })
        resp = app_client.get("/discussions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    def test_get_thread_detail(self, app_client, auth_headers):
        create = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Detail Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = create.json()["id"]
        resp = app_client.get(f"/discussions/{thread_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Detail Thread"


class TestDiscussionMessages:
    def test_post_message(self, app_client, auth_headers):
        thread = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Msg Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]
        resp = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "This is my take on the architecture."},
        )
        assert resp.status_code == 200

    def test_edit_own_message(self, app_client, auth_headers):
        thread = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Edit Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]
        msg = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "Original content"},
        )
        msg_id = msg.json()["id"]

        resp = app_client.put(
            f"/discussions/{thread_id}/messages/{msg_id}",
            headers=auth_headers,
            json={"content": "Updated content"},
        )
        assert resp.status_code == 200

    def test_delete_own_message(self, app_client, auth_headers):
        thread = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Del Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]
        msg = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "To be deleted"},
        )
        msg_id = msg.json()["id"]

        resp = app_client.delete(
            f"/discussions/{thread_id}/messages/{msg_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_cannot_edit_others_message(self, app_client, auth_headers):
        """Another user should not be able to edit someone else's message."""
        thread = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Access Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]
        msg = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "Alice's message"},
        )
        msg_id = msg.json()["id"]

        # Register another user
        bob = app_client.post("/auth/register", json={
            "username": "disc_bob",
            "email": "disc_bob@test.com",
            "password": "Str0ngPass!",
        })
        bob_headers = {"Authorization": f"Bearer {bob.json()['token']}"}

        resp = app_client.put(
            f"/discussions/{thread_id}/messages/{msg_id}",
            headers=bob_headers,
            json={"content": "Hijacked!"},
        )
        assert resp.status_code == 403

    def test_threaded_reply(self, app_client, auth_headers):
        """Messages can reply to parent messages."""
        thread = app_client.post("/discussions", headers=auth_headers, json={
            "title": "Reply Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]
        parent = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "Parent message"},
        )
        parent_id = parent.json()["id"]

        reply = app_client.post(
            f"/discussions/{thread_id}/messages",
            headers=auth_headers,
            json={"content": "Reply to parent", "parent_message_id": parent_id},
        )
        assert reply.status_code == 200


class TestDiscussionWebSocket:
    def test_ws_auth_and_disconnect(self, app_client):
        """WebSocket requires valid token."""
        reg = app_client.post("/auth/register", json={
            "username": "dws_user",
            "email": "dws@test.com",
            "password": "Str0ngPass!",
        })
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        thread = app_client.post("/discussions", headers=headers, json={
            "title": "WS Thread", "context_type": "member", "context_id": "test-member",
        })
        thread_id = thread.json()["id"]

        with app_client.websocket_connect(f"/discussions/ws/{thread_id}") as ws:
            ws.send_text(json.dumps({"token": "invalid-token"}))
            try:
                data = json.loads(ws.receive_text())
                assert data.get("type") == "error" or "error" in str(data).lower()
            except WebSocketDisconnect:
                pass  # Expected


class TestDiscussionAuth:
    def test_discussions_require_auth(self, app_client):
        resp = app_client.get("/discussions")
        assert resp.status_code == 401

    def test_create_thread_requires_auth(self, app_client):
        resp = app_client.post("/discussions", json={
            "title": "No Auth", "context_type": "member", "context_id": "test-member",
        })
        assert resp.status_code == 401
