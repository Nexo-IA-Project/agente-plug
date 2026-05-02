# tests/unit/infrastructure/db/test_loja_express_case_repo.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.db.repositories.loja_express_case_repo import LojaExpressCaseRepository
from shared.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


def _make_model(
    status: str = "aguardando_formulario",
    loja_entregue: bool = False,
    form_submitted: bool = False,
    scheduled_job_d1_id: str | None = None,
    scheduled_job_d3_id: str | None = None,
    scheduled_job_d5_id: str | None = None,
    scheduled_job_d7_id: str | None = None,
):
    m = MagicMock()
    m.id = "case-le-1"
    m.account_id = 1
    m.contact_id = "5511999990000"
    m.conversation_id = "conv-1"
    m.purchase_id = "purchase-abc"
    m.product_name = "Loja Express Pack"
    m.student_email = "aluno@test.com"
    m.form_submitted = form_submitted
    m.loja_entregue = loja_entregue
    m.status = status
    m.scheduled_job_d1_id = scheduled_job_d1_id
    m.scheduled_job_d3_id = scheduled_job_d3_id
    m.scheduled_job_d5_id = scheduled_job_d5_id
    m.scheduled_job_d7_id = scheduled_job_d7_id
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


@pytest.mark.asyncio
async def test_save_adds_model_and_flushes():
    session = AsyncMock()
    session.add = MagicMock()  # session.add is synchronous in SQLAlchemy AsyncSession
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    await repo.save(case)
    session.add.assert_called_once()
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_persists_all_fields():
    session = AsyncMock()
    mock_model = _make_model()
    session.get = AsyncMock(return_value=mock_model)
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        id="case-le-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        status=LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO,
        form_submitted=True,
        loja_entregue=False,
        scheduled_job_d1_id="job-d1",
        scheduled_job_d3_id="job-d3",
        scheduled_job_d5_id="job-d5",
        scheduled_job_d7_id="job-d7",
    )
    await repo.update(case)
    session.flush.assert_called_once()
    assert mock_model.status == "lembrete_d1_enviado"
    assert mock_model.form_submitted is True
    assert mock_model.loja_entregue is False
    assert mock_model.scheduled_job_d1_id == "job-d1"
    assert mock_model.scheduled_job_d3_id == "job-d3"
    assert mock_model.scheduled_job_d5_id == "job-d5"
    assert mock_model.scheduled_job_d7_id == "job-d7"


@pytest.mark.asyncio
async def test_update_raises_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        id="missing-id",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    with pytest.raises(ValueError, match="missing-id"):
        await repo.update(case)


@pytest.mark.asyncio
async def test_find_by_purchase_context_returns_none_when_not_found():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_purchase_context(account_id=1, contact_id="5511999990000")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_purchase_context_maps_to_entity():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = _make_model(
        status="lembrete_d1_enviado",
        scheduled_job_d1_id="job-d1",
    )
    session.execute = AsyncMock(return_value=execute_result)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_purchase_context(account_id=1, contact_id="5511999990000")
    assert result is not None
    assert result.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert result.scheduled_job_d1_id == "job-d1"
    assert result.account_id == 1
    assert result.purchase_id == "purchase-abc"


@pytest.mark.asyncio
async def test_find_by_id_returns_none_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_id("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_id_returns_entity():
    session = AsyncMock()
    session.get = AsyncMock(return_value=_make_model(loja_entregue=True, status="entregue"))
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_id("case-le-1")
    assert result is not None
    assert result.loja_entregue is True
    assert result.status == LojaExpressCaseStatus.ENTREGUE
