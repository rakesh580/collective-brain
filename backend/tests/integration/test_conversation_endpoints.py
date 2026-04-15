"""Integration tests for conversation endpoints — CRUD, sharing, access control."""

import pytest


@pytest.fixture()
def second_user(app_client):
    resp = app_client.post(
        "/auth/register",
        json={
            "username": "bob",
            "email": "bob@test.com",
            "password": "Str0ngPass!",
            "display_name": "Bob",
        },
    )
    data = resp.json()
    return data["user"], data["token"]


class TestConversationCRUD:
    def test_list_conversations_empty(self, app_client, auth_headers):
        resp = app_client.get("/conversations", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_conversation_not_found(self, app_client, auth_headers):
        resp = app_client.get("/conversations/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestConversationSharing:
    def test_share_conversation(self, app_client, auth_headers, registered_user, second_user):
        user, token = registered_user
        bob_user, bob_token = second_user

        # Create a conversation by querying (mocked LLM)
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={"question": "test question"},
        )
        assert resp.status_code == 200
        conv_id = resp.json()["conversation_id"]

        # Share with bob
        resp = app_client.post(
            f"/conversations/{conv_id}/share",
            headers=auth_headers,
            json={"user_ids": [bob_user["id"]]},
        )
        assert resp.status_code == 200

        # Bob should now be able to access it
        bob_headers = {"Authorization": f"Bearer {bob_token}"}
        resp = app_client.get(f"/conversations/{conv_id}", headers=bob_headers)
        assert resp.status_code == 200

    def test_share_nonexistent_conversation(self, app_client, auth_headers):
        resp = app_client.post(
            "/conversations/fake-id/share",
            headers=auth_headers,
            json={"user_ids": ["some-user"]},
        )
        assert resp.status_code == 404


class TestConversationAccessControl:
    def test_cannot_access_others_private_conversation(self, app_client, auth_headers, second_user):
        # Alice creates a conversation
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={"question": "private question"},
        )
        conv_id = resp.json()["conversation_id"]

        # Bob tries to access it
        bob_headers = {"Authorization": f"Bearer {second_user[1]}"}
        resp = app_client.get(f"/conversations/{conv_id}", headers=bob_headers)
        assert resp.status_code == 403

    def test_cannot_delete_others_conversation(self, app_client, auth_headers, second_user):
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={"question": "my conversation"},
        )
        conv_id = resp.json()["conversation_id"]

        bob_headers = {"Authorization": f"Bearer {second_user[1]}"}
        resp = app_client.delete(f"/conversations/{conv_id}", headers=bob_headers)
        assert resp.status_code == 403


class TestParticipantEndpoint:
    def test_list_participants_requires_access(self, app_client, auth_headers, second_user):
        resp = app_client.post(
            "/query",
            headers=auth_headers,
            json={"question": "private conv"},
        )
        conv_id = resp.json()["conversation_id"]

        bob_headers = {"Authorization": f"Bearer {second_user[1]}"}
        resp = app_client.get(f"/conversations/{conv_id}/participants", headers=bob_headers)
        assert resp.status_code == 403
