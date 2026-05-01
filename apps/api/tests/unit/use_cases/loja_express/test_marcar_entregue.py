# tests/unit/use_cases/loja_express/test_marcar_entregue.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexoia.application.use_cases.loja_express.marcar_entregue import MarcarEntregue
from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


def _make_case(
    scheduled_job_d1_id: str | None = "job-d1",
    scheduled_job_d3_id: str | None = "job-d3",
    scheduled_job_d5_id: str | None = None,
    scheduled_job_d7_id: str | None = "job-d7",
) -> LojaExpressCase:
    return LojaExpressCase(
        id="case-le-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        status=LojaExpressCaseStatus.CHECK_D3_ENVIADO,
        scheduled_job_d1_id=scheduled_job_d1_id,
        scheduled_job_d3_id=scheduled_job_d3_id,
        scheduled_job_d5_id=scheduled_job_d5_id,
        scheduled_job_d7_id=scheduled_job_d7_id,
    )


@pytest.mark.asyncio
async def test_marks_case_as_delivered_and_updates():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=_make_case())
    repo.update = AsyncMock()
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="case-le-1")
    repo.update.assert_called_once()
    updated_case = repo.update.call_args.args[0]
    assert updated_case.loja_entregue is True
    assert updated_case.status == LojaExpressCaseStatus.ENTREGUE
    assert "ENTREGUE" in result
    assert "case-le-1" in result
    assert scheduler.cancel_job.call_count == 3  # d1, d3, d7 (d5 is None in _make_case)


@pytest.mark.asyncio
async def test_cancels_only_non_none_job_ids():
    # D5 job is None — only d1, d3, d7 should be cancelled (3 jobs)
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(
        return_value=_make_case(
            scheduled_job_d1_id="job-d1",
            scheduled_job_d3_id="job-d3",
            scheduled_job_d5_id=None,
            scheduled_job_d7_id="job-d7",
        )
    )
    repo.update = AsyncMock()
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="case-le-1")
    assert scheduler.cancel_job.call_count == 3
    cancelled = {c.args[0] for c in scheduler.cancel_job.call_args_list}
    assert cancelled == {"job-d1", "job-d3", "job-d7"}
    assert "jobs_cancelados=3" in result


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="nonexistent-id")
    repo.find_by_id.assert_called_once_with("nonexistent-id")
    assert "ERRO" in result
    repo.update.assert_not_called()
    scheduler.cancel_job.assert_not_called()
