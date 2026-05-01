# tests/unit/worker/test_purchase_handler_wire.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_purchase_calls_purchase_handler():
    mock_handler = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.purchase._get_purchase_handler",
        return_value=mock_handler,
    ):
        from interface.worker.handlers.purchase import handle_purchase
        await handle_purchase({
            "purchase_id": "p-1",
            "account_id": "00000000-0000-0000-0000-000000000001",
            "contact_name": "João",
            "contact_email": "joao@test.com",
            "contact_phone": "5511999990000",
            "product": "Mentoria",
            "amount_brl": 49700,
            "occurred_at": "2026-04-24T00:00:00+00:00",
        })
    mock_handler.execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_scheduled_idle_ping_calls_lifecycle():
    mock_lifecycle = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_lifecycle_handler",
        return_value=mock_lifecycle,
    ):
        from interface.worker.handlers.scheduled import handle_scheduled
        await handle_scheduled({
            "job_type": "IDLE_PING",
            "account_id": "t1",
            "phone": "5511999990000",
            "conversation_id": "c1",
        })
    mock_lifecycle.send_ping.assert_called_once()
