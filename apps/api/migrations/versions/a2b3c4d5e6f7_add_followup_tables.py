"""add_followup_tables

Revision ID: a2b3c4d5e6f7
Revises: 657de6865172, a1b2c3d4e5f6
Create Date: 2026-05-07 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str]] = ("657de6865172", "a1b2c3d4e5f6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "followup_flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("product_tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_flows_account_id", "followup_flows", ["account_id"])

    op.create_table(
        "followup_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("flow_id", UUID(as_uuid=True), sa.ForeignKey("followup_flows.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("delay_from_purchase_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("meta_template_name", sa.String(200), nullable=False),
        sa.Column("template_variables", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_steps_flow_id", "followup_steps", ["flow_id"])
    op.create_index("ix_followup_steps_flow_position", "followup_steps", ["flow_id", "position"])

    op.create_table(
        "followup_enrollments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("flow_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("contact_phone", sa.String(30), nullable=False),
        sa.Column("purchase_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_enrollments_account_id", "followup_enrollments", ["account_id"])

    op.create_table(
        "followup_enrollment_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enrollment_id", UUID(as_uuid=True), sa.ForeignKey("followup_enrollments.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("delay_from_purchase_hours", sa.Integer, nullable=False),
        sa.Column("meta_template_name", sa.String(200), nullable=False),
        sa.Column("template_variables", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scheduled_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_followup_enrollment_steps_enrollment_id", "followup_enrollment_steps", ["enrollment_id"])


def downgrade() -> None:
    op.drop_table("followup_enrollment_steps")
    op.drop_table("followup_enrollments")
    op.drop_table("followup_steps")
    op.drop_table("followup_flows")
