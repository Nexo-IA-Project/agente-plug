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

    # Renomear índices — onboarding_flows
    op.execute(
        "ALTER INDEX followup_flows_pkey "
        "RENAME TO onboarding_flows_pkey"
    )
    op.execute(
        "ALTER INDEX ix_followup_flows_account_id "
        "RENAME TO ix_onboarding_flows_account_id"
    )
    op.execute(
        "ALTER INDEX ix_followup_flows_product_id "
        "RENAME TO ix_onboarding_flows_product_id"
    )
    op.execute(
        "ALTER INDEX ix_followup_flows_trigger_event_type "
        "RENAME TO ix_onboarding_flows_trigger_event_type"
    )

    # Renomear índices — onboarding_steps
    op.execute(
        "ALTER INDEX followup_steps_pkey "
        "RENAME TO onboarding_steps_pkey"
    )
    op.execute(
        "ALTER INDEX ix_followup_steps_flow_id "
        "RENAME TO ix_onboarding_steps_flow_id"
    )
    op.execute(
        "ALTER INDEX ix_followup_steps_flow_position "
        "RENAME TO ix_onboarding_steps_flow_position"
    )

    # Renomear índices — onboarding_enrollments
    op.execute(
        "ALTER INDEX followup_enrollments_pkey "
        "RENAME TO onboarding_enrollments_pkey"
    )
    op.execute(
        "ALTER INDEX ix_followup_enrollments_account_contact "
        "RENAME TO ix_onboarding_enrollments_account_contact"
    )
    op.execute(
        "ALTER INDEX ix_followup_enrollments_account_id "
        "RENAME TO ix_onboarding_enrollments_account_id"
    )
    op.execute(
        "ALTER INDEX ix_followup_enrollments_flow_status "
        "RENAME TO ix_onboarding_enrollments_flow_status"
    )
    op.execute(
        "ALTER INDEX uq_followup_enrollment_dedup "
        "RENAME TO uq_onboarding_enrollment_dedup"
    )

    # Renomear índices — onboarding_enrollment_steps
    op.execute(
        "ALTER INDEX followup_enrollment_steps_pkey "
        "RENAME TO onboarding_enrollment_steps_pkey"
    )
    op.execute(
        "ALTER INDEX ix_followup_enrollment_steps_enrollment_id "
        "RENAME TO ix_onboarding_enrollment_steps_enrollment_id"
    )
    op.execute(
        "ALTER INDEX ix_followup_enrollment_steps_enrollment_status "
        "RENAME TO ix_onboarding_enrollment_steps_enrollment_status"
    )

    # Renomear FKs
    op.execute(
        "ALTER TABLE onboarding_flows "
        "RENAME CONSTRAINT followup_flows_account_id_fkey "
        "TO onboarding_flows_account_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_flows "
        "RENAME CONSTRAINT fk_followup_flows_product_id "
        "TO fk_onboarding_flows_product_id"
    )
    op.execute(
        "ALTER TABLE onboarding_steps "
        "RENAME CONSTRAINT followup_steps_flow_id_fkey "
        "TO onboarding_steps_flow_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT followup_enrollments_account_id_fkey "
        "TO onboarding_enrollments_account_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT followup_enrollments_contact_id_fkey "
        "TO onboarding_enrollments_contact_id_fkey"
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
    # Reverter FKs (ordem inversa do upgrade)
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
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT onboarding_enrollments_contact_id_fkey "
        "TO followup_enrollments_contact_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT onboarding_enrollments_account_id_fkey "
        "TO followup_enrollments_account_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_steps "
        "RENAME CONSTRAINT onboarding_steps_flow_id_fkey "
        "TO followup_steps_flow_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_flows "
        "RENAME CONSTRAINT fk_onboarding_flows_product_id "
        "TO fk_followup_flows_product_id"
    )
    op.execute(
        "ALTER TABLE onboarding_flows "
        "RENAME CONSTRAINT onboarding_flows_account_id_fkey "
        "TO followup_flows_account_id_fkey"
    )

    # Reverter índices — onboarding_enrollment_steps
    op.execute(
        "ALTER INDEX ix_onboarding_enrollment_steps_enrollment_status "
        "RENAME TO ix_followup_enrollment_steps_enrollment_status"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_enrollment_steps_enrollment_id "
        "RENAME TO ix_followup_enrollment_steps_enrollment_id"
    )
    op.execute(
        "ALTER INDEX onboarding_enrollment_steps_pkey "
        "RENAME TO followup_enrollment_steps_pkey"
    )

    # Reverter índices — onboarding_enrollments
    op.execute(
        "ALTER INDEX uq_onboarding_enrollment_dedup "
        "RENAME TO uq_followup_enrollment_dedup"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_enrollments_flow_status "
        "RENAME TO ix_followup_enrollments_flow_status"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_enrollments_account_id "
        "RENAME TO ix_followup_enrollments_account_id"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_enrollments_account_contact "
        "RENAME TO ix_followup_enrollments_account_contact"
    )
    op.execute(
        "ALTER INDEX onboarding_enrollments_pkey "
        "RENAME TO followup_enrollments_pkey"
    )

    # Reverter índices — onboarding_steps
    op.execute(
        "ALTER INDEX ix_onboarding_steps_flow_position "
        "RENAME TO ix_followup_steps_flow_position"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_steps_flow_id "
        "RENAME TO ix_followup_steps_flow_id"
    )
    op.execute(
        "ALTER INDEX onboarding_steps_pkey "
        "RENAME TO followup_steps_pkey"
    )

    # Reverter índices — onboarding_flows
    op.execute(
        "ALTER INDEX ix_onboarding_flows_trigger_event_type "
        "RENAME TO ix_followup_flows_trigger_event_type"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_flows_product_id "
        "RENAME TO ix_followup_flows_product_id"
    )
    op.execute(
        "ALTER INDEX ix_onboarding_flows_account_id "
        "RENAME TO ix_followup_flows_account_id"
    )
    op.execute(
        "ALTER INDEX onboarding_flows_pkey "
        "RENAME TO followup_flows_pkey"
    )

    op.rename_table("onboarding_enrollment_steps", "followup_enrollment_steps")
    op.rename_table("onboarding_enrollments", "followup_enrollments")
    op.rename_table("onboarding_steps", "followup_steps")
    op.rename_table("onboarding_flows", "followup_flows")
