from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from jose import jwt

from app.models.user import UserRecord
from app.services.auth_service import AuthService


class TestHashPassword:
    def test_hash_password_returns_hash(self, settings):
        service = AuthService(settings)
        hashed = service.hash_password("MyPassword123")
        assert hashed != "MyPassword123"
        assert hashed.startswith("$2b$")  # bcrypt prefix


class TestVerifyPassword:
    def test_verify_password_correct(self, settings):
        service = AuthService(settings)
        hashed = service.hash_password("MyPassword123")
        assert service.verify_password("MyPassword123", hashed) is True

    def test_verify_password_incorrect(self, settings):
        service = AuthService(settings)
        hashed = service.hash_password("MyPassword123")
        assert service.verify_password("WrongPassword", hashed) is False


class TestCreateToken:
    def test_create_token_returns_string(self, settings):
        service = AuthService(settings)
        token = service.create_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token contents
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"


class TestDecodeToken:
    def test_decode_token_valid(self, settings):
        service = AuthService(settings)
        token = service.create_token("user-456")
        result = service.decode_token(token)
        assert result == "user-456"

    def test_decode_token_expired(self, settings):
        service = AuthService(settings)
        # Manually create an expired token
        expire = datetime.now(UTC) - timedelta(minutes=5)
        payload = {"sub": "user-789", "type": "access", "exp": expire}
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        result = service.decode_token(token)
        assert result is None

    def test_decode_token_rejects_refresh(self, settings):
        service = AuthService(settings)
        refresh_token = service.create_refresh_token("user-111")
        result = service.decode_token(refresh_token)
        assert result is None


class TestRefreshToken:
    def test_create_refresh_token(self, settings):
        service = AuthService(settings)
        token = service.create_refresh_token("user-222")
        assert isinstance(token, str)

        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user-222"
        assert payload["type"] == "refresh"

    def test_refresh_access_token_valid(self, settings):
        service = AuthService(settings)
        refresh_token = service.create_refresh_token("user-333")
        result = service.refresh_access_token(refresh_token)
        assert result is not None
        new_access, new_refresh = result
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)

        # The new access token should decode to the same user
        user_id = service.decode_token(new_access)
        assert user_id == "user-333"

    def test_refresh_access_token_invalid(self, settings):
        service = AuthService(settings)
        result = service.refresh_access_token("totally-invalid-token")
        assert result is None

    def test_refresh_access_token_rejects_access_token(self, settings):
        """refresh_access_token should reject an access token (type != refresh)."""
        service = AuthService(settings)
        access_token = service.create_token("user-444")
        result = service.refresh_access_token(access_token)
        assert result is None


class TestRegister:
    def test_register_success(self, settings, mock_db):
        service = AuthService(settings)

        # Make db.query(...).filter(...).first() return None (no existing user)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        user = service.register(
            mock_db,
            username="newuser",
            email="new@example.com",
            password="StrongPass1",
            display_name="New User",
        )

        assert isinstance(user, UserRecord)
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert user.auth_provider == "local"
        assert user.is_active is True
        # Password should be hashed, not plain
        assert user.password_hash != "StrongPass1"
        mock_db.add.assert_called_once_with(user)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(user)

    def test_register_duplicate_username(self, settings, mock_db):
        service = AuthService(settings)

        # First query (username check) returns an existing user
        existing_user = MagicMock(spec=UserRecord)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        with pytest.raises(ValueError, match="Username already taken"):
            service.register(
                mock_db,
                username="taken",
                email="new@example.com",
                password="StrongPass1",
            )


class TestAuthenticate:
    def test_authenticate_success(self, settings, mock_db):
        service = AuthService(settings)

        fake_user = MagicMock(spec=UserRecord)
        fake_user.is_active = True
        fake_user.password_hash = service.hash_password("CorrectPass1")

        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        result = service.authenticate(mock_db, "testuser", "CorrectPass1")
        assert result is fake_user
        mock_db.commit.assert_called_once()

    def test_authenticate_wrong_password(self, settings, mock_db):
        service = AuthService(settings)

        fake_user = MagicMock(spec=UserRecord)
        fake_user.is_active = True
        fake_user.password_hash = service.hash_password("CorrectPass1")

        mock_db.query.return_value.filter.return_value.first.return_value = fake_user

        with pytest.raises(ValueError, match="Invalid credentials"):
            service.authenticate(mock_db, "testuser", "WrongPassword")
