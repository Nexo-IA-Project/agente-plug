"""account_id Integer -> UUID + FK (data-safe) em 7 tabelas

Revision ID: f0a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2026-05-30

down_revision escolhido a partir do único head ativo reportado por
`alembic heads` no momento da escrita (e7f8a9b0c1d2).

Converte ``account_id`` de INTEGER para UUID (FK -> accounts.id) nas tabelas
herdadas do schema pré multi-tenant: users, smtp_config, knowledge_documents,
knowledge_chunks, kb_usage_logs, access_cases, refund_cases.

PRESERVAÇÃO DE DADOS: toda linha existente é backfillada com o UUID da conta
single-tenant (primeira conta criada) ANTES de aplicar NOT NULL. O UUID é
resolvido em Python (SELECT na tabela accounts) e passado por parâmetro — não
dependemos de gen_random_uuid()/extensões. Se nenhuma conta existir, criamos
uma 'Conta Principal' com UUID gerado em Python.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f0a1b2c3d4e5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


# (tabela, [constraints unique a dropar], [indexes a dropar]) — nomes REAIS
# verificados contra o Postgres local via pg_constraint / pg_indexes.
_DROP_UNIQUES = {
    "users": ["uq_users_account_email"],
    "smtp_config": ["smtp_config_account_id_key"],
}
_DROP_INDEXES = {
    "users": ["ix_users_account_id"],
    "access_cases": ["idx_access_cases_account_contact", "ix_access_cases_account_id"],
    "refund_cases": ["idx_refund_cases_account_contact", "ix_refund_cases_account_id"],
    "knowledge_documents": ["idx_knowledge_documents_account"],
    "knowledge_chunks": ["idx_knowledge_chunks_account"],
    "kb_usage_logs": ["idx_kb_usage_logs_account"],
}

_TABLES = [
    "users",
    "smtp_config",
    "knowledge_documents",
    "knowledge_chunks",
    "kb_usage_logs",
    "access_cases",
    "refund_cases",
]


def _resolve_account_uuid(conn) -> uuid.UUID:
    """Retorna o UUID da primeira conta; cria 'Conta Principal' se não houver."""
    row = conn.execute(sa.text("SELECT id FROM accounts ORDER BY created_at LIMIT 1")).first()
    if row is not None:
        return row[0]

    new_id = uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO accounts (id, name, settings, created_at) "
            "VALUES (:id, :name, '{}'::jsonb, NOW())"
        ),
        {"id": str(new_id), "name": "Conta Principal"},
    )
    return new_id


def _convert(conn, table: str, account_uuid: uuid.UUID) -> None:
    # 1. coluna nova nullable
    op.add_column(table, sa.Column("account_uuid", UUID(as_uuid=True), nullable=True))

    # 2. backfill TODAS as linhas com o UUID da conta single-tenant
    conn.execute(
        sa.text(f"UPDATE {table} SET account_uuid = :acc"),
        {"acc": str(account_uuid)},
    )

    # 3. dropar constraints/índices que dependem do account_id integer
    for cons in _DROP_UNIQUES.get(table, []):
        op.drop_constraint(cons, table, type_="unique")
    for idx in _DROP_INDEXES.get(table, []):
        op.drop_index(idx, table_name=table)

    # 4. dropar coluna antiga e renomear a nova
    op.drop_column(table, "account_id")
    op.alter_column(table, "account_uuid", new_column_name="account_id")

    # 5. NOT NULL (seguro: todas as linhas já foram backfilladas)
    op.alter_column(table, "account_id", existing_type=UUID(as_uuid=True), nullable=False)

    # 6. FK -> accounts + índice base
    op.create_foreign_key(
        f"fk_{table}_account_id_accounts", table, "accounts", ["account_id"], ["id"]
    )


# View legada de compat (criada manualmente fora das migrations em alguns ambientes;
# espelha users). Depende de users.account_id, então precisa ser dropada antes do
# DROP COLUMN / ALTER TYPE e recriada depois. IF EXISTS torna idempotente em ambientes
# que não têm a view (ex: testcontainer).
_ADMIN_USERS_VIEW = (
    "CREATE VIEW admin_users AS "
    "SELECT id, account_id, email, password_hash, role, created_at FROM users"
)


def upgrade() -> None:
    conn = op.get_bind()
    account_uuid = _resolve_account_uuid(conn)

    # só recria a view depois se ela JÁ existia (ambientes que têm o shim manual).
    # Em prod ela não existe → não criamos nada inesperado.
    had_view = conn.execute(sa.text("SELECT to_regclass('admin_users') IS NOT NULL")).scalar()
    op.execute("DROP VIEW IF EXISTS admin_users")

    for table in _TABLES:
        _convert(conn, table, account_uuid)

    # 7. recriar índices/uniques (mesmos nomes do schema original)
    op.create_index("ix_users_account_id", "users", ["account_id"])
    op.create_unique_constraint("uq_users_account_email", "users", ["account_id", "email"])

    op.create_unique_constraint("smtp_config_account_id_key", "smtp_config", ["account_id"])

    op.create_index("idx_knowledge_documents_account", "knowledge_documents", ["account_id"])
    op.create_index("idx_knowledge_chunks_account", "knowledge_chunks", ["account_id"])
    op.create_index("idx_kb_usage_logs_account", "kb_usage_logs", ["account_id"])

    op.create_index("ix_access_cases_account_id", "access_cases", ["account_id"])
    op.create_index(
        "idx_access_cases_account_contact", "access_cases", ["account_id", "contact_id"]
    )
    op.create_index("ix_refund_cases_account_id", "refund_cases", ["account_id"])
    op.create_index(
        "idx_refund_cases_account_contact", "refund_cases", ["account_id", "contact_id"]
    )

    # recria a view de compat (agora account_id é uuid) — só se existia antes
    if had_view:
        op.execute(_ADMIN_USERS_VIEW)


def _revert(table: str) -> None:
    # FK e índices criados no upgrade são dropados; a coluna volta a INTEGER.
    op.drop_constraint(f"fk_{table}_account_id_accounts", table, type_="foreignkey")
    op.alter_column(
        table,
        "account_id",
        existing_type=UUID(as_uuid=True),
        type_=sa.Integer(),
        nullable=False,
        server_default="1",
        postgresql_using="1",
    )
    op.alter_column(table, "account_id", server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    had_view = conn.execute(sa.text("SELECT to_regclass('admin_users') IS NOT NULL")).scalar()
    op.execute("DROP VIEW IF EXISTS admin_users")
    # dropar índices/uniques recriados no upgrade
    op.drop_constraint("uq_users_account_email", "users", type_="unique")
    op.drop_index("ix_users_account_id", table_name="users")
    op.drop_constraint("smtp_config_account_id_key", "smtp_config", type_="unique")
    op.drop_index("idx_knowledge_documents_account", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_chunks_account", table_name="knowledge_chunks")
    op.drop_index("idx_kb_usage_logs_account", table_name="kb_usage_logs")
    op.drop_index("idx_access_cases_account_contact", table_name="access_cases")
    op.drop_index("ix_access_cases_account_id", table_name="access_cases")
    op.drop_index("idx_refund_cases_account_contact", table_name="refund_cases")
    op.drop_index("ix_refund_cases_account_id", table_name="refund_cases")

    for table in _TABLES:
        _revert(table)

    # recriar índices/uniques originais (sobre account_id INTEGER)
    op.create_index("ix_users_account_id", "users", ["account_id"])
    op.create_unique_constraint("uq_users_account_email", "users", ["account_id", "email"])
    op.create_unique_constraint("smtp_config_account_id_key", "smtp_config", ["account_id"])
    op.create_index("idx_knowledge_documents_account", "knowledge_documents", ["account_id"])
    op.create_index("idx_knowledge_chunks_account", "knowledge_chunks", ["account_id"])
    op.create_index("idx_kb_usage_logs_account", "kb_usage_logs", ["account_id"])
    op.create_index("ix_access_cases_account_id", "access_cases", ["account_id"])
    op.create_index(
        "idx_access_cases_account_contact", "access_cases", ["account_id", "contact_id"]
    )
    op.create_index("ix_refund_cases_account_id", "refund_cases", ["account_id"])
    op.create_index(
        "idx_refund_cases_account_contact", "refund_cases", ["account_id", "contact_id"]
    )

    # recria a view de compat (account_id de volta a integer) — só se existia antes
    if had_view:
        op.execute(_ADMIN_USERS_VIEW)
