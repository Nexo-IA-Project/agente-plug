import pytest
from unittest.mock import AsyncMock, patch

from nexoia.interface.worker.handlers.process_purchase import handle_process_purchase_webhook


@pytest.mark.asyncio
async def test_handler_invokes_run_welcome_subgraph():
    job_payload = {
        "purchase_id": "p-001",
        "account_id": 1,
        "student_name": "João Silva",
        "student_phone": "+5511999999999",
        "student_email": "joao@email.com",
        "product_name": "Curso Python",
        "correlation_id": "corr-001",
    }
    run_subgraph = AsyncMock(return_value={"access_case_id": "ac-001"})

    with patch(
        "nexoia.interface.worker.handlers.process_purchase.run_welcome_subgraph",
        run_subgraph,
    ):
        await handle_process_purchase_webhook(payload=job_payload)

    run_subgraph.assert_called_once()
    call_kwargs = run_subgraph.call_args[1]
    assert call_kwargs["purchase_id"] == "p-001"
    assert call_kwargs["account_id"] == 1


@pytest.mark.asyncio
async def test_handler_missing_required_field_raises():
    bad_payload = {"purchase_id": "p-001"}  # missing required fields

    with pytest.raises((KeyError, ValueError)):
        await handle_process_purchase_webhook(payload=bad_payload)
