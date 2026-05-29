from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.product_repo import SqlProductRepository


def _model(name: str):
    m = MagicMock()
    m.id = uuid4()
    m.account_id = uuid4()
    m.name = name
    m.hubla_id = "hub-1"
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    return m


def _session_returning(models: list):
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = models
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_find_active_by_name_returns_single_match():
    session = _session_returning([_model("LE | Loja Express")])
    repo = SqlProductRepository(session=session)
    p = await repo.find_active_by_name(uuid4(), "LE | Loja Express")
    assert p is not None
    assert p.name == "LE | Loja Express"


@pytest.mark.asyncio
async def test_find_active_by_name_none_when_ambiguous():
    # Dois produtos com o mesmo nome → não resolve (evita enrollar no flow errado)
    session = _session_returning([_model("X"), _model("X")])
    repo = SqlProductRepository(session=session)
    assert await repo.find_active_by_name(uuid4(), "X") is None


@pytest.mark.asyncio
async def test_find_active_by_name_none_when_no_match():
    session = _session_returning([])
    repo = SqlProductRepository(session=session)
    assert await repo.find_active_by_name(uuid4(), "Nada") is None


@pytest.mark.asyncio
async def test_find_active_by_name_empty_name_short_circuits():
    session = AsyncMock()
    repo = SqlProductRepository(session=session)
    assert await repo.find_active_by_name(uuid4(), "") is None
    session.execute.assert_not_called()
