"""followup engine v2 — FK, indexes, failure_reason, flow_step_id

Revision ID: a1b2c3d4e5f7
Revises: b5c6d7e8f9a0
Create Date: 2026-05-21

Mudanças:
- FK em followup_enrollments.flow_id apontando para followup_flows.id (ON DELETE SET NULL).
- Coluna flow_id torna-se nullable (necessário para SET NULL).
- Índice UNIQUE compound em (account_id, contact_id, flow_id, purchase_id) para dedup.
- Índices de leitura em followup_enrollments e followup_enrollment_steps.
- Novas colunas failure_reason e flow_step_id em followup_enrollment_steps.

Observações:
- A coluna status (tanto em followup_enrollments quanto em followup_enrollment_steps) é
  armazenada como VARCHAR(20) — NÃO existe um tipo ENUM do PostgreSQL nessas tabelas.
  Portanto não há ALTER TYPE para adicionar 'CANCELLED'; o novo valor é adicionado apenas
  no enum Python (EnrollmentStepStatus) na entity.
- scheduled_job_id já foi criada na migration a2b3c4d5e6f7; não é recriada aqui.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f7"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Tornar flow_id nullable (pré-requisito para FK com ON DELETE SET NULL)
    op.alter_column(
        "followup_enrollments",
        "flow_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 2. FK em followup_enrollments.flow_id (SET NULL ao deletar flow)
    op.create_foreign_key(
        "fk_followup_enrollments_flow",
        "followup_enrollments",
        "followup_flows",
        ["flow_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. UNIQUE compound para dedup
    op.create_index(
        "uq_followup_enrollment_dedup",
        "followup_enrollments",
        ["account_id", "contact_id", "flow_id", "purchase_id"],
        unique=True,
    )

    # 4. Índices de leitura
    op.create_index(
        "idx_followup_enrollments_flow_status",
        "followup_enrollments",
        ["flow_id", "status"],
    )
    op.create_index(
        "idx_followup_enrollments_account_contact",
        "followup_enrollments",
        ["account_id", "contact_id"],
    )
    op.create_index(
        "idx_followup_enrollment_steps_enr_status",
        "followup_enrollment_steps",
        ["enrollment_id", "status"],
    )

    # 5. Novas colunas em followup_enrollment_steps
    op.add_column(
        "followup_enrollment_steps",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "followup_enrollment_steps",
        sa.Column("flow_step_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("followup_enrollment_steps", "flow_step_id")
    op.drop_column("followup_enrollment_steps", "failure_reason")
    op.drop_index(
        "idx_followup_enrollment_steps_enr_status",
        table_name="followup_enrollment_steps",
    )
    op.drop_index(
        "idx_followup_enrollments_account_contact",
        table_name="followup_enrollments",
    )
    op.drop_index(
        "idx_followup_enrollments_flow_status",
        table_name="followup_enrollments",
    )
    op.drop_index("uq_followup_enrollment_dedup", table_name="followup_enrollments")
    op.drop_constraint(
        "fk_followup_enrollments_flow",
        "followup_enrollments",
        type_="foreignkey",
    )
    op.alter_column(
        "followup_enrollments",
        "flow_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
