"""rename delay_from_purchase_hours to delay_from_purchase_minutes

Revision ID: 64664593d802
Revises: 4fce596ca642
Create Date: 2026-05-22

A coluna era INT em horas mas a UI permitia minutos (2 min → 0.0333 horas, float).
Renomeada para minutos (INT direto) preservando dados via UPDATE * 60.
"""
from __future__ import annotations

from alembic import op


revision = "64664593d802"
down_revision = "4fce596ca642"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # followup_steps
    op.alter_column("followup_steps", "delay_from_purchase_hours", new_column_name="delay_from_purchase_minutes")
    op.execute("UPDATE followup_steps SET delay_from_purchase_minutes = delay_from_purchase_minutes * 60")

    # followup_enrollment_steps (snapshot)
    op.alter_column("followup_enrollment_steps", "delay_from_purchase_hours", new_column_name="delay_from_purchase_minutes")
    op.execute("UPDATE followup_enrollment_steps SET delay_from_purchase_minutes = delay_from_purchase_minutes * 60")


def downgrade() -> None:
    op.execute("UPDATE followup_enrollment_steps SET delay_from_purchase_minutes = delay_from_purchase_minutes / 60")
    op.alter_column("followup_enrollment_steps", "delay_from_purchase_minutes", new_column_name="delay_from_purchase_hours")

    op.execute("UPDATE followup_steps SET delay_from_purchase_minutes = delay_from_purchase_minutes / 60")
    op.alter_column("followup_steps", "delay_from_purchase_minutes", new_column_name="delay_from_purchase_hours")
