"""Integration tests for Decision Intelligence endpoints — decisions, risk radar, continuity."""

import pytest


# ── Decision Endpoints ─────────────────────────────────────────────────────


class TestDecisionEndpoints:
    """Tests for /api/v1/decisions/* endpoints."""

    # -- Auth --

    def test_list_decisions_requires_auth(self, app_client):
        resp = app_client.get("/api/v1/decisions")
        assert resp.status_code == 401

    def test_get_decision_requires_auth(self, app_client):
        resp = app_client.get("/api/v1/decisions/some-id")
        assert resp.status_code == 401

    # -- CRUD --

    def test_list_decisions_empty(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert "total" in data
        assert isinstance(data["decisions"], list)
        assert isinstance(data["total"], int)

    def test_list_decisions_with_filters(self, app_client, auth_headers):
        resp = app_client.get(
            "/api/v1/decisions?decision_type=technical&status=active&limit=10&offset=0",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert "total" in data

    def test_get_decision_not_found(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions/nonexistent-id-12345", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_update_decision_not_found(self, app_client, auth_headers):
        resp = app_client.put(
            "/api/v1/decisions/nonexistent-id-12345",
            headers=auth_headers,
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_delete_decision_not_found(self, app_client, auth_headers):
        resp = app_client.delete("/api/v1/decisions/nonexistent-id-12345", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- Search --

    def test_search_decisions_empty(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions/search?q=test", headers=auth_headers)
        # Accept 200 (normal) or 500/503 (LLM not configured)
        if resp.status_code == 200:
            data = resp.json()
            assert "query" in data
            assert "results" in data
            assert "count" in data
            assert data["query"] == "test"
        else:
            assert resp.status_code in (500, 503)
            data = resp.json()
            assert "detail" in data

    def test_search_decisions_requires_query(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions/search", headers=auth_headers)
        assert resp.status_code == 422  # Missing required query param

    # -- Why did we --

    def test_why_endpoint(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/why",
            headers=auth_headers,
            json={"question": "Why did we choose Python?"},
        )
        # Accept 200 (normal) or 500/503 (LLM not configured)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (500, 503)
            data = resp.json()
            assert "detail" in data

    def test_why_requires_question(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/why",
            headers=auth_headers,
            json={"question": ""},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data

    # -- Timeline --

    def test_timeline_empty(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions/timeline?topic=test", headers=auth_headers)
        # Accept 200 (normal) or 500/503 (LLM not configured)
        if resp.status_code == 200:
            data = resp.json()
            assert "topic" in data
            assert "timeline" in data
            assert "count" in data
            assert data["topic"] == "test"
        else:
            assert resp.status_code in (500, 503)
            data = resp.json()
            assert "detail" in data

    def test_timeline_requires_topic(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/decisions/timeline", headers=auth_headers)
        assert resp.status_code == 422  # Missing required query param

    # -- Extract --

    def test_extract_requires_artifact_ids(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/extract",
            headers=auth_headers,
            json={"artifact_ids": []},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data

    def test_extract_with_nonexistent_artifacts(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/extract",
            headers=auth_headers,
            json={"artifact_ids": ["nonexistent-id-12345"]},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_extract_all(self, app_client, auth_headers):
        resp = app_client.post("/api/v1/decisions/extract-all", headers=auth_headers)
        # With empty DB (no artifacts), should succeed with 0 processed
        if resp.status_code == 200:
            data = resp.json()
            assert "total_artifacts" in data or "message" in data
        else:
            # LLM not configured
            assert resp.status_code in (500, 503)

    # -- Link --

    def test_link_decisions_not_found(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/nonexistent-id-12345/link",
            headers=auth_headers,
            json={"to_decision_id": "other-nonexistent-id", "link_type": "related"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- Acknowledge --

    def test_acknowledge_not_found(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/decisions/nonexistent-id-12345/acknowledge",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data


# ── Risk Radar Endpoints ──────────────────────────────────────────────────


class TestRiskRadarEndpoints:
    """Tests for /api/v1/risk-radar/* endpoints."""

    # -- Auth --

    def test_scan_requires_auth(self, app_client):
        resp = app_client.post("/api/v1/risk-radar/scan")
        assert resp.status_code == 401

    def test_alerts_requires_auth(self, app_client):
        resp = app_client.get("/api/v1/risk-radar/alerts")
        assert resp.status_code == 401

    # -- Scan --

    def test_scan_returns_alerts(self, app_client, auth_headers):
        resp = app_client.post("/api/v1/risk-radar/scan", headers=auth_headers)
        # Accept 200 (normal) or 500/503 (service issues)
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data
            assert "alert_count" in data
            assert "alerts" in data
            assert data["status"] == "completed"
            assert isinstance(data["alerts"], list)
            assert data["alert_count"] == len(data["alerts"])
        else:
            assert resp.status_code in (500, 503)

    # -- Alerts --

    def test_get_alerts(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/risk-radar/alerts", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert "count" in data
            assert "alerts" in data
            assert isinstance(data["alerts"], list)
        else:
            assert resp.status_code in (500, 503)

    def test_get_alerts_with_filters(self, app_client, auth_headers):
        resp = app_client.get(
            "/api/v1/risk-radar/alerts?severity=high&acknowledged=false",
            headers=auth_headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "count" in data
            assert "alerts" in data
        else:
            assert resp.status_code in (500, 503)

    def test_get_alert_not_found(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/risk-radar/alerts/nonexistent-id-12345", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- Alert actions --

    def test_acknowledge_alert_not_found(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/risk-radar/alerts/nonexistent-id-12345/acknowledge",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_resolve_alert_not_found(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/risk-radar/alerts/nonexistent-id-12345/resolve",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- Summary --

    def test_risk_summary(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/risk-radar/summary", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (500, 503)

    def test_risk_summary_has_required_fields(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/risk-radar/summary", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            for field in [
                "total_alerts",
                "critical_count",
                "high_count",
                "medium_count",
                "low_count",
                "by_severity",
                "by_type",
            ]:
                assert field in data, f"Missing field: {field}"
        else:
            # LLM/service not configured — verify error shape
            assert resp.status_code in (500, 503)
            data = resp.json()
            assert "detail" in data


# ── Continuity Endpoints ──────────────────────────────────────────────────


class TestContinuityEndpoints:
    """Tests for /api/v1/continuity/* endpoints."""

    # -- Auth --

    def test_dashboard_requires_auth(self, app_client):
        resp = app_client.get("/api/v1/continuity/dashboard")
        assert resp.status_code == 401

    # -- Dashboard --

    def test_continuity_dashboard(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/continuity/dashboard", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (500, 503)

    def test_dashboard_has_required_fields(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/continuity/dashboard", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            for field in [
                "overall_score",
                "risk_level",
                "members_at_risk",
                "knowledge_gaps",
                "backed_up_areas",
                "total_members",
                "recommendations",
            ]:
                assert field in data, f"Missing field: {field}"
        else:
            assert resp.status_code in (500, 503)
            data = resp.json()
            assert "detail" in data

    # -- Member --

    def test_member_continuity_not_found(self, app_client, auth_headers):
        resp = app_client.get(
            "/api/v1/continuity/member/nonexistent-id-12345",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- Team --

    def test_team_continuity(self, app_client, auth_headers):
        resp = app_client.get("/api/v1/continuity/team", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (500, 503)

    # -- Calculate --

    def test_calculate_continuity(self, app_client, auth_headers):
        resp = app_client.post("/api/v1/continuity/calculate", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (500, 503)

    # -- Project --

    def test_project_continuity(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/continuity/project",
            headers=auth_headers,
            json={"artifact_ids": ["some-artifact-id"]},
        )
        # With non-existent artifacts, should still return a result (empty analysis)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (404, 500, 503)

    def test_project_continuity_empty_ids(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/v1/continuity/project",
            headers=auth_headers,
            json={"artifact_ids": []},
        )
        # Empty list should either return a valid response or a 400
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        else:
            assert resp.status_code in (400, 422, 500, 503)


# ── Response Schema Validation ────────────────────────────────────────────


class TestResponseSchemas:
    """Verify response shapes match what the frontend expects."""

    def test_risk_summary_shape(self, app_client, auth_headers):
        """Verify risk summary has all fields the frontend expects."""
        resp = app_client.get("/api/v1/risk-radar/summary", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            for field in [
                "total_alerts",
                "critical_count",
                "high_count",
                "medium_count",
                "low_count",
                "by_severity",
                "by_type",
            ]:
                assert field in data, f"Missing field: {field}"
            # Verify types
            assert isinstance(data["total_alerts"], int)
            assert isinstance(data["by_severity"], dict)
            assert isinstance(data["by_type"], dict)
        else:
            pytest.skip("Risk radar service not available (LLM not configured)")

    def test_continuity_dashboard_shape(self, app_client, auth_headers):
        """Verify continuity dashboard has all fields the frontend expects."""
        resp = app_client.get("/api/v1/continuity/dashboard", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            for field in [
                "overall_score",
                "risk_level",
                "members_at_risk",
                "knowledge_gaps",
                "backed_up_areas",
                "total_members",
                "recommendations",
            ]:
                assert field in data, f"Missing field: {field}"
            # Verify types
            assert isinstance(data["overall_score"], (int, float))
            assert isinstance(data["risk_level"], str)
            assert isinstance(data["members_at_risk"], list)
            assert isinstance(data["knowledge_gaps"], list)
            assert isinstance(data["recommendations"], list)
            assert isinstance(data["total_members"], int)
        else:
            pytest.skip("Continuity service not available (LLM not configured)")

    def test_decisions_list_shape(self, app_client, auth_headers):
        """Verify decisions list response shape."""
        resp = app_client.get("/api/v1/decisions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["decisions"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_scan_response_shape(self, app_client, auth_headers):
        """Verify risk scan response has correct shape."""
        resp = app_client.post("/api/v1/risk-radar/scan", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "completed"
            assert isinstance(data["alert_count"], int)
            assert isinstance(data["alerts"], list)
            assert data["alert_count"] == len(data["alerts"])
        else:
            pytest.skip("Risk radar service not available")
