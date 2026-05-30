"""Integration test: PlatformConfigRepository — entity + Fernet + upsert parcial.

Pattern de fixtures: testcontainers Postgres + alembic migrations (igual a
test_scheduler_runner_commit.py).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    from shared.config.settings import get_settings

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


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()


@pytest.fixture
def repo(session: AsyncSession) -> PlatformConfigRepository:
    return PlatformConfigRepository(session=session)


async def test_encrypt_decrypt_roundtrip(repo: PlatformConfigRepository) -> None:
    assert repo.decrypt(repo.encrypt("segredo")) == "segredo"


async def test_upsert_and_get(repo: PlatformConfigRepository) -> None:
    encrypted_key = repo.encrypt("sk-test")
    await repo.upsert(
        openai_api_key=encrypted_key,
        smtp_host="smtp.x.com",
        smtp_port=587,
    )
    cfg = await repo.get()

    assert repo.decrypt(cfg.openai_api_key) == "sk-test"
    assert cfg.smtp_host == "smtp.x.com"
    assert cfg.smtp_port == 587


async def test_partial_upsert_preserves_existing_fields(
    engine: AsyncEngine,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    # Primeiro upsert: grava openai_api_key + smtp_host
    async with maker() as s:
        r = PlatformConfigRepository(session=s)
        encrypted_key = r.encrypt("sk-test")
        await r.upsert(openai_api_key=encrypted_key, smtp_host="smtp.x.com", smtp_port=587)
        await s.commit()

    # Segundo upsert: apenas smtp_username — NÃO deve apagar openai_api_key / smtp_host
    async with maker() as s:
        r = PlatformConfigRepository(session=s)
        await r.upsert(smtp_username="u@x.com")
        await s.commit()

    # Verificação em sessão nova
    async with maker() as s:
        r = PlatformConfigRepository(session=s)
        cfg = await r.get()
        assert cfg.smtp_username == "u@x.com"
        assert r.decrypt(cfg.openai_api_key) == "sk-test"
        assert cfg.smtp_host == "smtp.x.com"


async def test_get_on_fresh_migrated_db_does_not_raise(
    repo: PlatformConfigRepository,
) -> None:
    """Banco recém-migrado tem 1 linha singleton (com nulos) — não deve levantar."""
    cfg = await repo.get()
    # Retorna entidade válida; campos podem ser None
    assert cfg is not None
