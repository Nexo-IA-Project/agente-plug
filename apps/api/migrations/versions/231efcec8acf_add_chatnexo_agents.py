"""add chatnexo_agents table and conversations.last_onboarding_agent_id

Revision ID: 231efcec8acf
Revises: 8bdd77da3217
Create Date: 2026-05-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "231efcec8acf"
down_revision = "8bdd77da3217"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatnexo_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "name", name="uq_chatnexo_agents_account_name"),
    )
    op.create_index("ix_chatnexo_agents_account", "chatnexo_agents", ["account_id"])

    op.add_column(
        "conversations",
        sa.Column("last_onboarding_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_last_onboarding_agent",
        "conversations",
        "chatnexo_agents",
        ["last_onboarding_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_last_onboarding_agent", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "last_onboarding_agent_id")
    op.drop_index("ix_chatnexo_agents_account", table_name="chatnexo_agents")
    op.drop_table("chatnexo_agents")
