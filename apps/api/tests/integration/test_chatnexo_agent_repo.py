"""Testes de integração: ChatNexoAgentRepository."""

from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel, ChatNexoAgentModel
from shared.adapters.db.repositories.chatnexo_agent_repo import ChatNexoAgentRepository
from shared.config.single_tenant import get_default_account_uuid, reset_cache

# ──────────────────────────────────────────────────────────────
# Migrations no testcontainer (autouse session-scope)
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão."""
    import os

    from shared.config.settings import get_settings

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def fernet() -> Fernet:
    return Fernet(Fernet.generate_key())


@pytest.fixture(autouse=True)
async def _clean_db(db_session: AsyncSession) -> None:
    """Limpa tabelas relevantes antes de cada teste."""
    await db_session.execute(delete(ChatNexoAgentModel))
    await db_session.execute(delete(AccountModel))
    await db_session.commit()
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
async def seed_account(db_session: AsyncSession) -> AccountModel:
    account = AccountModel(id=uuid.uuid4(), name="T")
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()
    return account


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_create_and_list_agent(
    db_session: AsyncSession, fernet: Fernet, seed_account: AccountModel
) -> None:
    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Ana", api_key="raw-key-123")
    assert agent.name == "Ana"
    assert agent.api_key == "raw-key-123"
    assert agent.is_active is True

    agents = await repo.list_active(account_id)
    found = [a for a in agents if a.name == "Ana"]
    assert len(found) == 1
    assert found[0].api_key == "raw-key-123"


@pytest.mark.integration
async def test_delete_agent(
    db_session: AsyncSession, fernet: Fernet, seed_account: AccountModel
) -> None:
    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Bob", api_key="key-bob")
    await repo.delete(id=agent.id, account_id=account_id)

    agents = await repo.list_active(account_id)
    assert all(a.id != agent.id for a in agents)


@pytest.mark.integration
async def test_update_agent_name(
    db_session: AsyncSession, fernet: Fernet, seed_account: AccountModel
) -> None:
    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Carol", api_key="key-carol")
    updated = await repo.update(id=agent.id, account_id=account_id, name="Carolina", api_key=None)
    assert updated.name == "Carolina"
    assert updated.api_key == "key-carol"
