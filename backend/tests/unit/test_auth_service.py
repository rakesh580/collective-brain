"""Unit tests for AuthService — JWT, password hashing, registration, authentication."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from jose import jwt


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt(self, auth_service):
        hashed = auth_service.hash_password("mypassword")
        assert hashed.startswith("$2b$")
        assert hashed != "mypassword"

    def test_verify_correct_password(self, auth_service):
        hashed = auth_service.hash_password("correct")
        assert auth_service.verify_password("correct", hashed) is True

    def test_verify_wrong_password(self, auth_service):
        hashed = auth_service.hash_password("correct")
        assert auth_service.verify_password("wrong", hashed) is False

    def test_different_passwords_produce_different_hashes(self, auth_service):
        h1 = auth_service.hash_password("password1")
        h2 = auth_service.hash_password("password2")
        assert h1 != h2

    def test_same_password_produces_different_hashes(self, auth_service):
        """bcrypt salting ensures different hashes each time."""
        h1 = auth_service.hash_password("same")
        h2 = auth_service.hash_password("same")
        assert h1 != h2


class TestJWTTokens:
    def test_create_token_returns_string(self, auth_service):
        token = auth_service.create_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self, auth_service):
        token = auth_service.create_token("user-123")
        user_id = auth_service.decode_token(token)
        assert user_id == "user-123"

    def test_decode_token_with_wrong_secret(self, auth_service):
        token = auth_service.create_token("user-123")
        # Tamper by decoding with wrong secret
        from app.services.auth_service import AuthService
        from app.config import Settings

        other = AuthService(Settings(jwt_secret="different-secret"))
        assert other.decode_token(token) is None

    def test_decode_expired_token(self, settings):
        """Token with 0 expiry minutes should expire immediately."""
        from app.services.auth_service import AuthService

        settings.jwt_expire_minutes = 0
        svc = AuthService(settings)
        token = svc.create_token("user-123")
        # The token's exp is set to now + 0 minutes = now, should be expired
        time.sleep(1)
        assert svc.decode_token(token) is None

    def test_decode_garbage_token(self, auth_service):
        assert auth_service.decode_token("not.a.jwt") is None

    def test_decode_empty_token(self, auth_service):
        assert auth_service.decode_token("") is None

    def test_token_contains_sub_claim(self, auth_service):
        token = auth_service.create_token("user-xyz")
        payload = jwt.decode(
            token, auth_service.secret, algorithms=[auth_service.algorithm]
        )
        assert payload["sub"] == "user-xyz"
        assert "exp" in payload


class TestRegistration:
    def test_register_creates_user(self, db_session, auth_service):
        user = auth_service.register(db_session, "newuser", "new@test.com", "Pass123!")
        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@test.com"
        assert user.is_active is True
        assert user.password_hash != "Pass123!"

    def test_register_with_display_name(self, db_session, auth_service):
        user = auth_service.register(
            db_session, "newuser", "new@test.com", "Pass123!", "Display Name"
        )
        assert user.display_name == "Display Name"

    def test_register_defaults_display_name_to_username(self, db_session, auth_service):
        user = auth_service.register(db_session, "newuser", "new@test.com", "Pass123!")
        assert user.display_name == "newuser"

    def test_register_duplicate_username_raises(self, db_session, auth_service):
        auth_service.register(db_session, "taken", "a@test.com", "Pass123!")
        with pytest.raises(ValueError, match="Username already taken"):
            auth_service.register(db_session, "taken", "b@test.com", "Pass123!")

    def test_register_duplicate_email_raises(self, db_session, auth_service):
        auth_service.register(db_session, "user1", "dup@test.com", "Pass123!")
        with pytest.raises(ValueError, match="Email already registered"):
            auth_service.register(db_session, "user2", "dup@test.com", "Pass123!")

    def test_register_sets_created_at(self, db_session, auth_service):
        user = auth_service.register(db_session, "newuser", "n@test.com", "Pass123!")
        assert user.created_at is not None
        assert (datetime.now(timezone.utc) - user.created_at).total_seconds() < 5


class TestAuthentication:
    def test_authenticate_valid_credentials(self, db_session, auth_service):
        auth_service.register(db_session, "alice", "alice@test.com", "MyPass123!")
        user = auth_service.authenticate(db_session, "alice", "MyPass123!")
        assert user is not None
        assert user.username == "alice"

    def test_authenticate_with_email(self, db_session, auth_service):
        auth_service.register(db_session, "alice", "alice@test.com", "MyPass123!")
        user = auth_service.authenticate(db_session, "alice@test.com", "MyPass123!")
        assert user is not None

    def test_authenticate_wrong_password(self, db_session, auth_service):
        auth_service.register(db_session, "alice", "alice@test.com", "MyPass123!")
        with pytest.raises(ValueError, match="Incorrect password"):
            auth_service.authenticate(db_session, "alice", "wrongpass")

    def test_authenticate_nonexistent_user(self, db_session, auth_service):
        with pytest.raises(ValueError, match="No account found"):
            auth_service.authenticate(db_session, "nobody", "pass")

    def test_authenticate_inactive_user(self, db_session, auth_service):
        user = auth_service.register(db_session, "alice", "a@test.com", "Pass123!")
        user.is_active = False
        db_session.commit()
        with pytest.raises(ValueError, match="deactivated"):
            auth_service.authenticate(db_session, "alice", "Pass123!")

    def test_authenticate_updates_last_login(self, db_session, auth_service):
        auth_service.register(db_session, "alice", "a@test.com", "Pass123!")
        user = auth_service.authenticate(db_session, "alice", "Pass123!")
        assert user.last_login is not None
