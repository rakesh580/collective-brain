"""Integration tests for the AI query endpoint."""



class TestQueryEndpoint:
    def test_query_creates_conversation(self, app_client, auth_headers):
        resp = app_client.post("/query", headers=auth_headers, json={
            "question": "Who is the best Python developer?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "conversation_id" in data
        assert data["conversation_id"] is not None

    def test_query_continues_conversation(self, app_client, auth_headers):
        # First query creates a conversation
        resp1 = app_client.post("/query", headers=auth_headers, json={
            "question": "Tell me about the team",
        })
        conv_id = resp1.json()["conversation_id"]

        # Second query in same conversation
        resp2 = app_client.post("/query", headers=auth_headers, json={
            "question": "Who contributes the most?",
            "conversation_id": conv_id,
        })
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id

    def test_query_requires_auth(self, app_client):
        resp = app_client.post("/query", json={"question": "test"})
        assert resp.status_code == 401

    def test_query_empty_question(self, app_client, auth_headers):
        resp = app_client.post("/query", headers=auth_headers, json={"question": ""})
        assert resp.status_code == 422

    def test_query_with_filters(self, app_client, auth_headers):
        resp = app_client.post("/query", headers=auth_headers, json={
            "question": "What has Alice done?",
            "filters": {"members": ["alice"]},
        })
        assert resp.status_code == 200
        assert "answer" in resp.json()

    def test_query_returns_sources(self, app_client, auth_headers):
        resp = app_client.post("/query", headers=auth_headers, json={
            "question": "What projects are active?",
        })
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)
