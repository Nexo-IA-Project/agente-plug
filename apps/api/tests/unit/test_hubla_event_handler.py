from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.hubla_event_handler import HublaEventHandler


def _make_event(event_type: str = "subscription.activated") -> dict:
    return {
        "type": event_type,
        "version": "2.0.0",
        "event": {
            "product": {"id": "prod-hubla-123", "name": "Produto X"},
            "products": [{"id": "prod-hubla-123", "name": "Produto X"}],
            "subscription": {
                "id": "sub-uuid-001",
                "payer": {
                    "firstName": "João",
                    "lastName": "Silva",
                    "document": "12345678901",
                    "email": "joao@email.com",
                    "phone": "+5511999990000",
                },
                "activatedAt": "2026-05-22T12:00:00Z",
            },
        },
    }


def _make_contact():
    contact = MagicMock()
    contact.id = uuid4()
    contact.phone = "+5511999990000"
    return contact


def _make_product():
    product = MagicMock()
    product.id = uuid4()
    return product


def _make_flow(event_type: str):
    flow = MagicMock()
    flow.id = uuid4()
    flow.trigger_event_type = event_type
    return flow


@pytest.mark.asyncio
async def test_subscription_activated_enrolls_and_runs_purchase_handler():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_event = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-new-123")

    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    await handler.handle(_make_event("subscription.activated"))

    enroll_uc.execute.assert_called_once()
    purchase_handler.handle_one.assert_called_once()
    chatnexo.create_conversation.assert_called_once()


@pytest.mark.asyncio
async def test_lead_abandoned_uses_existing_conversation_and_skips_purchase_handler():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_event = AsyncMock(
        return_value=[_make_flow("lead.abandoned")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value="conv-existing-456")
    chatnexo.create_conversation = AsyncMock()

    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    await handler.handle(_make_event("lead.abandoned"))

    enroll_uc.execute.assert_called_once()
    purchase_handler.handle_one.assert_not_called()
    chatnexo.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_product_for_subscription_activated_still_runs_purchase_handler():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)

    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    await handler.handle(_make_event("subscription.activated"))

    enroll_uc.execute.assert_not_called()
    purchase_handler.handle_one.assert_called_once()


@pytest.mark.asyncio
async def test_no_payer_phone_skips_processing():
    product_repo = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=purchase_handler,
    )

    payload = _make_event("subscription.activated")
    payload["event"]["subscription"]["payer"]["phone"] = ""
    await handler.handle(payload)

    product_repo.find_active_by_hubla_id.assert_not_called()
    purchase_handler.handle_one.assert_not_called()
