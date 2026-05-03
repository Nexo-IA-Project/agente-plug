# tests/e2e/test_message_flow.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_handle_message_invokes_agent_and_sends_reply():
    fake_session = AsyncMock()
    fake_session_ctx = MagicMock()
    fake_session_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("interface.worker.handlers.message.session_scope", return_value=fake_session_ctx),
        patch(
            "interface.worker.handlers.message.run_agent",
            new_callable=AsyncMock,
            return_value="Olá! Como posso ajudar?",
        ) as mock_run,
        patch(
            "interface.worker.handlers.message.build_registry",
            return_value=MagicMock(),
        ),
        patch(
            "interface.worker.handlers.message.ChatNexoClient",
        ) as mock_chatnexo_cls,
    ):
        mock_chatnexo = AsyncMock()
        mock_chatnexo_cls.return_value = mock_chatnexo

        from interface.worker.handlers.message import handle_message

        await handle_message(
            {
                "account_id": "t1",
                "phone": "5511999990000",
                "conversation_id": "c1",
                "text": "oi",
            }
        )

    mock_run.assert_called_once()
    mock_chatnexo.send_message.assert_called_once_with(
        account_id="t1",
        conversation_id="c1",
        text="Olá! Como posso ajudar?",
    )
