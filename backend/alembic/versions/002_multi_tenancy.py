"""Multi-tenancy: organizations table + organization_id on every tenant-scoped table.

Revision ID: 002_multi_tenancy
Revises: 001_initial_schema
Create Date: 2026-04-07
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "002_multi_tenancy"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All tables that receive an organization_id FK column
_TENANT_TABLES = [
    "users",
    "members",
    "artifacts",
    "contributions",
    "conversations",
    "insights",
    "discussion_threads",
    "chat_rooms",
    "slack_workspaces",
    "help_requests",
    "slack_digest_config",
    "health_snapshots",
]


def upgrade() -> None:
    # ── organizations ──────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("settings_json", sa.JSON(), server_default="{}"),
        sa.Column("metadata_json", sa.JSON(), server_default="{}"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # ── organization_memberships ───────────────────────────────────────
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_membership"),
    )
    op.create_index("ix_org_memberships_org_id", "organization_memberships", ["organization_id"])
    op.create_index("ix_org_memberships_user_id", "organization_memberships", ["user_id"])

    # ── Add organization_id FK to every tenant-scoped table ───────────
    for table in _TENANT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "organization_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")

    op.drop_index("ix_org_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_org_memberships_org_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
