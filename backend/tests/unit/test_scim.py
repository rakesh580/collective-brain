"""Unit tests for SCIM helper functions."""

from datetime import UTC
from unittest.mock import MagicMock


class TestSlugifyUsername:
    def test_simple_email_prefix(self):
        from app.routers.scim import _slugify_username

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        assert _slugify_username(db, "alice") == "alice"

    def test_strips_special_chars(self):
        from app.routers.scim import _slugify_username

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        result = _slugify_username(db, "john.doe+test")
        # special chars replaced with _
        assert all(c.isalnum() or c == "_" for c in result)

    def test_deduplicates_on_collision(self):
        from app.routers.scim import _slugify_username

        db = MagicMock()
        # First call (username "alice") — already exists; second ("alice_1") — free
        call_count = {"n": 0}

        def _first():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return MagicMock()  # exists
            return None  # free

        db.query.return_value.filter_by.return_value.first.side_effect = _first
        result = _slugify_username(db, "alice")
        assert result == "alice_1"


class TestScimUserShape:
    def test_scim_user_dict_has_required_fields(self):
        from datetime import datetime
        from unittest.mock import MagicMock

        from app.models.user import UserRecord
        from app.routers.scim import _scim_user

        user = UserRecord(
            id="u-1",
            username="alice",
            email="alice@example.com",
            display_name="Alice",
            is_active=True,
            scim_external_id="ext-1",
            created_at=datetime.now(UTC),
        )
        request = MagicMock()
        request.base_url = "http://localhost:8000/"

        result = _scim_user(user, request)
        assert result["id"] == "u-1"
        assert result["userName"] == "alice@example.com"
        assert result["active"] is True
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in result["schemas"]
        assert "meta" in result
