"""meta_templates media columns

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-08 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meta_templates",
        sa.Column("category", sa.String(32), nullable=False, server_default="UTILITY"),
    )
    op.add_column(
        "meta_templates",
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("meta_templates", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("meta_templates", sa.Column("media_object_key", sa.Text(), nullable=True))
    op.add_column("meta_templates", sa.Column("media_kind", sa.String(16), nullable=True))
    op.add_column("meta_templates", sa.Column("media_sha256", sa.String(64), nullable=True))
    op.add_column("meta_templates", sa.Column("media_size", sa.BigInteger(), nullable=True))
    op.add_column(
        "meta_templates",
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
    )
    op.add_column("meta_templates", sa.Column("rejection_reason", sa.Text(), nullable=True))

    # Migra dados antigos (approved bool → status)
    op.execute("UPDATE meta_templates SET status = 'APPROVED' WHERE approved = TRUE")
    op.drop_column("meta_templates", "approved")

    # Constraints
    op.create_check_constraint(
        "chk_media_consistency",
        "meta_templates",
        "(media_url IS NULL AND media_kind IS NULL AND media_object_key IS NULL) OR "
        "(media_url IS NOT NULL AND media_kind IS NOT NULL AND media_object_key IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_meta_template_account_name", "meta_templates", ["account_id", "name"]
    )
    op.create_index("ix_meta_templates_status", "meta_templates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_meta_templates_status", table_name="meta_templates")
    op.drop_constraint("uq_meta_template_account_name", "meta_templates", type_="unique")
    op.drop_constraint("chk_media_consistency", "meta_templates", type_="check")
    op.add_column(
        "meta_templates",
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE meta_templates SET approved = TRUE WHERE status = 'APPROVED'")
    op.drop_column("meta_templates", "rejection_reason")
    op.drop_column("meta_templates", "status")
    op.drop_column("meta_templates", "media_size")
    op.drop_column("meta_templates", "media_sha256")
    op.drop_column("meta_templates", "media_kind")
    op.drop_column("meta_templates", "media_object_key")
    op.drop_column("meta_templates", "media_url")
    op.drop_column("meta_templates", "components")
    op.drop_column("meta_templates", "category")
