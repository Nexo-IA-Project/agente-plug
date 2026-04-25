# tests/unit/application/test_purchase_handler_loja_express.py
from __future__ import annotations

import pytest
from datetime import UTC, datetime
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock, patch

from nexoia.application.purchase_handler import PurchaseHandler
from nexoia.domain.events.purchase_received import PurchaseReceived


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch get_settings to avoid requiring a real .env in unit tests."""
    settings = MagicMock()
    settings.loja_express_product_tags = ["loja_express", "loja-express"]
    with patch(
        "nexoia.application.purchase_handler.get_settings",
        return_value=settings,
    ):
        yield settings


def _fake_event(product: str = "Loja Express Pack") -> PurchaseReceived:
    return PurchaseReceived(
        purchase_id="p-loja-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        contact_name="Maria Lima",
        contact_email="maria@test.com",
        contact_phone="5511988880000",
        product=product,
        amount_brl=19700,
        occurred_at=datetime.now(UTC),
    )


def _make_loja_handler(criar_uc: AsyncMock) -> PurchaseHandler:
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511988880000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-loja"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    return PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
        loja_express_case_repo=AsyncMock(),
        loja_express_port=AsyncMock(),
        criar_uc=criar_uc,
    )


@pytest.mark.asyncio
async def test_loja_express_product_routes_to_criar_uc():
    """When product name contains 'loja_express' tag, criar_uc.execute is called."""
    criar_uc = AsyncMock()
    criar_uc.execute = AsyncMock(return_value="CASO_CRIADO: case_id=abc")
    handler = _make_loja_handler(criar_uc)
    event = _fake_event(product="loja_express Curso Avancado")
    await handler.execute(event)
    criar_uc.execute.assert_called_once()
    call_kwargs = criar_uc.execute.call_args.kwargs
    assert call_kwargs["purchase_id"] == "p-loja-1"
    assert call_kwargs["contact_name"] == "Maria Lima"
    assert call_kwargs["student_email"] == "maria@test.com"


@pytest.mark.asyncio
async def test_non_loja_express_product_uses_normal_welcome_flow():
    """When product has no loja express tag, normal access-case flow runs, criar_uc is NOT called."""
    criar_uc = AsyncMock()
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-2", phone="5511988880000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-existing"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
        loja_express_case_repo=AsyncMock(),
        loja_express_port=AsyncMock(),
        criar_uc=criar_uc,
    )
    event = _fake_event(product="Mentoria de Tráfego")
    await handler.execute(event)
    criar_uc.execute.assert_not_called()
    access_case_repo.save.assert_called_once()
