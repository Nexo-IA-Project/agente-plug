# tests/unit/use_cases/refund/test_processar_reembolso.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock
from nexoia.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.domain.ports.hubla_port import RefundResult

_REFUND_MSG_FRAGMENT = "processando seu reembolso"


def _make_case(
    offers_made: list[str] | None = None,
    is_duplicate: bool = False,
    purchase_id: str = "purchase-1",
) -> RefundCase:
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        purchase_id=purchase_id,
        within_deadline=True,
        is_duplicate_purchase=is_duplicate,
    )
    case.offers_made = offers_made or []
    case.refund_reason = "não quero mais"
    return case


@pytest.mark.asyncio
async def test_happy_path_processes_refund():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-1", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert _REFUND_MSG_FRAGMENT in result
    repo.update.assert_called_once()
    updated = repo.update.call_args[0][0]
    assert updated.status == RefundCaseStatus.REFUNDED


@pytest.mark.asyncio
async def test_mandatory_retention_invariant_blocks_without_n2():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1"]))
    hubla = AsyncMock()
    mutex = AsyncMock()
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    assert "N2" in result
    hubla.process_refund.assert_not_called()


@pytest.mark.asyncio
async def test_mandatory_retention_not_triggered_for_duplicate():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=[], is_duplicate=True))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-2", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert _REFUND_MSG_FRAGMENT in result


@pytest.mark.asyncio
async def test_mutex_blocks_duplicate_job():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=False)  # já bloqueado
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    assert "em processamento" in result.lower()
    hubla.process_refund.assert_not_called()


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=None)
    uc = ProcessarReembolso(repo, AsyncMock(), AsyncMock())
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_sets_refund_processed_this_turn_flag():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-3", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    await uc.execute(1, "5511999990000")
    updated = repo.update.call_args[0][0]
    assert updated.refund_processed_this_turn is True


@pytest.mark.asyncio
async def test_hubla_failure_releases_mutex_and_returns_error():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=False, refund_id=None, error="timeout"))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    mutex.release = AsyncMock()
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    mutex.release.assert_called_once()
