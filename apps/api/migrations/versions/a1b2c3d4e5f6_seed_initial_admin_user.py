"""seed_initial_admin_user

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-06 00:00:00.000000

Lê ADMIN_EMAIL, ADMIN_PASSWORD e ADMIN_ACCOUNT_ID do ambiente e cria o
usuário admin inicial se ainda não existir. Idempotente.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import bcrypt
from alembic import op
from sqlalchemy import text

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def upgrade() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    account_id = int(os.environ.get("ADMIN_ACCOUNT_ID", "1"))

    if not email or not password:
        return  # variáveis não configuradas — pula silenciosamente

    conn = op.get_bind()

    existing = conn.execute(
        text("SELECT id FROM admin_users WHERE email = :e AND account_id = :a"),
        {"e": email, "a": account_id},
    ).fetchone()

    if existing:
        return  # já existe — idempotente

    conn.execute(
        text(
            "INSERT INTO admin_users (id, account_id, email, password_hash, role, created_at) "
            "VALUES (:id, :account_id, :email, :password_hash, 'admin', :created_at)"
        ),
        {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "email": email,
            "password_hash": _hash(password),
            "created_at": datetime.now(UTC),
        },
    )


def downgrade() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    account_id = int(os.environ.get("ADMIN_ACCOUNT_ID", "1"))

    if not email:
        return

    op.get_bind().execute(
        text("DELETE FROM admin_users WHERE email = :e AND account_id = :a"),
        {"e": email, "a": account_id},
    )
