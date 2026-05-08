"""followup_step: add message_text, make meta_template_name nullable

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-05-07 23:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("followup_steps", "meta_template_name", nullable=True)
    op.add_column("followup_steps", sa.Column("message_text", sa.Text(), nullable=True))

    op.alter_column("followup_enrollment_steps", "meta_template_name", nullable=True)
    op.add_column(
        "followup_enrollment_steps", sa.Column("message_text", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("followup_enrollment_steps", "message_text")
    op.alter_column("followup_enrollment_steps", "meta_template_name", nullable=False)

    op.drop_column("followup_steps", "message_text")
    op.alter_column("followup_steps", "meta_template_name", nullable=False)
