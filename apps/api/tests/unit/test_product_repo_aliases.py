from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.product_repo import SqlProductRepository


def _prod(name="P"):
    m = MagicMock()
    m.id = uuid4()
    m.account_id = uuid4()
    m.name = name
    m.hubla_id = "primary"
    m.is_active = True
    m.created_at = None
    m.updated_at = None
    return m


@pytest.mark.asyncio
async def test_resolves_by_primary_first():
    session = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = _prod()
    session.execute = AsyncMock(return_value=r)
    repo = SqlProductRepository(session=session)
    p = await repo.find_active_by_hubla_id(uuid4(), "primary")
    assert p is not None and p.hubla_id == "primary"
    assert session.execute.await_count == 1  # achou no principal, não consulta alias


@pytest.mark.asyncio
async def test_resolves_by_alias_when_primary_misses():
    session = AsyncMock()
    miss = MagicMock()
    miss.scalar_one_or_none.return_value = None
    alias_hit = MagicMock()
    alias_hit.scalar_one_or_none.return_value = _prod()
    session.execute = AsyncMock(side_effect=[miss, alias_hit])
    repo = SqlProductRepository(session=session)
    p = await repo.find_active_by_hubla_id(uuid4(), "offer-id")
    assert p is not None
    assert session.execute.await_count == 2  # principal falhou → consultou alias
