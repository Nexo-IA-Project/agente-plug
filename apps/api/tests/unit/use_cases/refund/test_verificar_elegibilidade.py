from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from shared.application.use_cases.refund.verificar_elegibilidade import (
    VerificarElegibilidadeReembolso,
)
from shared.domain.ports.hubla_port import HublaPurchase


def _make_purchase(
    days_ago: int = 3,
    is_duplicate: bool = False,
    is_recurring: bool = False,
    first_charge_at: datetime | None = None,
) -> HublaPurchase:
    created_at = datetime.now(UTC) - timedelta(days=days_ago)
    return HublaPurchase(
        id="purchase-1",
        product_name="Curso Python",
        created_at=created_at,
        amount=199.0,
        is_duplicate=is_duplicate,
        is_recurring=is_recurring,
        first_charge_at=first_charge_at,
    )


def _make_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_eligible_within_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=3))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "ELEGIVEL" in result
    assert "3" in result  # dias


@pytest.mark.asyncio
async def test_ineligible_outside_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=10))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "INELEGIVEL" in result
    assert "10" in result or "data_compra" in result


@pytest.mark.asyncio
async def test_purchase_not_found_returns_error():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=None)
    legal = AsyncMock()
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "COMPRA_NAO_ENCONTRADA" in result


@pytest.mark.asyncio
async def test_duplicate_purchase_returns_duplicate_signal():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=2, is_duplicate=True))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "COMPRA_DUPLICADA" in result


@pytest.mark.asyncio
async def test_art49_prior_mention_forces_within_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=10))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=True)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    # Art. 49: prior mention within deadline → eligible even with 10 days
    assert "ELEGIVEL" in result


@pytest.mark.asyncio
async def test_recurring_purchase_uses_first_charge_date():
    repo = _make_repo()
    hubla = AsyncMock()
    # first_charge_at was 3 days ago (within deadline), created_at was 30 days ago
    first_charge = datetime.now(UTC) - timedelta(days=3)
    purchase = _make_purchase(days_ago=30, is_recurring=True, first_charge_at=first_charge)
    hubla.get_purchase_by_email = AsyncMock(return_value=purchase)
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    # Must be ELEGIVEL because uses first_charge_at (3 days ago), not created_at (30 days)
    assert "ELEGIVEL" in result


@pytest.mark.asyncio
async def test_recurring_purchase_with_no_first_charge_falls_back_to_created_at():
    repo = _make_repo()
    hubla = AsyncMock()
    # is_recurring=True but first_charge_at=None → should fall back to created_at (3 days ago)
    purchase = _make_purchase(days_ago=3, is_recurring=True, first_charge_at=None)
    hubla.get_purchase_by_email = AsyncMock(return_value=purchase)
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    # created_at is 3 days ago → within 7-day deadline
    assert "ELEGIVEL" in result
