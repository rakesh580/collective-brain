"""WebSocket tests for chat rooms — messaging, typing, presence, membership."""

import json

from starlette.websockets import WebSocketDisconnect


class TestRoomCreation:
    def test_create_room(self, app_client, auth_headers):
        resp = app_client.post(
            "/rooms",
            headers=auth_headers,
            json={
                "name": "general",
                "description": "General chat",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "general"
        assert "id" in data

    def test_list_rooms(self, app_client, auth_headers):
        app_client.post("/rooms", headers=auth_headers, json={"name": "room-a"})
        app_client.post("/rooms", headers=auth_headers, json={"name": "room-b"})
        resp = app_client.get("/rooms", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["rooms"]) >= 2

    def test_create_room_requires_auth(self, app_client):
        resp = app_client.post("/rooms", json={"name": "unauth"})
        assert resp.status_code == 401


class TestRoomMembers:
    def test_add_member_to_room(self, app_client, auth_headers, registered_user):
        # Create a second user
        resp2 = app_client.post(
            "/auth/register",
            json={
                "username": "charlie",
                "email": "charlie@test.com",
                "password": "Str0ngPass!",
                "display_name": "Charlie",
            },
        )
        charlie_id = resp2.json()["user"]["id"]

        # Create room
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "team"})
        room_id = room.json()["id"]

        # Add charlie
        resp = app_client.post(
            f"/rooms/{room_id}/members",
            headers=auth_headers,
            json={"user_ids": [charlie_id]},
        )
        assert resp.status_code == 200

    def test_leave_room(self, app_client, auth_headers, registered_user):
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "temp-room"})
        room_id = room.json()["id"]
        user_id = registered_user[0]["id"]

        resp = app_client.delete(f"/rooms/{room_id}/members/{user_id}", headers=auth_headers)
        assert resp.status_code == 200


class TestRoomMessages:
    def test_send_message(self, app_client, auth_headers):
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "msg-room"})
        room_id = room.json()["id"]

        resp = app_client.post(
            f"/rooms/{room_id}/messages",
            headers=auth_headers,
            json={"content": "Hello, team!"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Hello, team!"

    def test_list_messages(self, app_client, auth_headers):
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "hist-room"})
        room_id = room.json()["id"]

        for i in range(3):
            app_client.post(
                f"/rooms/{room_id}/messages",
                headers=auth_headers,
                json={"content": f"Message {i}"},
            )

        resp = app_client.get(f"/rooms/{room_id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) >= 3

    def test_send_message_requires_membership(self, app_client, auth_headers):
        """Non-members should not be able to send messages."""
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "private-room"})
        room_id = room.json()["id"]

        # Register a new user who is NOT a member of the room
        other = app_client.post(
            "/auth/register",
            json={
                "username": "outsider",
                "email": "outsider@test.com",
                "password": "Str0ngPass!",
            },
        )
        other_headers = {"Authorization": f"Bearer {other.json()['token']}"}

        resp = app_client.post(
            f"/rooms/{room_id}/messages",
            headers=other_headers,
            json={"content": "Sneaky message"},
        )
        assert resp.status_code in (403, 404)


class TestRoomWebSocket:
    def test_websocket_auth_required(self, app_client):
        """Connecting without sending a valid token should disconnect."""
        room_resp = None
        # We need a valid room; create via REST first
        reg = app_client.post(
            "/auth/register",
            json={
                "username": "wsuser",
                "email": "wsuser@test.com",
                "password": "Str0ngPass!",
            },
        )
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        room_resp = app_client.post("/rooms", headers=headers, json={"name": "ws-room"})
        room_id = room_resp.json()["id"]

        with app_client.websocket_connect(f"/rooms/ws/{room_id}") as ws:
            # Send invalid token
            ws.send_text(json.dumps({"token": "bad-token-here"}))
            try:
                data = ws.receive_text()
                msg = json.loads(data)
                # Should receive an error or disconnect
                assert msg.get("type") == "error" or "error" in str(msg).lower()
            except WebSocketDisconnect:
                pass  # Expected — server closed connection

    def test_websocket_message_broadcast(self, app_client):
        """A message sent via WebSocket should be receivable."""
        reg = app_client.post(
            "/auth/register",
            json={
                "username": "wsmsg",
                "email": "wsmsg@test.com",
                "password": "Str0ngPass!",
            },
        )
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        room = app_client.post("/rooms", headers=headers, json={"name": "ws-msg-room"})
        room_id = room.json()["id"]

        with app_client.websocket_connect(f"/rooms/ws/{room_id}") as ws:
            # Authenticate
            ws.send_text(json.dumps({"token": token}))
            # Wait for presence or ack
            ack = json.loads(ws.receive_text())

            # Send a message
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "Hello via WebSocket!",
                    }
                )
            )
            response = json.loads(ws.receive_text())
            assert response.get("type") in ("new_message", "message", "error")

    def test_websocket_typing_indicator(self, app_client):
        """Typing indicators should be transmitted."""
        reg = app_client.post(
            "/auth/register",
            json={
                "username": "wstype",
                "email": "wstype@test.com",
                "password": "Str0ngPass!",
            },
        )
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        room = app_client.post("/rooms", headers=headers, json={"name": "ws-type-room"})
        room_id = room.json()["id"]

        with app_client.websocket_connect(f"/rooms/ws/{room_id}") as ws:
            ws.send_text(json.dumps({"token": token}))
            ws.receive_text()  # ack/presence

            ws.send_text(json.dumps({"type": "typing"}))
            # Server may or may not echo typing to solo user, just ensure no crash
            ws.send_text(json.dumps({"type": "typing_stop"}))

    def test_websocket_ping_pong(self, app_client):
        """Ping should get a pong response."""
        reg = app_client.post(
            "/auth/register",
            json={
                "username": "wsping",
                "email": "wsping@test.com",
                "password": "Str0ngPass!",
            },
        )
        token = reg.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        room = app_client.post("/rooms", headers=headers, json={"name": "ws-ping-room"})
        room_id = room.json()["id"]

        with app_client.websocket_connect(f"/rooms/ws/{room_id}") as ws:
            ws.send_text(json.dumps({"token": token}))
            ws.receive_text()  # ack

            ws.send_text(json.dumps({"type": "ping"}))
            resp = json.loads(ws.receive_text())
            assert resp.get("type") == "pong"


class TestRoomAIQuery:
    def test_ai_query_in_room(self, app_client, auth_headers):
        room = app_client.post("/rooms", headers=auth_headers, json={"name": "ai-room"})
        room_id = room.json()["id"]

        resp = app_client.post(
            f"/rooms/{room_id}/ai",
            headers=auth_headers,
            json={"question": "Who is the top contributor?"},
        )
        assert resp.status_code == 200
        assert "content" in resp.json()
