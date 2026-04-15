"""Phase 4 enterprise: audit_logs table, SAML/SCIM fields on users.

Revision ID: 004_enterprise
Revises: 003_pgvector
Create Date: 2026-04-08
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "004_enterprise"
down_revision: str | None = "003_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── SAML / SSO fields on users ────────────────────────────────────────────
    op.add_column("users", sa.Column("saml_nameid", sa.String(), nullable=True))
    op.add_column("users", sa.Column("saml_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("scim_external_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("mfa_secret", sa.String(), nullable=True))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), server_default="false"))

    op.create_index("ix_users_saml_nameid", "users", ["saml_nameid"])
    op.create_index("ix_users_scim_external_id", "users", ["scim_external_id"])

    # ── SCIM token on organization_memberships ────────────────────────────────
    # Orgs can have a SCIM provisioning token stored in organizations.settings_json
    # (no DDL change needed — settings_json is already JSON)

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),  # e.g. "auth.login"
        sa.Column("actor", sa.String(), nullable=True),       # username or "scim"
        sa.Column("target_type", sa.String(50), nullable=True),  # "user", "org", etc.
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("result", sa.String(20), nullable=False, server_default="ok"),  # ok | fail
        sa.Column("detail", sa.JSON(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_users_scim_external_id", table_name="users")
    op.drop_index("ix_users_saml_nameid", table_name="users")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "scim_external_id")
    op.drop_column("users", "saml_provider")
    op.drop_column("users", "saml_nameid")
