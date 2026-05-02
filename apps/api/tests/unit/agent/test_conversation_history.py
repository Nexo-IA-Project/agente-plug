"""Unit tests for ConversationHistory (Task 2) — mocked AsyncSession."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.history import ConversationHistory
from shared.adapters.db.models import ConversationMessageModel


def _mock_session_with_row(row: Any) -> AsyncMock:
    """Return a session mock where execute()'s result.scalar_one_or_none() = row."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _row(messages: list) -> MagicMock:
    row = MagicMock(spec=ConversationMessageModel)
    row.messages = messages
    return row


# ── load ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_returns_empty_list_when_no_row():
    session = _mock_session_with_row(None)
    history = ConversationHistory(session=session)

    result = await history.load("thread-1")

    assert result == []


@pytest.mark.asyncio
async def test_load_returns_stored_messages():
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    session = _mock_session_with_row(_row(msgs))
    history = ConversationHistory(session=session)

    result = await history.load("thread-1")

    assert result == msgs


# ── save ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_calls_execute():
    session = _mock_session_with_row(None)
    history = ConversationHistory(session=session)
    msgs = [{"role": "user", "content": "test"}]

    await history.save("thread-42", msgs)

    session.execute.assert_awaited_once()


# ── clear ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_calls_execute():
    session = _mock_session_with_row(None)
    history = ConversationHistory(session=session)

    await history.clear("thread-42")

    session.execute.assert_awaited_once()
