"""Integration: migração account_id Integer -> UUID + FK (f0a1b2c3d4e5).

Verifica que após `alembic upgrade heads`:
- account_id é UUID em users/smtp_config/knowledge_documents/knowledge_chunks/
  kb_usage_logs/access_cases/refund_cases.
- Existe FK fk_<tabela>_account_id_accounts -> accounts(id).
- Os uniques originais (uq_users_account_email, smtp_config_account_id_key)
  foram recriados.
- A migração é reversível: downgrade -1 + upgrade heads não falha e termina
  novamente como uuid.

Estratégia: testcontainers (postgres pgvector) + alembic command.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_UUID_TABLES = [
    "users",
    "smtp_config",
    "knowledge_documents",
    "knowledge_chunks",
    "kb_usage_logs",
    "access_cases",
    "refund_cases",
]


def _alembic_cfg(database_url: str):
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    from shared.config.settings import get_settings

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command

        command.upgrade(_alembic_cfg(database_url), "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


async def _column_type(session: AsyncSession, table: str) -> str | None:
    result = await session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'account_id'"
        ),
        {"t": table},
    )
    return result.scalar_one_or_none()


@pytest.mark.integration
@pytest.mark.parametrize("table", _UUID_TABLES)
async def test_account_id_is_uuid(db_session: AsyncSession, table: str) -> None:
    assert await _column_type(db_session, table) == "uuid"


@pytest.mark.integration
@pytest.mark.parametrize("table", _UUID_TABLES)
async def test_account_id_has_fk_to_accounts(db_session: AsyncSession, table: str) -> None:
    result = await db_session.execute(
        text(
            "SELECT confrelid::regclass::text "
            "FROM pg_constraint "
            "WHERE conname = :name AND contype = 'f'"
        ),
        {"name": f"fk_{table}_account_id_accounts"},
    )
    assert result.scalar_one_or_none() == "accounts"


@pytest.mark.integration
async def test_uniques_recreated(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conname IN ('uq_users_account_email', 'smtp_config_account_id_key') "
            "ORDER BY conname"
        )
    )
    names = {row[0] for row in result.fetchall()}
    assert names == {"smtp_config_account_id_key", "uq_users_account_email"}


@pytest.mark.integration
async def test_migration_is_reversible(database_url: str, db_session: AsyncSession) -> None:
    """Reverte a migração de account_id (→ INTEGER) e re-aplica (→ uuid).

    Desce até a revisão ANTERIOR à conversão de account_id (`e7f8a9b0c1d2`, a de
    profiles) — não dá pra usar "-1" porque o head agora é a migração de seed, que
    fica acima da conversão de account_id.

    Os comandos do alembic rodam o env.py async via asyncio.run(), que não pode
    ser chamado de dentro do event loop do pytest-asyncio — por isso despachamos
    cada comando numa thread separada.
    """
    import asyncio

    from alembic import command

    # revisão imediatamente anterior à migração account_id→UUID (f0a1b2c3d4e5)
    before_account_uuid = "e7f8a9b0c1d2"

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    cfg = _alembic_cfg(database_url)
    try:
        await asyncio.to_thread(command.downgrade, cfg, before_account_uuid)
        # após downgrade, account_id deve ser integer novamente
        assert await _column_type(db_session, "users") == "integer"
        assert await _column_type(db_session, "smtp_config") == "integer"

        await asyncio.to_thread(command.upgrade, cfg, "heads")
        # de volta para uuid
        assert await _column_type(db_session, "users") == "uuid"
        assert await _column_type(db_session, "knowledge_documents") == "uuid"
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
