"""seed_g2_courses

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f7
Create Date: 2026-05-21 00:00:00.000000

Popula a tabela courses com os produtos oficiais da G2 Educação / Guilherme Cirilo.
Idempotente: usa INSERT ... ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import uuid

from alembic import op
from sqlalchemy import text

revision = "c1d2e3f4a5b6"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

_COURSES = [
    ("MVS | Máquina de Vendas: Shopee", "QaIlGtff9tlU94JjDKSq"),
    ("Comunidade Maverick Pro", "DVdGuF8RwSKYDYnJvao1"),
    ("LE | Loja Express", "mHfbJg3hAf0juI6IXJ0F"),
    ("Escola de Anúncios: Shopee", "XqPpW3fbh5VfW4XpzlwF"),
    ("MVML | Máquina de Vendas: Mercado Livre", "YTZi3Zr9b2ekuXuL3DG2"),
    ("Programa de Aceleração & Escala", "oy7iKOItf8lE6R27k869"),
    ("Black Marketplace Vitalício", "wiK0PWNsy6pgKta7STSL"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Busca o primeiro account_id disponível (single-tenant na prática)
    row = conn.execute(text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).fetchone()
    if row is None:
        return  # nenhuma conta ainda — pula silenciosamente

    account_id = str(row[0])

    for name, hubla_id in _COURSES:
        conn.execute(
            text(
                "INSERT INTO courses (id, account_id, name, hubla_id, is_active, created_at, updated_at) "
                "VALUES (:id, :account_id, :name, :hubla_id, true, NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_courses_account_hubla DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "account_id": account_id,
                "name": name,
                "hubla_id": hubla_id,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    hubla_ids = [hubla_id for _, hubla_id in _COURSES]
    conn.execute(
        text("DELETE FROM courses WHERE hubla_id = ANY(:ids)"),
        {"ids": hubla_ids},
    )
