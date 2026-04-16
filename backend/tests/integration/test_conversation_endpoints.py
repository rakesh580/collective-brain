"""Integration tests for conversation endpoints — CRUD, sharing, access control."""


class TestConversationCRUD:
    def test_list_conversations_empty(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/conversations", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_conversation_not_found(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/conversations/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestConversationSharing:
    def test_share_conversation(self, app_client, auth_headers, registered_user, second_user):
        # Create a conversation by querying
        resp = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={"question": "test question"},
        )
        assert resp.status_code == 200
        conv_id = resp.json()["conversation_id"]

        # Share with bob
        bob_user_id = second_user["user"].get("id", "")
        resp = app_client.post(
            f"/api/v1/conversations/{conv_id}/share",
            headers=auth_headers,
            json={"user_ids": [bob_user_id]},
        )
        assert resp.status_code == 200

        # Bob should now be able to access it
        resp = app_client.get(f"/api/v1/conversations/{conv_id}", headers=second_user["headers"])
        assert resp.status_code == 200

    def test_share_nonexistent_conversation(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/conversations/fake-id/share",
            headers=auth_headers,
            json={"user_ids": ["some-user"]},
        )
        assert resp.status_code == 404


class TestConversationAccessControl:
    def test_cannot_access_others_private_conversation(self, app_client, auth_headers, second_user):
        resp = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={"question": "private question"},
        )
        conv_id = resp.json()["conversation_id"]

        resp = app_client.get(f"/api/v1/conversations/{conv_id}", headers=second_user["headers"])
        assert resp.status_code == 403

    def test_cannot_delete_others_conversation(self, app_client, auth_headers, second_user):
        resp = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={"question": "my conversation"},
        )
        conv_id = resp.json()["conversation_id"]

        resp = app_client.delete(f"/api/v1/conversations/{conv_id}", headers=second_user["headers"])
        assert resp.status_code == 403


class TestParticipantEndpoint:
    def test_list_participants_requires_access(self, app_client, auth_headers, second_user):
        resp = app_client.post(
            "/api/v1/query",
            headers=auth_headers,
            json={"question": "private conv"},
        )
        conv_id = resp.json()["conversation_id"]

        resp = app_client.get(f"/api/v1/conversations/{conv_id}/participants", headers=second_user["headers"])
        assert resp.status_code == 403
