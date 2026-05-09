"""Dynamic follow-up by course

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-05-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Cria courses
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hubla_id", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_courses_account_hubla"),
    )
    op.create_index("ix_courses_account_id", "courses", ["account_id"])

    # 2. Limpa dados de follow-up (rasgar e recriar)
    op.execute("DELETE FROM followup_enrollment_steps")
    op.execute("DELETE FROM followup_enrollments")
    op.execute("DELETE FROM followup_steps")
    op.execute("DELETE FROM followup_flows")

    # 3. Ajusta followup_flows
    op.add_column(
        "followup_flows",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_followup_flows_course_id",
        "followup_flows", "courses",
        ["course_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_followup_flows_course_id", "followup_flows", ["course_id"])
    op.drop_column("followup_flows", "product_tags")
    op.drop_column("followup_flows", "position")

    # 4. Snapshots em followup_enrollments
    op.add_column(
        "followup_enrollments",
        sa.Column("customer_name", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column(
        "followup_enrollments",
        sa.Column("product_name", sa.String(200), nullable=False, server_default=""),
    )
    op.alter_column("followup_enrollments", "customer_name", server_default=None)
    op.alter_column("followup_enrollments", "product_name", server_default=None)

    # 5. Drop loja_express_cases
    op.drop_table("loja_express_cases")


def downgrade() -> None:
    # Recria loja_express_cases (schema mínimo — dados não voltam)
    op.create_table(
        "loja_express_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("purchase_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
    )

    # Reverte enrollments
    op.drop_column("followup_enrollments", "product_name")
    op.drop_column("followup_enrollments", "customer_name")

    # Reverte followup_flows
    op.add_column(
        "followup_flows",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "followup_flows",
        sa.Column("product_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.drop_index("ix_followup_flows_course_id", table_name="followup_flows")
    op.drop_constraint("fk_followup_flows_course_id", "followup_flows", type_="foreignkey")
    op.drop_column("followup_flows", "course_id")

    # Drop courses
    op.drop_index("ix_courses_account_id", table_name="courses")
    op.drop_table("courses")
