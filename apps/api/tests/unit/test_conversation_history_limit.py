"""Unit tests for ConversationHistory.load(limit=...)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.history import ConversationHistory


def _fake_session(stored_messages):
    session = MagicMock()
    row = MagicMock()
    row.messages = stored_messages
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.mark.asyncio
async def test_load_with_limit_returns_only_last_n():
    msgs = [{"role": "user", "content": f"m{i}"} for i in range(50)]
    session = _fake_session(msgs)
    history = ConversationHistory(session=session)
    result = await history.load("t1", limit=10)
    assert len(result) == 10
    assert result[0]["content"] == "m40"
    assert result[-1]["content"] == "m49"


@pytest.mark.asyncio
async def test_load_without_limit_returns_all():
    msgs = [{"role": "user", "content": "m"}] * 50
    session = _fake_session(msgs)
    history = ConversationHistory(session=session)
    result = await history.load("t1")
    assert len(result) == 50


@pytest.mark.asyncio
async def test_load_with_limit_larger_than_messages_returns_all():
    msgs = [{"role": "user", "content": "m"}] * 5
    session = _fake_session(msgs)
    history = ConversationHistory(session=session)
    result = await history.load("t1", limit=20)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_load_returns_empty_when_no_row():
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    history = ConversationHistory(session=session)
    assert await history.load("t1", limit=10) == []
