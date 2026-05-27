"""step delay relative and position one indexed

Revision ID: 9f07c98d5b22
Revises: 5a315d3321ab
Create Date: 2026-05-27

Renomeia delay_from_purchase_minutes → delay_from_previous_minutes em
onboarding_steps e onboarding_enrollment_steps, convertendo valores absolutos
em relativos (diff do step anterior). Também migra position 0-indexed → 1-indexed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9f07c98d5b22"
down_revision = "5a315d3321ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Adiciona coluna nova com default 0
    op.add_column(
        "onboarding_steps",
        sa.Column(
            "delay_from_previous_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column(
            "delay_from_previous_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    conn = op.get_bind()

    # 2. Converte absolutos em relativos (por parent_id, ordenado por position)
    for table, parent_col in (
        ("onboarding_steps", "flow_id"),
        ("onboarding_enrollment_steps", "enrollment_id"),
    ):
        rows = conn.execute(
            sa.text(
                f"SELECT id, {parent_col}, position, delay_from_purchase_minutes "
                f"FROM {table} ORDER BY {parent_col}, position"
            )
        ).fetchall()
        prev_by_parent: dict = {}
        for r in rows:
            parent = getattr(r, parent_col)
            prev = prev_by_parent.get(parent, 0)
            relative = max(0, r.delay_from_purchase_minutes - prev)
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET delay_from_previous_minutes = :rel WHERE id = :id"
                ),
                {"rel": relative, "id": r.id},
            )
            prev_by_parent[parent] = r.delay_from_purchase_minutes

    # 3. Corrige position zero-indexed em flows/enrollments que ainda têm position=0
    conn.execute(
        sa.text(
            """
            UPDATE onboarding_steps SET position = position + 1
            WHERE flow_id IN (
                SELECT DISTINCT flow_id FROM onboarding_steps WHERE position = 0
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE onboarding_enrollment_steps SET position = position + 1
            WHERE enrollment_id IN (
                SELECT DISTINCT enrollment_id FROM onboarding_enrollment_steps WHERE position = 0
            )
            """
        )
    )

    # 4. Dropa coluna antiga
    op.drop_column("onboarding_steps", "delay_from_purchase_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_purchase_minutes")


def downgrade() -> None:
    # 1. Recria coluna antiga
    op.add_column(
        "onboarding_steps",
        sa.Column(
            "delay_from_purchase_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column(
            "delay_from_purchase_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    conn = op.get_bind()

    # 2. Reconstrói absoluto via soma cumulativa
    for table, parent_col in (
        ("onboarding_steps", "flow_id"),
        ("onboarding_enrollment_steps", "enrollment_id"),
    ):
        rows = conn.execute(
            sa.text(
                f"SELECT id, {parent_col}, position, delay_from_previous_minutes "
                f"FROM {table} ORDER BY {parent_col}, position"
            )
        ).fetchall()
        cumulative_by_parent: dict = {}
        for r in rows:
            parent = getattr(r, parent_col)
            cum = cumulative_by_parent.get(parent, 0) + r.delay_from_previous_minutes
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET delay_from_purchase_minutes = :abs WHERE id = :id"
                ),
                {"abs": cum, "id": r.id},
            )
            cumulative_by_parent[parent] = cum

    # 3. Reverte position (1-indexed → 0-indexed)
    conn.execute(sa.text("UPDATE onboarding_steps SET position = position - 1 WHERE position > 0"))
    conn.execute(
        sa.text("UPDATE onboarding_enrollment_steps SET position = position - 1 WHERE position > 0")
    )

    op.drop_column("onboarding_steps", "delay_from_previous_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_previous_minutes")
