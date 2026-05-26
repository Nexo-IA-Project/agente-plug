"""rename followup to onboarding tables

Revision ID: 8bdd77da3217
Revises: 64664593d802
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op


revision = "8bdd77da3217"
down_revision = "64664593d802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("followup_flows", "onboarding_flows")
    op.rename_table("followup_steps", "onboarding_steps")
    op.rename_table("followup_enrollments", "onboarding_enrollments")
    op.rename_table("followup_enrollment_steps", "onboarding_enrollment_steps")

    # Renomear índice de steps
    op.execute(
        "ALTER INDEX ix_followup_steps_flow_position "
        "RENAME TO ix_onboarding_steps_flow_position"
    )

    # Renomear FKs que referenciam o nome da tabela origem
    # Nomes verificados diretamente no banco com \d
    op.execute(
        "ALTER TABLE onboarding_steps "
        "RENAME CONSTRAINT followup_steps_flow_id_fkey "
        "TO onboarding_steps_flow_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT fk_followup_enrollments_flow "
        "TO fk_onboarding_enrollments_flow"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollment_steps "
        "RENAME CONSTRAINT followup_enrollment_steps_enrollment_id_fkey "
        "TO onboarding_enrollment_steps_enrollment_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE onboarding_enrollment_steps "
        "RENAME CONSTRAINT onboarding_enrollment_steps_enrollment_id_fkey "
        "TO followup_enrollment_steps_enrollment_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT fk_onboarding_enrollments_flow "
        "TO fk_followup_enrollments_flow"
    )
    op.execute(
        "ALTER TABLE onboarding_steps "
        "RENAME CONSTRAINT onboarding_steps_flow_id_fkey "
        "TO followup_steps_flow_id_fkey"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_steps_flow_position "
        "RENAME TO ix_followup_steps_flow_position"
    )

    op.rename_table("onboarding_enrollment_steps", "followup_enrollment_steps")
    op.rename_table("onboarding_enrollments", "followup_enrollments")
    op.rename_table("onboarding_steps", "followup_steps")
    op.rename_table("onboarding_flows", "followup_flows")
