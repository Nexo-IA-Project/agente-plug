"""add loja_express_cases table

Revision ID: c3f1a82e9d74
Revises: 50d62657fc63
Create Date: 2026-04-25 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3f1a82e9d74"
down_revision: Union[str, None] = "50d62657fc63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loja_express_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("purchase_id", sa.String(), nullable=False, unique=True),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("student_email", sa.String(), nullable=False),
        sa.Column("form_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("loja_entregue", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(40), nullable=False, server_default=sa.text("'aguardando_formulario'")),
        sa.Column("scheduled_job_d1_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d3_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d5_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d7_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(
        "idx_loja_express_cases_account_contact",
        "loja_express_cases",
        ["account_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_loja_express_cases_account_contact", table_name="loja_express_cases")
    op.drop_table("loja_express_cases")
