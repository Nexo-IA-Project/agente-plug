"""audit_events: add ip, geo and user columns

Revision ID: a9b0c1d2e3f4
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9b0c1d2e3f4"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "actor",
        type_=sa.String(120),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.add_column("audit_events", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("audit_events", sa.Column("user_name", sa.String(120), nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_events", sa.Column("geo_city", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("geo_country", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("geo_region", sa.String(100), nullable=True))
    op.create_index("ix_audit_events_account_user", "audit_events", ["account_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_account_user", table_name="audit_events")
    op.drop_column("audit_events", "geo_region")
    op.drop_column("audit_events", "geo_country")
    op.drop_column("audit_events", "geo_city")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "user_name")
    op.drop_column("audit_events", "user_id")
    op.alter_column(
        "audit_events",
        "actor",
        type_=sa.String(20),
        existing_type=sa.String(120),
        existing_nullable=False,
    )
