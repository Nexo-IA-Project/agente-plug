"""Integration test: migração c3d4e5f6a7b8 cria platform_config e dropa smtp_config.

Pattern de fixtures: testcontainers Postgres + alembic migrations (igual a
test_scheduler_runner_commit.py). No testcontainer não há dados de seed, então o
backfill insere a linha singleton com valores nulos — isso é esperado e válido.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


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


async def test_platform_config_created_and_smtp_dropped(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        pc_reg = await conn.execute(text("SELECT to_regclass('platform_config')"))
        assert pc_reg.scalar() is not None, "platform_config deveria existir"

        smtp_reg = await conn.execute(text("SELECT to_regclass('smtp_config')"))
        assert smtp_reg.scalar() is None, "smtp_config deveria ter sido dropada"

        count = await conn.execute(text("SELECT COUNT(*) FROM platform_config"))
        assert count.scalar() == 1, "platform_config deveria ter exatamente 1 linha singleton"

        singleton = await conn.execute(text("SELECT singleton FROM platform_config LIMIT 1"))
        assert singleton.scalar() is True


def _run_alembic(database_url: str, direction: str, target: str) -> None:
    """Roda alembic up/down num processo isolado (alembic env usa asyncio.run,
    que não pode rodar dentro do event loop do pytest-asyncio)."""
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    from shared.config.settings import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        if direction == "down":
            command.downgrade(cfg, target)
        else:
            command.upgrade(cfg, target)
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_downgrade_recreates_smtp_then_upgrade_restores(database_url: str) -> None:
    import asyncio

    from shared.adapters.db.session import create_engine

    # downgrade até a head anterior recria smtp_config e remove platform_config.
    _run_alembic(database_url, "down", "a7b8c9d0e1f2")

    async def _assert_downgraded() -> None:
        engine = create_engine(database_url)
        async with engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT to_regclass('smtp_config')"))
            ).scalar() is not None
            assert (
                await conn.execute(text("SELECT to_regclass('platform_config')"))
            ).scalar() is None
        await engine.dispose()

    asyncio.run(_assert_downgraded())

    # upgrade de volta restaura platform_config e dropa smtp_config.
    _run_alembic(database_url, "up", "heads")

    async def _assert_upgraded() -> None:
        engine = create_engine(database_url)
        async with engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT to_regclass('platform_config')"))
            ).scalar() is not None
            assert (await conn.execute(text("SELECT to_regclass('smtp_config')"))).scalar() is None
        await engine.dispose()

    asyncio.run(_assert_upgraded())


def test_upgrade_backfills_openai_from_env_when_tenant_has_none(database_url: str) -> None:
    """Sem key no tenant (testcontainer não tem conta), a migração deve criptografar
    a OPENAI_API_KEY do ambiente com a INTEGRATION_CREDENTIALS_KEY e gravá-la no
    platform_config — para a fonte de verdade passar a ser o banco."""
    import asyncio

    from cryptography.fernet import Fernet

    from shared.adapters.db.session import create_engine

    _run_alembic(database_url, "down", "a7b8c9d0e1f2")

    cred_key = Fernet.generate_key().decode()
    test_openai = "sk-from-env-test-12345"
    prev_openai = os.environ.get("OPENAI_API_KEY")
    prev_cred = os.environ.get("INTEGRATION_CREDENTIALS_KEY")
    os.environ["OPENAI_API_KEY"] = test_openai
    os.environ["INTEGRATION_CREDENTIALS_KEY"] = cred_key
    try:
        _run_alembic(database_url, "up", "heads")
    finally:
        for name, prev in (
            ("OPENAI_API_KEY", prev_openai),
            ("INTEGRATION_CREDENTIALS_KEY", prev_cred),
        ):
            if prev is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = prev

    async def _assert_backfilled() -> None:
        engine = create_engine(database_url)
        async with engine.connect() as conn:
            blob = (
                await conn.execute(text("SELECT openai_api_key FROM platform_config LIMIT 1"))
            ).scalar()
        await engine.dispose()
        assert blob is not None, "openai_api_key deveria ter sido backfillado do env"
        assert Fernet(cred_key.encode()).decrypt(blob.encode()).decode() == test_openai

    asyncio.run(_assert_backfilled())
