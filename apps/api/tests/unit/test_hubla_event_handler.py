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
async def test_flow_with_mismatched_trigger_is_not_enrolled():
    """Regressão C1: subscription.activated NÃO deve enrollar flows configurados para lead.abandoned."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    # O repo filtra por event_type; retorna lista vazia pois nenhum flow corresponde ao evento.
    flow_repo.list_active_by_product_and_event = AsyncMock(return_value=[])

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value="conv-1")

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

    # Verifica que o repo foi chamado com o filtro correto de event_type
    flow_repo.list_active_by_product_and_event.assert_called_once()
    call_kwargs = flow_repo.list_active_by_product_and_event.call_args.kwargs
    assert call_kwargs["event_type"] == "subscription.activated"

    # Nenhum flow correspondeu → sem enrollment, mas purchase_handler executa (access case)
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


@pytest.mark.asyncio
async def test_subscription_created_persists_lead_with_utms_and_invoice():
    """PR 4: HublaEventHandler grava HublaEvent + faz upsert do Lead com UTMs/valor."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)  # produto não cadastrado

    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=purchase_handler,
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    payload = {
        "type": "subscription.created",
        "version": "2.0.0",
        "event": {
            "product": {"id": "prod-123", "name": "Produto X"},
            "products": [
                {
                    "id": "prod-123",
                    "name": "Produto X",
                    "offers": [{"id": "offer-1", "name": "Oferta A"}],
                }
            ],
            "subscription": {
                "id": "sub-abc",
                "payer": {
                    "firstName": "Maria",
                    "lastName": "Souza",
                    "document": "99988877766",
                    "email": "maria@email.com",
                    "phone": "+5521988887777",
                },
                "paymentMethod": "pix",
                "status": "inactive",
                "firstPaymentSession": {
                    "ip": "200.0.0.1",
                    "url": "https://pay.hub.la/offer-1?utm_source=Meta+Ads",
                    "utm": {
                        "source": "Meta Ads",
                        "medium": "cpc",
                        "campaign": "Campanha 1",
                        "content": "Ad 1",
                        "term": "keyword1",
                    },
                    "cookies": {"fbp": "fb.1.123.456789"},
                },
                "lastInvoice": {
                    "amount": {"totalCents": 9700, "subtotalCents": 9700},
                    "paymentMethod": "pix",
                },
            },
        },
    }

    await handler.handle(payload)

    # HublaEvent log was written
    hubla_event_repo.insert.assert_called_once()
    event_kwargs = hubla_event_repo.insert.call_args.kwargs
    assert event_kwargs["event_type"] == "subscription.created"
    assert event_kwargs["hubla_subscription_id"] == "sub-abc"
    assert event_kwargs["payload"] == payload

    # Lead upsert called with UTMs and invoice fields
    lead_repo.upsert.assert_called_once()
    lead_kwargs = lead_repo.upsert.call_args.kwargs
    assert lead_kwargs["hubla_subscription_id"] == "sub-abc"
    assert lead_kwargs["event_type"] == "subscription.created"
    assert lead_kwargs["utm_source"] == "Meta Ads"
    assert lead_kwargs["utm_campaign"] == "Campanha 1"
    assert lead_kwargs["fbp"] == "fb.1.123.456789"
    assert lead_kwargs["amount_total_cents"] == 9700
    assert lead_kwargs["amount_subtotal_cents"] == 9700
    assert lead_kwargs["subscription_status"] == "inactive"
    assert lead_kwargs["payment_method"] == "pix"
    assert lead_kwargs["payer_document"] == "99988877766"
    assert lead_kwargs["offer_id"] == "offer-1"
    assert lead_kwargs["offer_name"] == "Oferta A"
    assert lead_kwargs["session_ip"] == "200.0.0.1"

    # Para subscription.created (não activated), PurchaseHandler NÃO é chamado
    purchase_handler.handle_one.assert_not_called()


@pytest.mark.asyncio
async def test_no_phone_still_persists_hubla_event_and_lead():
    """PR 4 review fix: payer_phone vazio NÃO deve descartar o evento.
    HublaEvent (audit log) e Lead (subscription-id keyed) ainda devem ser gravados.
    """
    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()

    handler = HublaEventHandler(
        product_repo=AsyncMock(),
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    payload = {
        "type": "lead.abandoned",
        "version": "2.0.0",
        "event": {
            "product": {"id": "prod-99", "name": "Produto 99"},
            "products": [{"id": "prod-99", "name": "Produto 99"}],
            "subscription": {
                "id": "sub-no-phone",
                "payer": {
                    "firstName": "Ana",
                    "lastName": "Silva",
                    "email": "ana@email.com",
                    "phone": "",  # ← VAZIO
                },
                "firstPaymentSession": {"utm": {"source": "Google Ads"}},
            },
        },
    }

    await handler.handle(payload)

    # AMBOS devem ter sido gravados, mesmo sem phone
    hubla_event_repo.insert.assert_called_once()
    lead_repo.upsert.assert_called_once()
    assert lead_repo.upsert.call_args.kwargs["utm_source"] == "Google Ads"


@pytest.mark.asyncio
async def test_handler_works_without_lead_repos_backward_compat():
    """Existing call sites that don't pass lead_repo/hubla_event_repo must still work."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        # lead_repo and hubla_event_repo omitted on purpose
    )

    payload = {
        "type": "subscription.activated",
        "event": {
            "product": {"id": "prod", "name": "P"},
            "subscription": {
                "id": "s1",
                "payer": {"firstName": "A", "lastName": "B", "phone": "+5511000000000", "email": "a@b.c"},
                "activatedAt": "2026-05-22T12:00:00Z",
            },
        },
    }

    # Should not raise
    await handler.handle(payload)
