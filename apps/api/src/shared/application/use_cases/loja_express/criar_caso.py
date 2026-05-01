# src/nexoia/application/use_cases/loja_express/criar_caso.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus
from nexoia.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


class CriarCasoLojaExpress:
    def __init__(self, repo: Any, chatnexo: Any, scheduler: Any) -> None:
        self._repo = repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler

    async def execute(
        self,
        *,
        account_id: int,
        contact_id: str,
        conversation_id: str,
        purchase_id: str,
        product_name: str,
        student_email: str,
        contact_name: str,
    ) -> str:
        account_id_str = str(account_id)
        now = datetime.now(UTC)

        case = LojaExpressCase(
            account_id=account_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            purchase_id=purchase_id,
            product_name=product_name,
            student_email=student_email,
            status=LojaExpressCaseStatus.AGUARDANDO_FORMULARIO,
        )
        await self._repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d0",
            variables={"nome": contact_name, "produto": product_name},
        )

        job_d1_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D1,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=24),
        )
        job_d3_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D3,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=72),
        )
        job_d5_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D5,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=120),
        )
        job_d7_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D7,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=168),
        )

        case.scheduled_job_d1_id = str(job_d1_id)
        case.scheduled_job_d3_id = str(job_d3_id)
        case.scheduled_job_d5_id = str(job_d5_id)
        case.scheduled_job_d7_id = str(job_d7_id)
        await self._repo.update(case)

        log.info(
            "loja_express_case_created",
            case_id=case.id,
            account_id=account_id,
            purchase_id=purchase_id,
        )
        return f"CASO_CRIADO: case_id={case.id}"
