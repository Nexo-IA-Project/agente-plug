from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from shared.application.purchase_handler import PurchaseHandler
from shared.domain.events.purchase_received import PurchaseReceived


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch get_settings to avoid requiring a real .env in unit tests."""
    settings = MagicMock()
    settings.loja_express_product_tags = ["loja_express", "loja-express"]
    with patch(
        "shared.application.purchase_handler.get_settings",
        return_value=settings,
    ):
        yield settings


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
async def test_enrolls_dynamic_followup_when_uc_provided():
    from uuid import uuid4

    contact_id = uuid4()
    conv_id = str(uuid4())
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id=contact_id, phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = conv_id
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    enroll_uc = AsyncMock()
    enroll_uc.execute.return_value = None  # sem flow ativo — enrollment retorna None
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
        enroll_contact_uc=enroll_uc,
    )
    await handler.execute(fake_event())
    enroll_uc.execute.assert_called_once()
    # scheduler.create_job legado foi removido — não deve ser chamado
    scheduler.create_job.assert_not_called()
