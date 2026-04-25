# tests/unit/use_cases/loja_express/test_criar_caso.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexoia.application.use_cases.loja_express.criar_caso import CriarCasoLojaExpress
from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus
from nexoia.domain.entities.scheduled_job import JobType


def _make_deps():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.update = AsyncMock()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    scheduler.create_job = AsyncMock(
        side_effect=["job-d1", "job-d3", "job-d5", "job-d7"]
    )
    return repo, chatnexo, scheduler


@pytest.mark.asyncio
async def test_creates_case_and_saves_to_repo():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    result = await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    repo.save.assert_called_once()
    saved_case = repo.save.call_args.args[0]
    assert saved_case.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert saved_case.purchase_id == "purchase-abc"
    assert "CASO_CRIADO" in result


@pytest.mark.asyncio
async def test_sends_d0_template_with_correct_variables():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d0"
    assert call_kwargs["variables"]["nome"] == "João Silva"
    assert call_kwargs["variables"]["produto"] == "Loja Express Pack"
    assert call_kwargs["account_id"] == "1"


@pytest.mark.asyncio
async def test_schedules_four_jobs_with_correct_types():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    assert scheduler.create_job.call_count == 4
    job_types_called = [
        c.kwargs["job_type"]
        for c in scheduler.create_job.call_args_list
    ]
    assert JobType.LOJA_EXPRESS_D1 in job_types_called
    assert JobType.LOJA_EXPRESS_D3 in job_types_called
    assert JobType.LOJA_EXPRESS_D5 in job_types_called
    assert JobType.LOJA_EXPRESS_D7 in job_types_called


@pytest.mark.asyncio
async def test_updates_case_with_job_ids_after_scheduling():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    repo.update.assert_called_once()
    updated_case = repo.update.call_args.args[0]
    assert updated_case.scheduled_job_d1_id == "job-d1"
    assert updated_case.scheduled_job_d3_id == "job-d3"
    assert updated_case.scheduled_job_d5_id == "job-d5"
    assert updated_case.scheduled_job_d7_id == "job-d7"


@pytest.mark.asyncio
async def test_result_contains_case_id():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    result = await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    assert "case_id=" in result
