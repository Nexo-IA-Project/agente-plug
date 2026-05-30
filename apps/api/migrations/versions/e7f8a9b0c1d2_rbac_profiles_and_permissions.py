"""rbac: profiles + profile_permissions + users.profile_id

Revision ID: e7f8a9b0c1d2
Revises: 1d898ca7cc45
Create Date: 2026-05-30

down_revision chosen from the single active head reported by
`alembic heads` at time of writing (1d898ca7cc45).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e7f8a9b0c1d2"
down_revision = "1d898ca7cc45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("account_id", "name", name="uq_profiles_account_name"),
    )
    op.create_index("ix_profiles_account_id", "profiles", ["account_id"])

    op.create_table(
        "profile_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission_key", sa.String(100), nullable=False),
        sa.UniqueConstraint("profile_id", "permission_key", name="uq_profile_perm"),
    )
    op.create_index(
        "ix_profile_permissions_profile_id",
        "profile_permissions",
        ["profile_id"],
    )

    op.add_column(
        "users",
        sa.Column(
            "profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_id")
    op.drop_index("ix_profile_permissions_profile_id", table_name="profile_permissions")
    op.drop_table("profile_permissions")
    op.drop_index("ix_profiles_account_id", table_name="profiles")
    op.drop_table("profiles")
