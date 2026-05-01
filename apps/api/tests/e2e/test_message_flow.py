# tests/e2e/test_message_flow.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


@pytest.mark.asyncio
async def test_handle_message_invokes_agent_and_sends_reply():
    fake_agent = AsyncMock()
    fake_agent.ainvoke.return_value = {
        "messages": [AIMessage("Olá! Como posso ajudar?")]
    }
    fake_dispatcher = AsyncMock()

    with (
        patch("nexoia.interface.worker.handlers.message._get_agent", return_value=fake_agent),
        patch("nexoia.interface.worker.handlers.message._get_dispatcher", return_value=fake_dispatcher),
        patch("nexoia.interface.worker.handlers.message._get_lifecycle", return_value=AsyncMock()),
        patch("nexoia.interface.worker.handlers.message._get_scheduler", return_value=AsyncMock()),
    ):
        from nexoia.interface.worker.handlers.message import handle_message
        await handle_message({
            "account_id": "t1",
            "phone": "5511999990000",
            "conversation_id": "c1",
            "chatnexo_message_id": "msg-1",
            "text": "oi",
        })

    fake_agent.ainvoke.assert_called_once()
    fake_dispatcher.send.assert_called_once()
