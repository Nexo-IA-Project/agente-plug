from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.message_dispatcher import MessageDispatcher


def fake_conv(within_window: bool):
    conv = MagicMock()
    if within_window:
        conv.window_expires_at = datetime.now(UTC) + timedelta(hours=1)
    else:
        conv.window_expires_at = datetime.now(UTC) - timedelta(hours=1)
    return conv


@pytest.mark.asyncio
async def test_sends_free_text_within_24h_window():
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    conv_repo.find_by_chatnexo_id.return_value = fake_conv(within_window=True)
    dispatcher = MessageDispatcher(chatnexo=chatnexo, conversation_repo=conv_repo)
    await dispatcher.send(account_id="t1", conversation_id="c1", content="Olá!")
    chatnexo.send_message.assert_called_once()
    chatnexo.send_template.assert_not_called()


@pytest.mark.asyncio
async def test_sends_template_outside_24h_window():
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    conv_repo.find_by_chatnexo_id.return_value = fake_conv(within_window=False)
    dispatcher = MessageDispatcher(chatnexo=chatnexo, conversation_repo=conv_repo)
    await dispatcher.send(account_id="t1", conversation_id="c1", content="Olá!")
    chatnexo.send_template.assert_called_once()
    chatnexo.send_message.assert_not_called()
