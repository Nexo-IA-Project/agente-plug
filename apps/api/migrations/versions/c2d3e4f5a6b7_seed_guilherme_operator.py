"""seed operator user guilherme.zanzoti@gmail.com

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-28

"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

# Senha gerada com generate_temp_password() + bcrypt — entregar ao usuário fora do código
_EMAIL = "guilherme.zanzoti@gmail.com"
_NAME = "Guilherme Zanzoti"
_ROLE = "operator"
_HASH = "$2b$12$7LOUtJDmoPuJkO/R07h7pOn.CcuqtqIJxzvhF9fxA/pDZqgz5cqIK"


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email AND account_id = 1"),
        {"email": _EMAIL},
    ).fetchone()
    if existing is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO users
                    (id, account_id, name, email, password_hash, role,
                     must_change_password, is_active, created_at)
                VALUES
                    (:id, 1, :name, :email, :hash, :role,
                     FALSE, TRUE, NOW())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": _NAME,
                "email": _EMAIL,
                "hash": _HASH,
                "role": _ROLE,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE email = :email AND account_id = 1"),
        {"email": _EMAIL},
    )
