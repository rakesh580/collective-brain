"""Integration tests for Google OAuth and password reset endpoints."""

from unittest.mock import patch


class TestGoogleAuthEndpoint:
    def test_google_not_configured_returns_501(self, app_client):
        resp = app_client.post("/api/v1/auth/google", json={"credential": "fake-token"})
        assert resp.status_code == 501
        assert "not configured" in resp.json()["detail"]

    def test_google_auth_invalid_token(self, app_client):
        from app.main import app

        app.state.settings.google_client_id = "test-client-id"
        try:
            with patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify:
                mock_verify.side_effect = ValueError("bad token")
                resp = app_client.post("/api/v1/auth/google", json={"credential": "bad"})
                assert resp.status_code == 401
        finally:
            app.state.settings.google_client_id = ""

    def test_google_auth_creates_user(self, app_client):
        from app.main import app

        app.state.settings.google_client_id = "test-client-id"
        try:
            with patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify:
                mock_verify.return_value = {
                    "sub": "goog-999",
                    "email": "newuser@gmail.com",
                    "email_verified": True,
                    "name": "New User",
                    "picture": None,
                }
                resp = app_client.post("/api/v1/auth/google", json={"credential": "good-token"})
                assert resp.status_code == 200
                data = resp.json()
                assert "token" in data
                assert data["user"]["email"] == "newuser@gmail.com"
                assert data["user"]["auth_provider"] == "google"
        finally:
            app.state.settings.google_client_id = ""


class TestLoginErrors:
    def test_login_no_account(self, app_client):
        resp = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "anything",
            },
        )
        assert resp.status_code == 401
        assert "No account found" in resp.json()["detail"]

    def test_login_wrong_password(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "WrongPassword!",
            },
        )
        assert resp.status_code == 401
        assert "Incorrect password" in resp.json()["detail"]

    def test_login_correct_password(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "Str0ngPass!",
            },
        )
        assert resp.status_code == 200
        assert "token" in resp.json()


class TestForgotPasswordEndpoint:
    def test_forgot_password_flow(self, app_client, auth_headers):
        # Step 1: Request reset code
        resp = app_client.post(
            "/api/v1/auth/forgot-password",
            json={
                "email": "alice@test.com",
            },
        )
        assert resp.status_code == 200
        code = resp.json()["code"]
        assert len(code) == 6

        # Step 2: Reset password with code
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": "alice@test.com",
                "code": code,
                "new_password": "NewSecure123!",
            },
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

        # Step 3: Login with new password works
        resp = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "NewSecure123!",
            },
        )
        assert resp.status_code == 200

        # Step 4: Old password fails
        resp = app_client.post(
            "/api/v1/auth/login",
            json={
                "username": "alice",
                "password": "Str0ngPass!",
            },
        )
        assert resp.status_code == 401

    def test_forgot_password_no_account(self, app_client):
        resp = app_client.post(
            "/api/v1/auth/forgot-password",
            json={
                "email": "nobody@test.com",
            },
        )
        assert resp.status_code == 400
        assert "No account found" in resp.json()["detail"]

    def test_reset_wrong_code(self, app_client, auth_headers):
        # Request code
        app_client.post("/api/v1/auth/forgot-password", json={"email": "alice@test.com"})
        # Use wrong code
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": "alice@test.com",
                "code": "000000",
                "new_password": "NewPass123!",
            },
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]
