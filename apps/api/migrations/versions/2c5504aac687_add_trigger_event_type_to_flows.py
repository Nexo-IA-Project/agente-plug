"""add trigger_event_type to followup_flows

Revision ID: 2c5504aac687
Revises: 42c2b623d919
Create Date: 2026-05-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2c5504aac687"
down_revision = "42c2b623d919"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "followup_flows",
        sa.Column(
            "trigger_event_type",
            sa.String(80),
            nullable=False,
            server_default="subscription.activated",
        ),
    )
    op.create_index(
        "ix_followup_flows_trigger_event_type",
        "followup_flows",
        ["trigger_event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_followup_flows_trigger_event_type", table_name="followup_flows")
    op.drop_column("followup_flows", "trigger_event_type")
