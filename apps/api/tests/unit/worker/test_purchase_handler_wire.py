# tests/unit/worker/test_purchase_handler_wire.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_handle_purchase_delegates_to_hubla_event_handler():
    """Verifica que handle_purchase delega para handle_hubla_event (pipeline unificado)."""
    mock_handle_hubla_event = AsyncMock(return_value=None)

    payload = {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {
            "product": {"id": "prod-mentoria", "name": "Mentoria"},
            "products": [{"id": "prod-mentoria", "name": "Mentoria"}],
            "subscription": {
                "id": "p-1",
                "payer": {
                    "firstName": "João",
                    "lastName": "",
                    "document": "00000000000",
                    "email": "joao@test.com",
                    "phone": "5511999990000",
                },
                "activatedAt": "2026-04-24T00:00:00Z",
            },
        },
    }

    with patch(
        "interface.worker.handlers.purchase.handle_hubla_event",
        mock_handle_hubla_event,
    ):
        from interface.worker.handlers.purchase import handle_purchase

        await handle_purchase(payload)

    mock_handle_hubla_event.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_handle_purchase_synthesizes_type_when_missing():
    """Se o payload legado não tiver 'type', sintetiza 'subscription.activated'."""
    mock_handle_hubla_event = AsyncMock(return_value=None)

    payload_without_type = {
        "version": "2.0.0",
        "event": {"product": {"id": "prod-1", "name": "Prod"}, "subscription": {"id": "s-1"}},
    }

    with patch(
        "interface.worker.handlers.purchase.handle_hubla_event",
        mock_handle_hubla_event,
    ):
        from interface.worker.handlers.purchase import handle_purchase

        await handle_purchase(payload_without_type)

    called_payload = mock_handle_hubla_event.call_args[0][0]
    assert called_payload["type"] == "subscription.activated"


@pytest.mark.asyncio
async def test_handle_scheduled_idle_ping_calls_lifecycle():
    mock_lifecycle = AsyncMock()
    with patch(
        "interface.worker.handlers.scheduled._get_lifecycle_handler",
        return_value=mock_lifecycle,
    ):
        from interface.worker.handlers.scheduled import handle_scheduled

        await handle_scheduled(
            {
                "job_type": "IDLE_PING",
                "account_id": "t1",
                "phone": "5511999990000",
                "conversation_id": "c1",
            }
        )
    mock_lifecycle.send_ping.assert_called_once()
