"""Week 11-12: org-level strengths/weaknesses snapshot column.

Revision ID: 013_org_strengths_weaknesses
Revises: 012_signals
Create Date: 2026-04-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_org_strengths_weaknesses"
down_revision: str | None = "012_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "strengths_weaknesses_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "strengths_weaknesses_json")
