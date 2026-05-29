"""Garante que HublaEventHandler aceita todos os 25 event types da Hubla v2."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.hubla_event_handler import HublaEventHandler
from shared.domain.value_objects.hubla_event_type import ALL_HUBLA_EVENT_TYPES


def _make_handler() -> HublaEventHandler:
    """Constrói handler com todas as deps mockadas (não toca DB nem rede)."""
    chatnexo = MagicMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-1")

    product_repo = MagicMock()
    product_repo.find_active_by_hubla_id = AsyncMock(
        return_value=None
    )  # produto não encontrado por padrão
    product_repo.find_active_by_name = AsyncMock(return_value=None)  # fallback por nome: sem match

    flow_repo = MagicMock()
    flow_repo.list_active_by_product_and_event = AsyncMock(return_value=[])

    contact_repo = MagicMock()
    contact = MagicMock(id=uuid4(), phone="+5511999999999")
    contact_repo.upsert = AsyncMock(return_value=contact)

    enroll_uc = MagicMock()
    enroll_uc.execute = AsyncMock()

    purchase_handler = MagicMock()
    purchase_handler.handle_one = AsyncMock()

    lead_repo = MagicMock()
    lead_repo.upsert = AsyncMock()

    hubla_event_repo = MagicMock()
    event_model = MagicMock(id=uuid4())
    hubla_event_repo.insert = AsyncMock(return_value=event_model)
    hubla_event_repo.mark_processed = AsyncMock()

    return HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )


def _make_payload(event_type: str) -> dict:
    """Payload mínimo compatível com a shape esperada pelo handler."""
    return {
        "id": "evt_test",
        "type": event_type,
        "version": "2.0.0",
        "event": {
            "subscription": {
                "id": "sub_1",
                "status": "active",
                "activatedAt": "2026-05-27T00:00:00Z",
                "payer": {
                    "firstName": "Test",
                    "lastName": "User",
                    "email": "t@x.com",
                    "phone": "+5511999999999",
                    "document": "12345678900",
                },
                "firstPaymentSession": {"utm": {}, "cookies": {}},
                "lastInvoice": {"amount": {}},
            },
            "products": [{"id": "prod_1", "name": "Produto X", "offers": []}],
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", sorted(ALL_HUBLA_EVENT_TYPES))
async def test_handler_accepts_all_25_types(event_type: str) -> None:
    handler = _make_handler()
    payload = _make_payload(event_type=event_type)
    # Deve completar sem erros para qualquer um dos 25 tipos
    await handler.handle(payload)
    # hubla_events foi gravado
    handler._hubla_event_repo.insert.assert_called_once()


@pytest.mark.asyncio
async def test_handler_logs_warning_for_unknown_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = _make_handler()
    await handler.handle(_make_payload(event_type="foo.bar"))
    # Deve persistir mesmo assim
    handler._hubla_event_repo.insert.assert_called_once()
    # E ter logado warning de evento desconhecido (structlog usa PrintLoggerFactory → stdout)
    captured = capsys.readouterr()
    assert "hubla_unknown_event" in captured.out
    assert "foo.bar" in captured.out


@pytest.mark.asyncio
async def test_handler_calls_purchase_handler_only_for_subscription_activated() -> None:
    handler = _make_handler()
    await handler.handle(_make_payload(event_type="subscription.activated"))
    handler._purchase_handler.handle_one.assert_called_once()


@pytest.mark.asyncio
async def test_handler_does_not_call_purchase_for_other_events() -> None:
    handler = _make_handler()
    await handler.handle(_make_payload(event_type="customer.member_added"))
    handler._purchase_handler.handle_one.assert_not_called()
