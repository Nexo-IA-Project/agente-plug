"""add job_queue and job_dlq tables

Revision ID: e1f2a3b4c5d6
Revises: d5e1f2a3b4c5
Create Date: 2026-05-02 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d5e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_queue",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="20"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_job_queue_dequeue", "job_queue", ["priority", "created_at"])

    op.create_table(
        "job_dlq",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("job_dlq")
    op.drop_index("ix_job_queue_dequeue", table_name="job_queue")
    op.drop_table("job_queue")
