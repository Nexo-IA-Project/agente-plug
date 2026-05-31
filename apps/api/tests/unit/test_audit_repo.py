from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.audit_repo import SqlAuditRepository


def test_repo_initializes_with_session():
    session = AsyncMock()
    repo = SqlAuditRepository(session=session)
    assert repo.session is session


@pytest.mark.asyncio
async def test_paginate_returns_empty_list_when_no_events():
    session = AsyncMock()
    count_result = AsyncMock()
    count_result.scalar_one = lambda: 0
    list_result = AsyncMock()
    list_result.scalars = lambda: type("S", (), {"all": lambda *_: []})()
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    repo = SqlAuditRepository(session=session)
    items, total = await repo.paginate(uuid4())

    assert items == []
    assert total == 0
    assert session.execute.call_count == 2
