"""onboarding_steps.flow_id ganha ON DELETE CASCADE

Revision ID: 3e4f5a6b7c8d
Revises: 231efcec8acf
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa  # noqa: F401
from alembic import op

revision = "3e4f5a6b7c8d"
down_revision = "231efcec8acf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "onboarding_steps_flow_id_fkey",
        "onboarding_steps",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "onboarding_steps_flow_id_fkey",
        "onboarding_steps",
        "onboarding_flows",
        ["flow_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "onboarding_steps_flow_id_fkey",
        "onboarding_steps",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "onboarding_steps_flow_id_fkey",
        "onboarding_steps",
        "onboarding_flows",
        ["flow_id"],
        ["id"],
    )
