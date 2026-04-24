from __future__ import annotations
import pytest
from datetime import datetime, UTC
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.purchase_handler import PurchaseHandler
from nexoia.domain.events.purchase_received import PurchaseReceived


def fake_event():
    return PurchaseReceived(
        purchase_id="p-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        contact_name="João Silva",
        contact_email="joao@test.com",
        contact_phone="5511999990000",
        product="Mentoria de Tráfego",
        amount_brl=49700,
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_creates_contact_and_access_case():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    contact_repo.find_or_create.assert_called_once()
    access_case_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_sends_welcome_template():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "existing-conv"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "welcome_purchase"


@pytest.mark.asyncio
async def test_schedules_d1_followup_job():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    scheduler.create_job.assert_called_once()
    call_kwargs = scheduler.create_job.call_args.kwargs
    assert "FOLLOWUP_D1" in str(call_kwargs.get("job_type", "")).upper()
