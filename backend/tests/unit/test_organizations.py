"""Unit tests for organization router helpers — slug validation, role checks."""
import pytest
from pydantic import ValidationError

from app.routers.organizations import (
    OrgCreateRequest,
    OrgUpdateRequest,
    InviteMemberRequest,
    SSOConfigRequest,
)


class TestOrgCreateRequest:
    def test_valid_org(self):
        req = OrgCreateRequest(name="Acme Corp", slug="acme-corp", plan="free")
        assert req.slug == "acme-corp"

    def test_invalid_plan(self):
        with pytest.raises(ValidationError):
            OrgCreateRequest(name="X", slug="x", plan="invalid-plan")

    def test_slug_must_be_lowercase_alphanumeric_dashes(self):
        with pytest.raises(ValidationError):
            OrgCreateRequest(name="X", slug="Upper_Case", plan="free")

    def test_slug_too_short(self):
        with pytest.raises(ValidationError):
            OrgCreateRequest(name="X", slug="a", plan="free")

    def test_enterprise_plan_allowed(self):
        req = OrgCreateRequest(name="Big Corp", slug="big-corp", plan="enterprise")
        assert req.plan == "enterprise"


class TestOrgUpdateRequest:
    def test_all_fields_optional(self):
        req = OrgUpdateRequest()
        assert req.name is None
        assert req.plan is None

    def test_invalid_plan(self):
        with pytest.raises(ValidationError):
            OrgUpdateRequest(plan="startup")

    def test_valid_update(self):
        req = OrgUpdateRequest(name="New Name", plan="pro")
        assert req.name == "New Name"
        assert req.plan == "pro"


class TestInviteMemberRequest:
    def test_valid_invite(self):
        req = InviteMemberRequest(user_id="user-123", role="admin")
        assert req.role == "admin"

    def test_default_role_is_member(self):
        req = InviteMemberRequest(user_id="user-123")
        assert req.role == "member"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            InviteMemberRequest(user_id="user-123", role="superuser")

    def test_owner_role_allowed(self):
        req = InviteMemberRequest(user_id="user-123", role="owner")
        assert req.role == "owner"


class TestSSOConfigRequest:
    def test_all_optional(self):
        req = SSOConfigRequest()
        assert req.idp_entity_id is None
        assert req.allowed_domains == []
        assert req.enforce_sso is False

    def test_full_config(self):
        req = SSOConfigRequest(
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            allowed_domains=["example.com", "corp.example.com"],
            enforce_sso=True,
        )
        assert len(req.allowed_domains) == 2
        assert req.enforce_sso is True
