# tests/unit/worker/test_purchase_handler_wire.py
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_handle_purchase_calls_purchase_handler():
    """Verifica que handle_purchase constrói PurchaseHandler e chama execute."""
    mock_account_config = MagicMock()
    mock_account_config.integration.chatnexo_base_url = "http://fake"
    mock_account_config.integration.chatnexo_api_key = "fake-key"

    @asynccontextmanager
    async def _fake_session_scope():
        yield AsyncMock()

    mock_handler_instance = AsyncMock()
    mock_handler_instance.execute = AsyncMock(return_value=None)

    with (
        patch("interface.worker.handlers.purchase.session_scope", _fake_session_scope),
        patch("interface.worker.handlers.purchase.get_settings", return_value=MagicMock(
            integration_credentials_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        )),
        patch("interface.worker.handlers.purchase.AccountConfigRepository") as MockConfigRepo,
        patch("interface.worker.handlers.purchase.PurchaseHandler", return_value=mock_handler_instance),
        patch("interface.worker.handlers.purchase.ChatNexoClient") as MockChatNexo,
        patch("interface.worker.handlers.purchase.ContactRepository"),
        patch("interface.worker.handlers.purchase.AccessCaseRepository"),
        patch("interface.worker.handlers.purchase.ScheduledJobRepository"),
        patch("interface.worker.handlers.purchase.LojaExpressCaseRepository"),
        patch("interface.worker.handlers.purchase.FollowupFlowRepository"),
        patch("interface.worker.handlers.purchase.FollowupEnrollmentRepository"),
        patch("interface.worker.handlers.purchase.CriarCasoLojaExpress"),
        patch("interface.worker.handlers.purchase.EnrollContact"),
        patch("interface.worker.handlers.purchase.LojaExpressStubClient"),
        patch("interface.worker.handlers.purchase.Fernet"),
    ):
        MockConfigRepo.return_value.get = AsyncMock(return_value=mock_account_config)
        MockChatNexo.from_account_config.return_value = AsyncMock()

        from interface.worker.handlers.purchase import handle_purchase

        await handle_purchase(
            {
                "purchase_id": "p-1",
                "account_id": "00000000-0000-0000-0000-000000000001",
                "contact_name": "João",
                "contact_email": "joao@test.com",
                "contact_phone": "5511999990000",
                "product": "Mentoria",
                "amount_brl": 49700,
                "occurred_at": "2026-04-24T00:00:00+00:00",
            }
        )
    mock_handler_instance.execute.assert_called_once()


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
