from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.product_repo import SqlProductRepository


async def _make_account(session: AsyncSession) -> AccountModel:
    account = AccountModel(id=uuid.uuid4(), name="T")
    session.add(account)
    await session.flush()
    return account


@pytest.mark.integration
async def test_create_and_find_by_id(db_session: AsyncSession) -> None:
    account = await _make_account(db_session)
    repo = SqlProductRepository(db_session)
    created = await repo.create(
        account_id=account.id,
        name="Marketing 360",
        hubla_id="prod-mkt-360",
    )
    assert created.id is not None
    found = await repo.find_by_id(created.id)
    assert found is not None
    assert found.name == "Marketing 360"
    assert found.hubla_id == "prod-mkt-360"
    assert found.is_active is True


@pytest.mark.integration
async def test_find_active_by_hubla_id(db_session: AsyncSession) -> None:
    account = await _make_account(db_session)
    repo = SqlProductRepository(db_session)
    await repo.create(account_id=account.id, name="Produto A", hubla_id="A")
    await repo.create(account_id=account.id, name="Produto B", hubla_id="B", is_active=False)

    found = await repo.find_active_by_hubla_id(account.id, "A")
    assert found is not None and found.name == "Produto A"

    inactive = await repo.find_active_by_hubla_id(account.id, "B")
    assert inactive is None


@pytest.mark.integration
async def test_unique_account_hubla_id(db_session: AsyncSession) -> None:
    account = await _make_account(db_session)
    repo = SqlProductRepository(db_session)
    await repo.create(account_id=account.id, name="A", hubla_id="X")
    with pytest.raises(IntegrityError):
        await repo.create(account_id=account.id, name="B", hubla_id="X")


@pytest.mark.integration
async def test_update_partial(db_session: AsyncSession) -> None:
    account = await _make_account(db_session)
    repo = SqlProductRepository(db_session)
    p = await repo.create(account_id=account.id, name="Old", hubla_id="X")
    updated = await repo.update(p.id, name="New")
    assert updated is not None and updated.name == "New" and updated.hubla_id == "X"


@pytest.mark.integration
async def test_delete(db_session: AsyncSession) -> None:
    account = await _make_account(db_session)
    repo = SqlProductRepository(db_session)
    p = await repo.create(account_id=account.id, name="A", hubla_id="X")
    deleted = await repo.delete(p.id)
    assert deleted is True
    assert await repo.find_by_id(p.id) is None
