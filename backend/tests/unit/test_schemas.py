import pytest
from pydantic import ValidationError

from app.schemas.requests import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    QueryRequest,
)


class TestRegisterRequest:
    def test_register_request_valid(self):
        req = RegisterRequest(
            username="johndoe",
            email="john@example.com",
            password="StrongPass1",
            display_name="John Doe",
        )
        assert req.username == "johndoe"
        assert req.email == "john@example.com"
        assert req.password == "StrongPass1"
        assert req.display_name == "John Doe"

    def test_register_request_weak_password_no_uppercase(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                username="johndoe",
                email="john@example.com",
                password="weakpass1",
            )
        assert "uppercase" in str(exc_info.value).lower()

    def test_register_request_short_password(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                username="johndoe",
                email="john@example.com",
                password="Ab1",
            )
        # min_length=8 validation
        errors = exc_info.value.errors()
        assert any(
            e["type"] == "string_too_short" for e in errors
        )


class TestLoginRequest:
    def test_login_request_valid(self):
        req = LoginRequest(username="johndoe", password="anything")
        assert req.username == "johndoe"
        assert req.password == "anything"


class TestResetPasswordRequest:
    def test_reset_password_request_code_length(self):
        """Code must be exactly 8 characters."""
        # Valid 8-char code
        req = ResetPasswordRequest(
            email="john@example.com",
            code="ABCD1234",
            new_password="NewStrong1",
        )
        assert req.code == "ABCD1234"

        # Too short
        with pytest.raises(ValidationError):
            ResetPasswordRequest(
                email="john@example.com",
                code="SHORT",
                new_password="NewStrong1",
            )

        # Too long
        with pytest.raises(ValidationError):
            ResetPasswordRequest(
                email="john@example.com",
                code="TOOLONGCODE1",
                new_password="NewStrong1",
            )


class TestQueryRequest:
    def test_query_request_valid(self):
        req = QueryRequest(question="What is the team working on?")
        assert req.question == "What is the team working on?"
        assert req.conversation_id is None
        assert req.filters is None

    def test_query_request_empty_question(self):
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(question="")
        errors = exc_info.value.errors()
        assert any(
            e["type"] == "string_too_short" for e in errors
        )
