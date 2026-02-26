"""Unit tests for Google OAuth and password reset in AuthService."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app.services.auth_service import AuthService
from app.models.user import UserRecord


class TestGoogleAuthenticate:
    """Test AuthService.google_authenticate with mocked Google verification."""

    def _mock_idinfo(self, sub="google-123", email="alice@gmail.com", name="Alice", picture=None, verified=True):
        return {
            "sub": sub,
            "email": email,
            "email_verified": verified,
            "name": name,
            "picture": picture,
        }

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_new_user_created(self, mock_verify, db_session, settings):
        mock_verify.return_value = self._mock_idinfo()
        svc = AuthService(settings)
        user = svc.google_authenticate(db_session, "fake-token", "test-client-id")
        assert user.email == "alice@gmail.com"
        assert user.google_id == "google-123"
        assert user.auth_provider == "google"
        assert user.password_hash is None
        assert user.display_name == "Alice"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_returning_google_user(self, mock_verify, db_session, settings):
        mock_verify.return_value = self._mock_idinfo()
        svc = AuthService(settings)
        user1 = svc.google_authenticate(db_session, "fake-token", "test-client-id")
        user2 = svc.google_authenticate(db_session, "fake-token", "test-client-id")
        assert user1.id == user2.id
        assert user2.last_login is not None

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_email_match_links_account(self, mock_verify, db_session, settings):
        svc = AuthService(settings)
        existing = svc.register(db_session, "alice", "alice@gmail.com", "Str0ngPass!")
        assert existing.auth_provider == "local"
        mock_verify.return_value = self._mock_idinfo()
        user = svc.google_authenticate(db_session, "fake-token", "test-client-id")
        assert user.id == existing.id
        assert user.google_id == "google-123"
        assert user.auth_provider == "google+local"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_invalid_token(self, mock_verify, db_session, settings):
        mock_verify.side_effect = ValueError("bad token")
        svc = AuthService(settings)
        with pytest.raises(ValueError, match="Invalid Google token"):
            svc.google_authenticate(db_session, "bad-token", "test-client-id")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_unverified_email(self, mock_verify, db_session, settings):
        mock_verify.return_value = self._mock_idinfo(verified=False)
        svc = AuthService(settings)
        with pytest.raises(ValueError, match="not verified"):
            svc.google_authenticate(db_session, "fake-token", "test-client-id")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_username_collision(self, mock_verify, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alicegmail", "other@test.com", "Str0ngPass!")
        mock_verify.return_value = self._mock_idinfo(email="alice.gmail@gmail.com")
        user = svc.google_authenticate(db_session, "fake-token", "test-client-id")
        assert user.username.startswith("alicegmail")
        assert user.username != "alicegmail"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_deactivated_user_blocked(self, mock_verify, db_session, settings):
        svc = AuthService(settings)
        user = svc.register(db_session, "alice", "alice@gmail.com", "Str0ngPass!")
        user.is_active = False
        db_session.commit()
        mock_verify.return_value = self._mock_idinfo()
        with pytest.raises(ValueError, match="deactivated"):
            svc.google_authenticate(db_session, "fake-token", "test-client-id")


class TestAuthenticateErrors:
    """Test improved error messages from authenticate()."""

    def test_no_account_found(self, db_session, settings):
        svc = AuthService(settings)
        with pytest.raises(ValueError, match="No account found"):
            svc.authenticate(db_session, "nobody", "pass")

    def test_deactivated_account(self, db_session, settings):
        svc = AuthService(settings)
        user = svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        user.is_active = False
        db_session.commit()
        with pytest.raises(ValueError, match="deactivated"):
            svc.authenticate(db_session, "alice", "Str0ngPass!")

    def test_oauth_only_user(self, db_session, settings):
        svc = AuthService(settings)
        from uuid import uuid4
        user = UserRecord(
            id=str(uuid4()), username="guser", email="g@test.com",
            password_hash=None, auth_provider="google", is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        with pytest.raises(ValueError, match="Google Sign-In"):
            svc.authenticate(db_session, "guser", "anypass")

    def test_wrong_password(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        with pytest.raises(ValueError, match="Incorrect password"):
            svc.authenticate(db_session, "alice", "WrongPass!")

    def test_correct_password_succeeds(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        user = svc.authenticate(db_session, "alice", "Str0ngPass!")
        assert user is not None
        assert user.username == "alice"


class TestPasswordReset:
    """Test password reset flow."""

    def test_generate_reset_code(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        code = svc.generate_reset_code(db_session, "alice@test.com")
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_code_no_account(self, db_session, settings):
        svc = AuthService(settings)
        with pytest.raises(ValueError, match="No account found"):
            svc.generate_reset_code(db_session, "nobody@test.com")

    def test_verify_and_reset(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        code = svc.generate_reset_code(db_session, "alice@test.com")
        user = svc.verify_reset_code(db_session, "alice@test.com", code, "NewPass123!")
        assert user is not None
        with pytest.raises(ValueError, match="Incorrect password"):
            svc.authenticate(db_session, "alice", "Str0ngPass!")
        user = svc.authenticate(db_session, "alice", "NewPass123!")
        assert user.username == "alice"

    def test_wrong_code(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        svc.generate_reset_code(db_session, "alice@test.com")
        with pytest.raises(ValueError, match="Invalid verification code"):
            svc.verify_reset_code(db_session, "alice@test.com", "000000", "NewPass!")

    def test_expired_code(self, db_session, settings):
        svc = AuthService(settings)
        svc.register(db_session, "alice", "alice@test.com", "Str0ngPass!")
        code = svc.generate_reset_code(db_session, "alice@test.com")
        user = db_session.query(UserRecord).filter(UserRecord.email == "alice@test.com").first()
        user.reset_code_expires = datetime.utcnow() - timedelta(minutes=1)
        db_session.commit()
        with pytest.raises(ValueError, match="expired"):
            svc.verify_reset_code(db_session, "alice@test.com", code, "NewPass!")
