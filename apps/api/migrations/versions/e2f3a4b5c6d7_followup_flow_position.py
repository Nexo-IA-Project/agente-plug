"""followup_flows: add position column

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-08 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Adiciona com default 0 para não quebrar inserts existentes durante o deploy.
    op.add_column(
        "followup_flows",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill: numera flows existentes por account_id, ordenando por created_at.
    op.execute(
        """
        UPDATE followup_flows AS f
        SET position = sub.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY account_id ORDER BY created_at ASC
            ) AS rn
            FROM followup_flows
        ) AS sub
        WHERE f.id = sub.id
        """
    )

    # Remove default — novos flows recebem position calculado pelo repo.
    op.alter_column("followup_flows", "position", server_default=None)


def downgrade() -> None:
    op.drop_column("followup_flows", "position")
