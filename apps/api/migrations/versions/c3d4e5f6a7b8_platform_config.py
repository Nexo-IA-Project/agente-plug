"""create platform_config (singleton) + backfill openai/smtp, drop smtp_config

Revision ID: c3d4e5f6a7b8
Revises: a7b8c9d0e1f2
Create Date: 2026-05-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import json
    import uuid as _uuid

    conn = op.get_bind()

    op.create_table(
        "platform_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.true(), unique=True),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        sa.Column("smtp_encrypted_password", sa.Text(), nullable=True),
        sa.Column("smtp_from_name", sa.String(255), nullable=True),
        sa.Column("smtp_from_email", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Backfill OpenAI: accounts.settings.integration.openai_api_key da 1ª conta.
    # O blob Fernet é copiado COMO ESTÁ (sem re-encriptar).
    acc = conn.execute(
        sa.text("SELECT settings FROM accounts ORDER BY created_at LIMIT 1")
    ).scalar()
    openai = None
    if acc:
        settings = acc if isinstance(acc, dict) else json.loads(acc)
        openai = (settings.get("integration") or {}).get("openai_api_key") or None

    # Backfill SMTP: única linha de smtp_config, se houver.
    smtp = (
        conn.execute(
            sa.text(
                "SELECT host, port, use_tls, username, encrypted_password, "
                "from_name, from_email FROM smtp_config LIMIT 1"
            )
        )
        .mappings()
        .first()
    )

    pid = str(_uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO platform_config (id, singleton, openai_api_key, smtp_host, "
            "smtp_port, smtp_use_tls, smtp_username, smtp_encrypted_password, "
            "smtp_from_name, smtp_from_email) "
            "VALUES (:id, TRUE, :ok, :h, :p, :tls, :u, :pw, :fn, :fe)"
        ),
        {
            "id": pid,
            "ok": openai,
            "h": smtp["host"] if smtp else None,
            "p": smtp["port"] if smtp else None,
            "tls": smtp["use_tls"] if smtp else True,
            "u": smtp["username"] if smtp else None,
            "pw": smtp["encrypted_password"] if smtp else None,
            "fn": smtp["from_name"] if smtp else None,
            "fe": smtp["from_email"] if smtp else None,
        },
    )

    # Remove openai_api_key do accounts.settings (todas as contas).
    conn.execute(
        sa.text("UPDATE accounts SET settings = settings #- '{integration,openai_api_key}'")
    )

    # Dados já migrados; downgrade recria.
    op.drop_table("smtp_config")


def downgrade() -> None:
    import uuid as _uuid

    conn = op.get_bind()

    # Recria smtp_config no estado em que esta migração a encontrou: account_id
    # UUID (resultado de f0a1b2c3d4e5, que roda antes desta na cadeia). Os nomes
    # de constraint precisam casar EXATAMENTE com os que o downgrade de
    # f0a1b2c3d4e5 espera dropar (fk_smtp_config_account_id_accounts e
    # smtp_config_account_id_key), senão a cadeia de rollback quebra.
    op.create_table(
        "smtp_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("host", sa.String(200), nullable=False),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("encrypted_password", sa.Text, nullable=False),
        sa.Column("use_tls", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("from_name", sa.String(100), nullable=False),
        sa.Column("from_email", sa.String(200), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_smtp_config_account_id_accounts"
        ),
        sa.UniqueConstraint("account_id", name="smtp_config_account_id_key"),
    )

    pc = (
        conn.execute(
            sa.text(
                "SELECT openai_api_key, smtp_host, smtp_port, smtp_use_tls, "
                "smtp_username, smtp_encrypted_password, smtp_from_name, smtp_from_email "
                "FROM platform_config LIMIT 1"
            )
        )
        .mappings()
        .first()
    )

    account_id = conn.execute(
        sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")
    ).scalar()

    # Restaura a linha de smtp_config (só se havia SMTP configurado e há conta).
    if pc and account_id is not None and pc["smtp_host"] is not None:
        conn.execute(
            sa.text(
                "INSERT INTO smtp_config (id, account_id, host, port, username, "
                "encrypted_password, use_tls, from_name, from_email) "
                "VALUES (:id, :acc, :h, :p, :u, :pw, :tls, :fn, :fe)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "acc": account_id,
                "h": pc["smtp_host"],
                "p": pc["smtp_port"],
                "u": pc["smtp_username"] or "",
                "pw": pc["smtp_encrypted_password"] or "",
                "tls": pc["smtp_use_tls"],
                "fn": pc["smtp_from_name"] or "",
                "fe": pc["smtp_from_email"] or "",
            },
        )

    # Re-grava openai_api_key em accounts.settings.integration da 1ª conta.
    if pc and account_id is not None and pc["openai_api_key"]:
        conn.execute(
            sa.text(
                "UPDATE accounts SET settings = "
                "jsonb_set("
                "  COALESCE(settings, '{}'::jsonb), "
                "  '{integration,openai_api_key}', "
                "  to_jsonb(CAST(:ok AS text)), "
                "  true"
                ") WHERE id = :acc"
            ),
            {"ok": pc["openai_api_key"], "acc": account_id},
        )

    op.drop_table("platform_config")
