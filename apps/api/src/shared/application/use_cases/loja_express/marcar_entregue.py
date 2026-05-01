# src/nexoia/application/use_cases/loja_express/marcar_entregue.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus

log = structlog.get_logger(__name__)


class MarcarEntregue:
    def __init__(self, repo: Any, scheduler: Any) -> None:
        self._repo = repo
        self._scheduler = scheduler

    async def execute(self, *, case_id: str) -> str:
        case = await self._repo.find_by_id(case_id)
        if case is None:
            log.warning("loja_express_marcar_entregue_not_found", case_id=case_id)
            return f"ERRO: caso {case_id} não encontrado"

        case.loja_entregue = True
        case.status = LojaExpressCaseStatus.ENTREGUE

        jobs_cancelados = 0
        for job_id in [
            case.scheduled_job_d1_id,
            case.scheduled_job_d3_id,
            case.scheduled_job_d5_id,
            case.scheduled_job_d7_id,
        ]:
            if job_id is not None:
                await self._scheduler.cancel_job(job_id)
                jobs_cancelados += 1

        await self._repo.update(case)

        log.info(
            "loja_express_marked_delivered",
            case_id=case.id,
            jobs_cancelados=jobs_cancelados,
        )
        return f"ENTREGUE: case_id={case.id}, jobs_cancelados={jobs_cancelados}"
