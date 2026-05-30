"""seed perfis padrão Admin/Operador na conta #1 + atribui aos usuários por role

Revision ID: a7b8c9d0e1f2
Revises: f0a1b2c3d4e5
Create Date: 2026-05-30

Seed idempotente: cria os perfis de sistema "Admin" (todas as permissões do
catálogo) e "Operador" (todas exceto ADMIN_ONLY_KEYS) na primeira conta
(single-tenant) e atribui ``profile_id`` aos usuários existentes pelo ``role``.

NÃO altera enforcement — os guards continuam usando ``users.role``. Esta
migração apenas popula a estrutura RBAC já criada.

O catálogo de permissões é importado de ``shared`` — o env.py do alembic já
adiciona ``src`` ao path e importa de ``shared`` no nível de módulo.
"""

from __future__ import annotations

import uuid as _uuid

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from shared.domain.permissions.catalog import ADMIN_ONLY_KEYS, all_permission_keys

    conn = op.get_bind()
    acc = conn.execute(sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).scalar()
    if acc is None:
        return  # ambiente sem conta: nada a semear (idempotente)

    def ensure_profile(name: str, is_system: bool, keys: list[str]) -> str:
        existing = conn.execute(
            sa.text("SELECT id FROM profiles WHERE account_id=:a AND name=:n"),
            {"a": acc, "n": name},
        ).scalar()
        if existing:
            return str(existing)
        pid = str(_uuid.uuid4())
        conn.execute(
            sa.text("INSERT INTO profiles (id, account_id, name, is_system) VALUES (:i,:a,:n,:s)"),
            {"i": pid, "a": acc, "n": name, "s": is_system},
        )
        for k in keys:
            conn.execute(
                sa.text(
                    "INSERT INTO profile_permissions (id, profile_id, permission_key) "
                    "VALUES (:i,:p,:k)"
                ),
                {"i": str(_uuid.uuid4()), "p": pid, "k": k},
            )
        return pid

    all_keys = list(all_permission_keys())
    operator_keys = [k for k in all_keys if k not in ADMIN_ONLY_KEYS]
    admin_pid = ensure_profile("Admin", True, all_keys)
    operator_pid = ensure_profile("Operador", False, operator_keys)

    conn.execute(
        sa.text("UPDATE users SET profile_id=:p WHERE role='admin' AND profile_id IS NULL"),
        {"p": admin_pid},
    )
    conn.execute(
        sa.text("UPDATE users SET profile_id=:p WHERE role='operator' AND profile_id IS NULL"),
        {"p": operator_pid},
    )


def downgrade() -> None:
    conn = op.get_bind()
    acc = conn.execute(sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).scalar()
    if acc is None:
        return
    conn.execute(
        sa.text(
            "UPDATE users SET profile_id=NULL WHERE profile_id IN "
            "(SELECT id FROM profiles WHERE account_id=:a AND name IN ('Admin','Operador'))"
        ),
        {"a": acc},
    )
    # cascade limpa profile_permissions
    conn.execute(
        sa.text("DELETE FROM profiles WHERE account_id=:a AND name IN ('Admin','Operador')"),
        {"a": acc},
    )
