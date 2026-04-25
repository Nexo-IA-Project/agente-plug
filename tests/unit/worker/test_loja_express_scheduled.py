# tests/unit/worker/test_loja_express_scheduled.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_scheduled_loja_express_d1_calls_followup_day_1():
    mock_followup = AsyncMock()
    mock_followup.execute = AsyncMock(return_value="FOLLOWUP_D1: template enviado")
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_followup_handler",
        return_value=mock_followup,
    ), patch(
        "nexoia.interface.worker.handlers.scheduled._get_lifecycle_handler",
        return_value=AsyncMock(),
    ):
        from nexoia.interface.worker.handlers.scheduled import handle_scheduled
        await handle_scheduled({
            "job_type": "LOJA_EXPRESS_D1",
            "account_id": "1",
            "contact_id": "5511999990000",
            "conversation_id": "conv-1",
        })
    mock_followup.execute.assert_called_once()
    call_kwargs = mock_followup.execute.call_args.kwargs
    assert call_kwargs["day"] == 1
    assert call_kwargs["account_id"] == 1
    assert call_kwargs["contact_id"] == "5511999990000"


@pytest.mark.asyncio
async def test_handle_scheduled_loja_express_d7_calls_followup_day_7():
    mock_followup = AsyncMock()
    mock_followup.execute = AsyncMock(return_value="ESCALADO: reason=loja_express_d7_prazo_critico")
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_followup_handler",
        return_value=mock_followup,
    ), patch(
        "nexoia.interface.worker.handlers.scheduled._get_lifecycle_handler",
        return_value=AsyncMock(),
    ):
        from nexoia.interface.worker.handlers.scheduled import handle_scheduled
        await handle_scheduled({
            "job_type": "LOJA_EXPRESS_D7",
            "account_id": "1",
            "contact_id": "5511999990000",
            "conversation_id": "conv-1",
        })
    mock_followup.execute.assert_called_once()
    call_kwargs = mock_followup.execute.call_args.kwargs
    assert call_kwargs["day"] == 7
