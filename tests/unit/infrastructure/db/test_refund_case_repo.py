from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.repositories.refund_case_repo import RefundCaseRepository


def _make_model(
    status: str = "collecting",
    purchase_id: str | None = None,
    within_deadline: bool | None = None,
    is_duplicate_purchase: bool = False,
    offers_made: list[str] | None = None,
):
    m = MagicMock()
    m.id = "case-1"
    m.account_id = 1
    m.contact_id = "5511999990000"
    m.conversation_id = "conv-1"
    m.purchase_id = purchase_id
    m.product_name = "Curso X"
    m.student_email = "a@b.com"
    m.student_cpf = None
    m.refund_reason = None
    m.days_since_purchase = None
    m.within_deadline = within_deadline
    m.is_duplicate_purchase = is_duplicate_purchase
    m.offers_made = offers_made or []
    m.offer_accepted = False
    m.refund_processed_this_turn = False
    m.status = status
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


@pytest.mark.asyncio
async def test_save_adds_model_and_flushes():
    session = AsyncMock()
    repo = RefundCaseRepository(session)
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
    )
    await repo.save(case)
    session.add.assert_called_once()
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_persists_fields():
    session = AsyncMock()
    mock_model = _make_model()
    session.get = AsyncMock(return_value=mock_model)
    repo = RefundCaseRepository(session)
    case = RefundCase(
        id="case-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        status=RefundCaseStatus.REFUNDED,
        offers_made=["N1", "N2"],
    )
    await repo.update(case)
    session.flush.assert_called_once()
    assert mock_model.status == "refunded"
    assert mock_model.offers_made == ["N1", "N2"]


@pytest.mark.asyncio
async def test_update_raises_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = RefundCaseRepository(session)
    case = RefundCase(
        id="missing",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
    )
    with pytest.raises(ValueError, match="missing"):
        await repo.update(case)


@pytest.mark.asyncio
async def test_find_by_phone_returns_none_when_not_found():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    repo = RefundCaseRepository(session)
    result = await repo.find_by_phone(account_id=1, phone="5511999990000")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_phone_maps_to_entity():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = _make_model(
        status="in_retention",
        offers_made=["N1"],
        within_deadline=True,
    )
    session.execute = AsyncMock(return_value=execute_result)
    repo = RefundCaseRepository(session)
    result = await repo.find_by_phone(account_id=1, phone="5511999990000")
    assert result is not None
    assert result.status == RefundCaseStatus.IN_RETENTION
    assert result.offers_made == ["N1"]
    assert result.within_deadline is True
