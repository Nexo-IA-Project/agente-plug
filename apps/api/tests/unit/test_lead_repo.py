"""Unit tests for SqlLeadRepository (dataclass + upsert kwargs validation).

Full upsert behavior requires postgres and lives in integration tests.
"""

from unittest.mock import AsyncMock

import pytest

from shared.adapters.db.repositories.lead_repo import SqlLeadRepository


def test_repo_dataclass_initialization():
    session = AsyncMock()
    repo = SqlLeadRepository(session=session)
    assert repo.session is session


@pytest.mark.asyncio
async def test_paginate_with_no_filters_uses_account_filter_only():
    session = AsyncMock()
    # Mock both execute calls (count + paginate)
    count_result = AsyncMock()
    count_result.scalar_one = lambda: 0
    list_result = AsyncMock()
    list_result.scalars = lambda: type("S", (), {"all": lambda *_: []})()

    session.execute = AsyncMock(side_effect=[count_result, list_result])

    from uuid import uuid4

    repo = SqlLeadRepository(session=session)
    items, total = await repo.paginate(uuid4())

    assert items == []
    assert total == 0
    assert session.execute.call_count == 2
