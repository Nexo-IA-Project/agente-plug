from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

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
    # subscription.activated é evento de ativação → matching flexível usa o método plural.
    flow_repo.list_active_by_product_and_events = AsyncMock(
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
async def test_schedule_mode_from_now_overrides_activated_at():
    """Task 7: ao reprocessar com `_schedule_mode=from_now`, o enrollment usa o
    horário atual (now) em vez do activatedAt original do payload."""
    from datetime import UTC, datetime

    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-now")

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

    before = datetime.now(UTC)
    payload = _make_event("subscription.activated")
    # activatedAt original: 2026-05-22 — bem no passado.
    payload["_schedule_mode"] = "from_now"
    await handler.handle(payload)
    after = datetime.now(UTC)

    # purchase_time passado ao enroll deve ser "agora", não o activatedAt do payload.
    enroll_uc.execute.assert_called_once()
    purchase_time = enroll_uc.execute.call_args.kwargs["purchase_time"]
    original = datetime.fromisoformat("2026-05-22T12:00:00+00:00")
    assert purchase_time != original
    assert before <= purchase_time <= after

    # purchase_handler também recebe o activated_at "agora".
    purchase_handler.handle_one.assert_called_once()
    assert before <= purchase_handler.handle_one.call_args.kwargs["activated_at"] <= after


@pytest.mark.asyncio
async def test_schedule_mode_original_keeps_payload_activated_at():
    """Task 7: sem `_schedule_mode` (ou "original"), mantém o activatedAt do payload."""
    from datetime import datetime

    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-orig")

    enroll_uc = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=AsyncMock(),
    )

    payload = _make_event("subscription.activated")
    payload["_schedule_mode"] = "original"
    await handler.handle(payload)

    enroll_uc.execute.assert_called_once()
    purchase_time = enroll_uc.execute.call_args.kwargs["purchase_time"]
    assert purchase_time == datetime.fromisoformat("2026-05-22T12:00:00+00:00")


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
    product_repo.find_active_by_name = AsyncMock(return_value=None)

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    await handler.handle(_make_event("subscription.activated"))

    enroll_uc.execute.assert_not_called()
    purchase_handler.handle_one.assert_called_once()


@pytest.mark.asyncio
async def test_unmapped_product_marks_lead_and_alerts():
    """Task 5: produto não casa (id/alias e nome) → marca lead.product_unmatched=True,
    dispara o hook de alerta e NÃO enrolla flow."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)
    product_repo.find_active_by_name = AsyncMock(return_value=None)

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    lead_id = uuid4()
    lead_repo = AsyncMock()
    lead_repo.upsert = AsyncMock(return_value=MagicMock(id=lead_id))
    lead_repo.set_product_unmatched = AsyncMock()

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    enroll_uc = AsyncMock()
    unmapped_alert = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=enroll_uc,
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
        unmapped_alert=unmapped_alert,
    )

    # lead.abandoned não está em PURCHASE_EVENT_TYPES → caminho puro de produto não reconhecido.
    await handler.handle(_make_event("lead.abandoned"))

    lead_repo.set_product_unmatched.assert_awaited_once_with(lead_id=lead_id, value=True)
    enroll_uc.execute.assert_not_called()
    unmapped_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_matched_product_marks_lead_not_unmatched():
    """Task 5: quando o produto casa, lead.product_unmatched é setado para False
    (cobre reprocesso de um lead antes não reconhecido)."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    lead_id = uuid4()
    lead_repo = AsyncMock()
    lead_repo.upsert = AsyncMock(return_value=MagicMock(id=lead_id))
    lead_repo.set_product_unmatched = AsyncMock()

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-z")

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    await handler.handle(_make_event("subscription.activated"))

    lead_repo.set_product_unmatched.assert_awaited_once_with(lead_id=lead_id, value=False)


@pytest.mark.asyncio
async def test_product_matched_by_name_fallback_when_id_unknown():
    """Hubla envia id de offer (v1) não cadastrado, mas o nome do produto bate →
    resolve por nome (ponte) e enrolla o flow normalmente."""
    product = _make_product()
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)  # id de offer desconhecido
    product_repo.find_active_by_name = AsyncMock(return_value=product)  # nome bate

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-y")

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

    product_repo.find_active_by_name.assert_awaited_once()
    enroll_uc.execute.assert_called_once()


@pytest.mark.asyncio
async def test_flow_with_mismatched_trigger_is_not_enrolled():
    """Regressão C1: subscription.activated NÃO deve enrollar flows configurados para lead.abandoned."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    # Evento de ativação usa o método plural (grupo canônico); retorna vazio
    # porque nenhum flow do produto está nesse grupo.
    flow_repo.list_active_by_product_and_events = AsyncMock(return_value=[])

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

    # Verifica que o repo foi consultado com o grupo canônico de ativação
    flow_repo.list_active_by_product_and_events.assert_called_once()
    call_kwargs = flow_repo.list_active_by_product_and_events.call_args.kwargs
    assert "subscription.activated" in call_kwargs["event_types"]
    assert "customer.member_added" in call_kwargs["event_types"]

    # Nenhum flow correspondeu → sem enrollment, mas purchase_handler executa (access case)
    enroll_uc.execute.assert_not_called()
    purchase_handler.handle_one.assert_called_once()


@pytest.mark.asyncio
async def test_member_added_enrolls_flow_configured_for_subscription_activated():
    """Matching flexível: customer.member_added (Hubla v2) deve disparar flows
    configurados para subscription.activated (grupo canônico de ativação)."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-x")

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

    await handler.handle(_make_event("customer.member_added"))

    # Casa o flow antigo via grupo de ativação e enrolla.
    flow_repo.list_active_by_product_and_events.assert_called_once()
    call_kwargs = flow_repo.list_active_by_product_and_events.call_args.kwargs
    assert "customer.member_added" in call_kwargs["event_types"]
    assert "subscription.activated" in call_kwargs["event_types"]
    enroll_uc.execute.assert_called_once()
    # customer.member_added NÃO está em PURCHASE_EVENT_TYPES → não roda welcome legado.
    purchase_handler.handle_one.assert_not_called()


@pytest.mark.asyncio
async def test_route_continues_when_create_conversation_fails():
    """Resiliência: falha de ChatNexo em um flow não impede os demais nem derruba o evento."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated"), _make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(side_effect=[RuntimeError("404"), "conv-2"])

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

    # Não deve levantar — o 1º flow falha, o 2º enrolla.
    await handler.handle(_make_event("customer.member_added"))

    assert enroll_uc.execute.await_count == 1


@pytest.mark.asyncio
async def test_single_flow_chatnexo_failure_does_not_raise_and_marks_processed():
    """Um único flow que falha no ChatNexo: handle() completa e marca processed."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=_make_product())

    flow_repo = AsyncMock()
    flow_repo.list_active_by_product_and_events = AsyncMock(
        return_value=[_make_flow("subscription.activated")]
    )

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(side_effect=RuntimeError("404 contact_inboxes"))

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        hubla_event_repo=hubla_event_repo,
    )

    await handler.handle(_make_event("customer.member_added"))

    # O finally garante mark_processed mesmo com a falha de ChatNexo.
    hubla_event_repo.mark_processed.assert_awaited_once()


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
    product_repo.find_active_by_name = AsyncMock(return_value=None)

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
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

    # PR 4 review fix #6: sem phone → contact não resolvido → contact_id deve ser None
    assert hubla_event_repo.insert.call_args.kwargs["contact_id"] is None
    assert lead_repo.upsert.call_args.kwargs["contact_id"] is None


@pytest.mark.asyncio
async def test_handler_works_without_lead_repos_backward_compat():
    """Existing call sites that don't pass lead_repo/hubla_event_repo must still work."""
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)
    product_repo.find_active_by_name = AsyncMock(return_value=None)

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
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
                "payer": {
                    "firstName": "A",
                    "lastName": "B",
                    "phone": "+5511000000000",
                    "email": "a@b.c",
                },
                "activatedAt": "2026-05-22T12:00:00Z",
            },
        },
    }

    # Should not raise
    await handler.handle(payload)


@pytest.mark.asyncio
async def test_contact_id_propagated_to_hubla_event_and_lead():
    """PR 4 review fix #6: o contact_id resolvido deve ser passado aos repos de
    persistência, para que os registros de hubla_events e leads referenciem
    o contato (FK) quando o telefone bater com um contato existente.
    """
    contact = _make_contact()
    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=contact)

    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)
    product_repo.find_active_by_name = AsyncMock(return_value=None)
    purchase_handler = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=purchase_handler,
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    await handler.handle(_make_event("subscription.activated"))

    # Both persistence calls must receive the resolved contact.id
    event_kwargs = hubla_event_repo.insert.call_args.kwargs
    assert event_kwargs["contact_id"] == UUID(str(contact.id))

    lead_kwargs = lead_repo.upsert.call_args.kwargs
    assert lead_kwargs["contact_id"] == UUID(str(contact.id))


@pytest.mark.asyncio
async def test_processed_at_marked_after_handling():
    """PR 4 review fix #12: processed_at deve ser setado em todos os caminhos de saída."""
    event_model = MagicMock()
    event_model.id = uuid4()

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=event_model)
    hubla_event_repo.mark_processed = AsyncMock()

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    handler = HublaEventHandler(
        product_repo=AsyncMock(),
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=AsyncMock(),
        hubla_event_repo=hubla_event_repo,
    )

    # Force the early-return path (no phone) so processed_at is tested on a short path
    payload = _make_event("subscription.activated")
    payload["event"]["subscription"]["payer"]["phone"] = ""

    await handler.handle(payload)

    hubla_event_repo.mark_processed.assert_called_once_with(event_model.id)


@pytest.mark.asyncio
async def test_publishes_lead_upserted_envelope_after_upsert():
    """Task 14: HublaEventHandler publica envelope `lead.upserted` no LeadsPubSub
    após o upsert do Lead, contendo a entity serializada + metadados do evento."""
    from datetime import UTC, datetime

    from shared.domain.entities.hubla_event import HublaEvent
    from shared.domain.entities.lead import Lead

    account_id = uuid4()
    lead_id = uuid4()
    now = datetime.now(UTC)

    # Entity Lead retornada pelo upsert — created_at == updated_at sinaliza "is_new".
    lead_entity = Lead(
        id=lead_id,
        account_id=account_id,
        hubla_subscription_id="sub-pub-1",
        payer_phone="+5511999990000",
        payer_name="João Silva",
        payer_email="joao@email.com",
        hubla_product_id="prod-hubla-123",
        product_name="Produto X",
        subscription_status="active",
        first_seen_at=now,
        last_event_at=now,
        last_event_type="subscription.activated",
        created_at=now,
        updated_at=now,
        activated_at=now,
        utm_source="Meta Ads",
    )

    event_entity = HublaEvent(
        id=uuid4(),
        account_id=account_id,
        event_type="subscription.activated",
        hubla_subscription_id="sub-pub-1",
        hubla_product_id="prod-hubla-123",
        product_name="Produto X",
        payer_phone="+5511999990000",
        payer_email="joao@email.com",
        payer_name="João Silva",
        payload={},
        received_at=now,
    )

    lead_repo = AsyncMock()
    lead_repo.upsert = AsyncMock(return_value=lead_entity)

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=event_entity)
    hubla_event_repo.mark_processed = AsyncMock()

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    leads_pubsub = AsyncMock()
    leads_pubsub.publish = AsyncMock()

    handler = HublaEventHandler(
        product_repo=AsyncMock(),
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
        leads_pubsub=leads_pubsub,
        account_id=account_id,
    )

    await handler.handle(_make_event("subscription.activated"))

    # Lead foi upserted e o envelope foi publicado uma vez.
    lead_repo.upsert.assert_awaited_once()
    leads_pubsub.publish.assert_awaited_once()

    published_account, envelope = leads_pubsub.publish.await_args.args
    assert published_account == account_id
    assert envelope["type"] == "lead.upserted"
    assert envelope["is_new"] is True  # created_at == updated_at
    assert envelope["lead"]["id"] == str(lead_id)
    assert envelope["lead"]["hubla_subscription_id"] == "sub-pub-1"
    assert envelope["lead"]["utm_source"] == "Meta Ads"
    assert envelope["lead"]["subscription_status"] == "active"
    # Metadados do hubla_event acompanham o envelope.
    assert envelope["event"]["event_type"] == "subscription.activated"
    assert envelope["event"]["id"] == str(event_entity.id)


@pytest.mark.asyncio
async def test_does_not_publish_when_pubsub_absent():
    """Sem leads_pubsub injetado: handle() funciona normalmente, sem erros."""
    lead_repo = AsyncMock()
    lead_repo.upsert = AsyncMock(return_value=MagicMock())  # retorno qualquer

    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    # leads_pubsub NÃO é injetado.
    handler = HublaEventHandler(
        product_repo=AsyncMock(),
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    # Não deve levantar — só não publica.
    await handler.handle(_make_event("subscription.activated"))


@pytest.mark.asyncio
async def test_does_not_publish_when_lead_not_persisted():
    """Sem purchase_id (sub.id ausente): lead_entity é None, então publish é skipped."""
    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()
    hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo.mark_processed = AsyncMock()

    contact_repo = AsyncMock()
    contact_repo.upsert = AsyncMock(return_value=_make_contact())

    leads_pubsub = AsyncMock()

    handler = HublaEventHandler(
        product_repo=AsyncMock(),
        flow_repo=AsyncMock(),
        contact_repo=contact_repo,
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
        leads_pubsub=leads_pubsub,
    )

    payload = _make_event("subscription.activated")
    payload["event"]["subscription"]["id"] = ""  # sem purchase_id

    await handler.handle(payload)

    lead_repo.upsert.assert_not_called()
    leads_pubsub.publish.assert_not_called()
