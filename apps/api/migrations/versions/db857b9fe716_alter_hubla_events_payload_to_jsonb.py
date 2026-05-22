"""alter hubla_events payload to jsonb

Revision ID: db857b9fe716
Revises: 83ff9745e1a6
Create Date: 2026-05-22

"""
from __future__ import annotations

from alembic import op

revision = "db857b9fe716"
down_revision = "83ff9745e1a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE hubla_events ALTER COLUMN payload TYPE jsonb USING payload::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE hubla_events ALTER COLUMN payload TYPE json USING payload::json"
    )
