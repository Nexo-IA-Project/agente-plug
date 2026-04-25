# tests/unit/use_cases/loja_express/test_enviar_followup.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from nexoia.application.use_cases.loja_express.enviar_followup import EnviarFollowup
from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


def _make_case(
    loja_entregue: bool = False,
    status: LojaExpressCaseStatus = LojaExpressCaseStatus.AGUARDANDO_FORMULARIO,
    scheduled_job_d1_id: str | None = "job-d1",
    scheduled_job_d3_id: str | None = "job-d3",
    scheduled_job_d5_id: str | None = "job-d5",
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
        loja_entregue=loja_entregue,
        status=status,
        scheduled_job_d1_id=scheduled_job_d1_id,
        scheduled_job_d3_id=scheduled_job_d3_id,
        scheduled_job_d5_id=scheduled_job_d5_id,
        scheduled_job_d7_id=scheduled_job_d7_id,
    )


def _make_deps(case: LojaExpressCase | None = None):
    repo = AsyncMock()
    repo.find_by_purchase_context = AsyncMock(return_value=case or _make_case())
    repo.update = AsyncMock()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    loja_express_port = AsyncMock()
    loja_express_port.is_form_submitted = AsyncMock(return_value=False)
    loja_express_port.get_store_status = AsyncMock(return_value="pending")
    return repo, chatnexo, scheduler, loja_express_port


@pytest.mark.asyncio
async def test_guard_returns_ignorado_when_loja_already_delivered():
    case = _make_case(loja_entregue=True)
    repo, chatnexo, scheduler, loja_express_port = _make_deps(case=case)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "IGNORADO" in result
    assert "loja já entregue" in result
    chatnexo.send_template.assert_not_called()


@pytest.mark.asyncio
async def test_guard_cancels_pending_jobs_when_loja_delivered():
    case = _make_case(loja_entregue=True)
    repo, chatnexo, scheduler, loja_express_port = _make_deps(case=case)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert scheduler.cancel_job.call_count == 4
    cancelled = {c.args[0] for c in scheduler.cancel_job.call_args_list}
    assert cancelled == {"job-d1", "job-d3", "job-d5", "job-d7"}


@pytest.mark.asyncio
async def test_d1_sends_lembrete_template_and_updates_status():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d1"
    assert "FOLLOWUP_D1" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO


@pytest.mark.asyncio
async def test_d1_treats_stub_not_implemented_as_false():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    loja_express_port.is_form_submitted = AsyncMock(side_effect=NotImplementedError)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "FOLLOWUP_D1" in result


@pytest.mark.asyncio
async def test_d3_sends_check_template_and_updates_status():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=3)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d3"
    assert "FOLLOWUP_D3" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.CHECK_D3_ENVIADO


@pytest.mark.asyncio
async def test_d5_transfers_to_human_when_not_delivered():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    loja_express_port.get_store_status = AsyncMock(return_value="pending")
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=5)
    chatnexo.transfer_to_human.assert_called_once()
    call_kwargs = chatnexo.transfer_to_human.call_args.kwargs
    assert call_kwargs["reason"] == "loja_express_d5_bloqueio"
    assert "ESCALADO" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.ALERTA_D5_ENVIADO


@pytest.mark.asyncio
async def test_d7_sends_template_and_transfers_to_human():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=7)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d7"
    chatnexo.transfer_to_human.assert_called_once()
    transfer_kwargs = chatnexo.transfer_to_human.call_args.kwargs
    assert transfer_kwargs["reason"] == "loja_express_d7_prazo_critico"
    assert "ESCALADO" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.PRAZO_CRITICO_D7


@pytest.mark.asyncio
async def test_case_not_found_returns_error():
    repo = AsyncMock()
    repo.find_by_purchase_context = AsyncMock(return_value=None)
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    loja_express_port = AsyncMock()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "ERRO" in result
    chatnexo.send_template.assert_not_called()
