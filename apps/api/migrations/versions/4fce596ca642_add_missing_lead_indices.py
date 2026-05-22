"""add missing indices for leads and hubla_events

Revision ID: 4fce596ca642
Revises: db857b9fe716
Create Date: 2026-05-22

"""
from __future__ import annotations

from alembic import op

revision: str = "4fce596ca642"
down_revision: str | None = "db857b9fe716"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_leads_account_utm_source", "leads", ["account_id", "utm_source"])
    op.create_index("ix_hubla_events_contact", "hubla_events", ["contact_id"])


def downgrade() -> None:
    op.drop_index("ix_hubla_events_contact", table_name="hubla_events")
    op.drop_index("ix_leads_account_utm_source", table_name="leads")
