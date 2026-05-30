"""Integration test: ProfileRepository — entity + dedup de permissões."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.db.models import AccountModel, UserModel
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


async def test_get_by_id(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc_id = uuid.uuid4()
    other_acc_id = uuid.uuid4()

    async with maker() as s:
        s.add(AccountModel(id=acc_id, name="t"))
        s.add(AccountModel(id=other_acc_id, name="o"))
        await s.commit()

    async with maker() as s:
        repo = ProfileRepository(s)
        profile = await repo.create(
            account_id=acc_id, name="Editor", is_system=False, permissions=["a.x", "b.y"]
        )
        await s.commit()

    # get_by_id: existente retorna com permissions
    async with maker() as s:
        repo = ProfileRepository(s)
        found = await repo.get_by_id(acc_id, profile.id)

    assert found is not None
    assert found.id == profile.id
    assert set(found.permissions) == {"a.x", "b.y"}

    # get_by_id: id inexistente → None
    async with maker() as s:
        repo = ProfileRepository(s)
        missing = await repo.get_by_id(acc_id, uuid.uuid4())
    assert missing is None

    # get_by_id: existe mas em outro account → None (scoped)
    async with maker() as s:
        repo = ProfileRepository(s)
        wrong_account = await repo.get_by_id(other_acc_id, profile.id)
    assert wrong_account is None


async def test_update(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc_id = uuid.uuid4()

    async with maker() as s:
        s.add(AccountModel(id=acc_id, name="t"))
        await s.commit()

    async with maker() as s:
        repo = ProfileRepository(s)
        profile = await repo.create(
            account_id=acc_id, name="Suporte", is_system=False, permissions=["a.x", "b.y"]
        )
        await s.commit()

    # update: troca name e substitui permissions por [c.z]
    async with maker() as s:
        repo = ProfileRepository(s)
        updated = await repo.update(
            account_id=acc_id,
            profile_id=profile.id,
            name="Suporte N2",
            permissions=["c.z"],
        )
        await s.commit()

    assert updated is not None
    assert updated.name == "Suporte N2"
    assert updated.permissions == ["c.z"]

    # get_by_id reflete só [c.z]
    async with maker() as s:
        repo = ProfileRepository(s)
        found = await repo.get_by_id(acc_id, profile.id)
    assert found is not None
    assert found.name == "Suporte N2"
    assert found.permissions == ["c.z"]

    # update de profile inexistente → None
    async with maker() as s:
        repo = ProfileRepository(s)
        missing = await repo.update(
            account_id=acc_id, profile_id=uuid.uuid4(), name="X", permissions=[]
        )
    assert missing is None


async def test_delete(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc_id = uuid.uuid4()

    async with maker() as s:
        s.add(AccountModel(id=acc_id, name="t"))
        await s.commit()

    async with maker() as s:
        repo = ProfileRepository(s)
        profile = await repo.create(
            account_id=acc_id, name="Temp", is_system=False, permissions=["a.x"]
        )
        await s.commit()

    # delete: existente → True
    async with maker() as s:
        repo = ProfileRepository(s)
        ok = await repo.delete(acc_id, profile.id)
        await s.commit()
    assert ok is True

    # some de fato
    async with maker() as s:
        repo = ProfileRepository(s)
        found = await repo.get_by_id(acc_id, profile.id)
    assert found is None

    # delete: inexistente → False
    async with maker() as s:
        repo = ProfileRepository(s)
        ok = await repo.delete(acc_id, uuid.uuid4())
    assert ok is False


async def test_list_with_counts(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc_id = uuid.uuid4()

    async with maker() as s:
        s.add(AccountModel(id=acc_id, name="t"))
        await s.commit()

    async with maker() as s:
        repo = ProfileRepository(s)
        profile = await repo.create(
            account_id=acc_id, name="Gestor", is_system=False, permissions=["a.x", "b.y"]
        )
        await s.commit()

    # 1 user apontando para o profile
    async with maker() as s:
        s.add(
            UserModel(
                id=str(uuid.uuid4()),
                account_id=acc_id,
                name="User One",
                email="u1@example.com",
                password_hash="x",
                role="operator",
                profile_id=profile.id,
            )
        )
        await s.commit()

    async with maker() as s:
        repo = ProfileRepository(s)
        rows = await repo.list_with_counts(acc_id)

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == profile.id
    assert row["name"] == "Gestor"
    assert row["is_system"] is False
    assert row["permission_count"] == 2
    assert row["user_count"] == 1
