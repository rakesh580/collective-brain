"""Integration tests for auth API endpoints using FastAPI TestClient."""


class TestRegistration:
    def test_register_success(self, app_client):
        resp = app_client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@test.com",
                "password": "StrongP@ss1",
                "display_name": "New User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert data["user"]["username"] == "newuser"

    def test_register_duplicate_username(self, app_client, registered_user):
        resp = app_client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "different@test.com",
                "password": "StrongP@ss1",
            },
        )
        assert resp.status_code == 409

    def test_register_invalid_email(self, app_client):
        resp = app_client.post(
            "/auth/register",
            json={
                "username": "badmail",
                "email": "not-an-email",
                "password": "StrongP@ss1",
            },
        )
        assert resp.status_code == 422  # Pydantic EmailStr validation

    def test_register_short_password(self, app_client):
        resp = app_client.post(
            "/auth/register",
            json={
                "username": "shortpw",
                "email": "short@test.com",
                "password": "abc",
            },
        )
        assert resp.status_code == 422

    def test_register_short_username(self, app_client):
        resp = app_client.post(
            "/auth/register",
            json={
                "username": "ab",
                "email": "ab@test.com",
                "password": "StrongP@ss1",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, app_client, registered_user):
        resp = app_client.post(
            "/auth/login",
            json={
                "username": "alice",
                "password": "Str0ngPass!",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["username"] == "alice"

    def test_login_wrong_password(self, app_client, registered_user):
        resp = app_client.post(
            "/auth/login",
            json={
                "username": "alice",
                "password": "wrongpass",
            },
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, app_client):
        resp = app_client.post(
            "/auth/login",
            json={
                "username": "nobody",
                "password": "password",
            },
        )
        assert resp.status_code == 401


class TestProfile:
    def test_get_profile(self, app_client, auth_headers):
        resp = app_client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "alice"

    def test_get_profile_no_auth(self, app_client):
        resp = app_client.get("/auth/me")
        assert resp.status_code == 401

    def test_get_profile_bad_token(self, app_client):
        resp = app_client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_update_profile(self, app_client, auth_headers):
        resp = app_client.put(
            "/auth/me",
            headers=auth_headers,
            json={
                "display_name": "Alice Updated",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Alice Updated"

    def test_list_users(self, app_client, auth_headers):
        resp = app_client.get("/auth/users", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1
