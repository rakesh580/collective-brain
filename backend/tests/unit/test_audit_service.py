"""Unit tests for AuditService — log writing, querying, request parsing."""

from unittest.mock import MagicMock

from app.services.audit_service import AuditService


class TestAuditServiceLog:
    def test_log_creates_entry(self):
        db = MagicMock()
        entry = AuditService.log(
            db,
            action="auth.login",
            user_id="user-1",
            organization_id="org-1",
            actor="alice",
            result="ok",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert entry.action == "auth.login"
        assert entry.user_id == "user-1"
        assert entry.organization_id == "org-1"
        assert entry.result == "ok"

    def test_log_defaults_to_ok_result(self):
        db = MagicMock()
        entry = AuditService.log(db, action="test.action")
        assert entry.result == "ok"

    def test_log_never_raises_on_db_error(self):
        db = MagicMock()
        db.commit.side_effect = Exception("DB down")
        # Should not raise
        AuditService.log(db, action="auth.login")
        db.rollback.assert_called_once()

    def test_log_with_detail(self):
        db = MagicMock()
        entry = AuditService.log(
            db,
            action="org.sso_configured",
            detail={"idp_entity_id": "https://idp.example.com", "enforce_sso": True},
        )
        assert entry.detail["idp_entity_id"] == "https://idp.example.com"

    def test_log_empty_detail_defaults_to_dict(self):
        db = MagicMock()
        entry = AuditService.log(db, action="user.created")
        assert isinstance(entry.detail, dict)


class TestAuditServiceFromRequest:
    def test_extracts_ip_from_x_forwarded_for(self):
        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1", "user-agent": "TestBot/1.0"}
        result = AuditService.from_request(request)
        assert result["ip_address"] == "1.2.3.4"
        assert result["user_agent"] == "TestBot/1.0"

    def test_falls_back_to_client_host(self):
        request = MagicMock()
        # Use MagicMock for headers so .get() is wrappable
        request.headers.get = lambda k, d=None: {"user-agent": "curl/7.88"}.get(k, d)
        request.client = MagicMock()
        request.client.host = "192.168.1.50"
        result = AuditService.from_request(request)
        assert result["ip_address"] == "192.168.1.50"

    def test_handles_none_request(self):
        result = AuditService.from_request(None)
        assert result["ip_address"] is None
        assert result["user_agent"] is None


class TestAuditServiceList:
    def test_list_filters_by_org(self):
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        AuditService.list(db, organization_id="org-1")
        db.query.assert_called_once()

    def test_list_returns_list(self):
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = AuditService.list(db)
        assert isinstance(result, list)
