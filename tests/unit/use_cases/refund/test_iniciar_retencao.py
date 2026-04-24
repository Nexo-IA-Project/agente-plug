from __future__ import annotations
import pytest
from unittest.mock import AsyncMock
from nexoia.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus


def _make_case(
    offers_made: list[str] | None = None,
    within_deadline: bool | None = True,
    is_duplicate: bool = False,
) -> RefundCase:
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        within_deadline=within_deadline,
        is_duplicate_purchase=is_duplicate,
    )
    case.offers_made = offers_made or []
    return case


@pytest.mark.asyncio
async def test_offers_n1_when_no_offers_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case())
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "OFERTA_N1" in result
    repo.update.assert_called_once()
    updated_case = repo.update.call_args[0][0]
    assert "N1" in updated_case.offers_made


@pytest.mark.asyncio
async def test_offers_n2_when_n1_already_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1"]))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "OFERTA_N2" in result
    updated_case = repo.update.call_args[0][0]
    assert "N2" in updated_case.offers_made


@pytest.mark.asyncio
async def test_returns_retention_exhausted_when_both_offers_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "RETENCAO_ESGOTADA" in result


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=None)
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_returns_error_when_not_within_deadline():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(within_deadline=False))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_status_set_to_in_retention_after_offer():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case())
    uc = IniciarRetencao(repo)
    await uc.execute(1, "5511999990000")
    updated_case = repo.update.call_args[0][0]
    assert updated_case.status == RefundCaseStatus.IN_RETENTION
