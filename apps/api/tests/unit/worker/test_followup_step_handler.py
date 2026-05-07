from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_handle_scheduled_followup_step_calls_dispatch():
    mock_dispatch = AsyncMock()
    mock_dispatch.execute = AsyncMock(return_value="SENT")

    step_id = str(uuid4())
    account_id = str(uuid4())
    conv_id = str(uuid4())

    with patch(
        "interface.worker.handlers.scheduled._get_dispatch_followup_step_handler",
        return_value=mock_dispatch,
    ):
        from interface.worker.handlers.scheduled import handle_scheduled

        await handle_scheduled({
            "job_type": "followup_step",
            "account_id": account_id,
            "conversation_id": conv_id,
            "contact_phone": "5511999990000",
            "enrollment_step_id": step_id,
        })

    mock_dispatch.execute.assert_called_once()
