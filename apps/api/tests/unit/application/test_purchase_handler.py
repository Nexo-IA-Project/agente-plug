from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from shared.application.purchase_handler import PurchaseHandler
from shared.domain.events.purchase_received import PurchaseReceived


def fake_event(
    product_id: str = "prod-mentoria",
    product_name: str = "Mentoria de Tráfego",
) -> PurchaseReceived:
    return PurchaseReceived(
        purchase_id="p-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        customer_name="João Silva",
        contact_email="joao@test.com",
        contact_phone="5511999990000",
        product_id=product_id,
        product_name=product_name,
        amount_brl=49700,
        occurred_at=datetime.now(UTC),
    )


def _make_handler(
    *,
    product_repo: AsyncMock | None = None,
    contact_repo: AsyncMock | None = None,
    chatnexo: AsyncMock | None = None,
    access_case_repo: AsyncMock | None = None,
    scheduler: AsyncMock | None = None,
) -> PurchaseHandler:
    contact_repo = contact_repo or AsyncMock()
    if not contact_repo.upsert.return_value:
        contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = chatnexo or AsyncMock()
    if (
        chatnexo.get_open_conversation.return_value is None
        and not chatnexo.create_conversation.return_value
    ):
        chatnexo.create_conversation.return_value = "conv-1"
    return PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo or AsyncMock(),
        scheduler=scheduler or AsyncMock(),
        product_repo=product_repo or AsyncMock(),
    )


@pytest.mark.asyncio
async def test_creates_contact_and_access_case():
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
    )
    await handler.execute(fake_event())
    contact_repo.upsert.assert_called_once()
    access_case_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_sends_welcome_template():
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "existing-conv"
    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
    )
    await handler.execute(fake_event())
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "welcome_purchase"


@pytest.mark.asyncio
async def test_purchase_handler_does_not_enroll_flows():
    """PurchaseHandler não deve tocar em flows/enrollment — isso é responsabilidade do HublaEventHandler."""
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"

    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
    )
    await handler.execute(fake_event())

    # PurchaseHandler nunca acessa flow_repo nem enroll_uc — por design não há esses atributos
    assert not hasattr(handler, "_flow_repo")
    assert not hasattr(handler, "_enroll_contact_uc")


@pytest.mark.asyncio
async def test_creates_conversation_when_none_exists():
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "new-conv"
    access_case_repo = AsyncMock()

    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
    )
    await handler.execute(fake_event())

    chatnexo.create_conversation.assert_called_once()
    access_case_repo.save.assert_called_once()
