"""Integration test: ProfileRepository — entity + dedup de permissões."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.profile_repo import ProfileRepository


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


async def test_create_dedup_get_list(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc_id = uuid.uuid4()

    # conta própria com uuid único por run; as asserções abaixo são scoped por
    # account_id, então não limpamos tabelas (deletar accounts violaria a FK nova
    # users.account_id → accounts).
    async with maker() as s:
        s.add(AccountModel(id=acc_id, name="t"))
        await s.commit()

    # create: dedup de permissões (a.x duplicado)
    async with maker() as s:
        repo = ProfileRepository(s)
        profile = await repo.create(
            account_id=acc_id,
            name="Admin",
            is_system=True,
            permissions=["a.x", "b.y", "a.x"],
        )
        await s.commit()

    assert profile.name == "Admin"
    assert profile.is_system is True
    assert profile.permissions == ["a.x", "b.y"]

    # get_by_name: encontra o profile com as 2 permissões
    async with maker() as s:
        repo = ProfileRepository(s)
        found = await repo.get_by_name(acc_id, "Admin")

    assert found is not None
    assert found.id == profile.id
    assert set(found.permissions) == {"a.x", "b.y"}

    # get_by_name: nome inexistente retorna None
    async with maker() as s:
        repo = ProfileRepository(s)
        missing = await repo.get_by_name(acc_id, "Nao existe")

    assert missing is None

    # list_by_account: retorna 1 profile
    async with maker() as s:
        repo = ProfileRepository(s)
        profiles = await repo.list_by_account(acc_id)

    assert len(profiles) == 1
    assert profiles[0].id == profile.id
