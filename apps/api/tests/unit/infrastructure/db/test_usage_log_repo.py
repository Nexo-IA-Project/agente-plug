# tests/unit/infrastructure/db/test_usage_log_repo.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.db.repositories.usage_log_repo import UsageLogRepository


@pytest.mark.asyncio
async def test_record_no_result_flushes():
    session = AsyncMock()
    session.add = MagicMock()  # synchronous in AsyncSession
    repo = UsageLogRepository(session)
    await repo.record_no_result(account_id=1, query="how to get refund?")
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_recent_returns_list_of_dicts():
    session = AsyncMock()
    from shared.adapters.db.models import KbUsageLogModel

    log = KbUsageLogModel(
        id="log-1",
        account_id=1,
        query="test query",
        result_count=0,
        created_at=datetime.now(UTC),
    )
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[log])))
        )
    )
    repo = UsageLogRepository(session)
    result = await repo.list_recent(account_id=1, limit=10)
    assert len(result) == 1
    assert result[0]["query"] == "test query"
    assert result[0]["account_id"] == 1
