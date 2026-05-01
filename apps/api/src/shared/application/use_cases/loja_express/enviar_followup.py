# src/nexoia/application/use_cases/loja_express/enviar_followup.py
from __future__ import annotations

import contextlib
from typing import Any

import structlog

from shared.domain.entities.loja_express_case import LojaExpressCaseStatus

log = structlog.get_logger(__name__)


class EnviarFollowup:
    def __init__(
        self,
        repo: Any,
        chatnexo: Any,
        scheduler: Any,
        loja_express_port: Any,
    ) -> None:
        self._repo = repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler
        self._loja_express_port = loja_express_port

    async def execute(
        self,
        *,
        account_id: int,
        contact_id: str,
        conversation_id: str,
        day: int,
    ) -> str:
        account_id_str = str(account_id)

        case = await self._repo.find_by_purchase_context(
            account_id=account_id, contact_id=contact_id
        )
        if case is None:
            log.warning(
                "loja_express_followup_case_not_found",
                account_id=account_id,
                contact_id=contact_id,
                day=day,
            )
            return "ERRO: caso loja express não encontrado"

        # Guard: loja already delivered — cancel all pending jobs
        if case.loja_entregue is True:
            for job_id in [
                case.scheduled_job_d1_id,
                case.scheduled_job_d3_id,
                case.scheduled_job_d5_id,
                case.scheduled_job_d7_id,
            ]:
                if job_id is not None:
                    await self._scheduler.cancel_job(job_id)
            log.info("loja_express_followup_ignored_delivered", case_id=case.id, day=day)
            return "IGNORADO: loja já entregue"

        if day == 1:
            return await self._handle_d1(case, account_id_str, conversation_id)
        elif day == 3:
            return await self._handle_d3(case, account_id_str, conversation_id)
        elif day == 5:
            return await self._handle_d5(case, account_id_str, conversation_id)
        elif day == 7:
            return await self._handle_d7(case, account_id_str, conversation_id)
        else:
            log.warning("loja_express_followup_unknown_day", day=day, case_id=case.id)
            return f"ERRO: dia desconhecido {day}"

    async def _handle_d1(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        with contextlib.suppress(NotImplementedError):
            await self._loja_express_port.is_form_submitted(case.id)

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d1",
            variables={"produto": case.product_name},
        )
        case.status = LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
        await self._repo.update(case)
        log.info("loja_express_d1_sent", case_id=case.id)
        return "FOLLOWUP_D1: template enviado"

    async def _handle_d3(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        with contextlib.suppress(NotImplementedError):
            await self._loja_express_port.get_store_status(case.id)
            # Result intentionally discarded — D3 only sends a status-check template

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d3",
            variables={"produto": case.product_name},
        )
        case.status = LojaExpressCaseStatus.CHECK_D3_ENVIADO
        await self._repo.update(case)
        log.info("loja_express_d3_sent", case_id=case.id)
        return "FOLLOWUP_D3: template enviado"

    async def _handle_d5(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        store_status = "pending"
        with contextlib.suppress(NotImplementedError):
            store_status = await self._loja_express_port.get_store_status(case.id)

        if store_status != "delivered":
            reason = "loja_express_d5_bloqueio"
            await self._chatnexo.transfer_to_human(
                account_id=account_id_str,
                conversation_id=conversation_id,
                reason=reason,
            )
            case.status = LojaExpressCaseStatus.ALERTA_D5_ENVIADO
            await self._repo.update(case)
            log.info("loja_express_d5_escalated", case_id=case.id, reason=reason)
            return f"ESCALADO: reason={reason}"

        case.loja_entregue = True
        case.status = LojaExpressCaseStatus.ENTREGUE
        await self._repo.update(case)
        log.info("loja_express_d5_delivered", case_id=case.id)
        return "FOLLOWUP_D5: loja entregue, nenhuma ação necessária"

    async def _handle_d7(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d7",
            variables={"produto": case.product_name},
        )
        reason = "loja_express_d7_prazo_critico"
        await self._chatnexo.transfer_to_human(
            account_id=account_id_str,
            conversation_id=conversation_id,
            reason=reason,
        )
        case.status = LojaExpressCaseStatus.PRAZO_CRITICO_D7
        await self._repo.update(case)
        log.info("loja_express_d7_escalated", case_id=case.id, reason=reason)
        return f"ESCALADO: reason={reason}"
