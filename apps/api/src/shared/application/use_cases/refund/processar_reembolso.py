from __future__ import annotations

from typing import Any

import structlog

from shared.domain.entities.refund_case import RefundCaseStatus
from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.refund_mutex import RefundMutexPort

log = structlog.get_logger(__name__)

_REFUND_MESSAGE = (
    "Tô processando seu reembolso agora! O prazo de estorno de pix é até 72 horas e "
    "cartão de 1 a 2 faturas, ambos dependem da sua operadora. "
    "Você vai receber a confirmação assim que o processamento terminar, tá?"
)


class ProcessarReembolso:
    def __init__(
        self,
        refund_repo: Any,
        hubla: HublaPort,
        refund_mutex: RefundMutexPort,
    ) -> None:
        self._repo = refund_repo
        self._hubla = hubla
        self._mutex = refund_mutex

    async def execute(self, account_id: int, contact_id: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=contact_id)
        if case is None:
            return "ERRO: Caso de reembolso não encontrado."

        if case.purchase_id is None:
            return "ERRO: ID de compra não disponível — execute verificar_elegibilidade primeiro."

        # Invariante MandatoryRetention: bypassa se compra duplicada
        if not case.is_duplicate_purchase:
            if "N2" not in case.offers_made:
                log.warning("mandatory_retention_violated", case_id=case.id, offers=case.offers_made)
                return "ERRO: Retenção obrigatória — N2 não foi oferecido ainda. Chame oferecer_retencao."

        acquired = await self._mutex.acquire(account_id, contact_id, case.purchase_id)
        if not acquired:
            log.warning("refund_mutex_blocked", case_id=case.id)
            return "ERRO: Reembolso já em processamento para esta compra. Aguarde."

        result = await self._hubla.process_refund(case.purchase_id, case.refund_reason or "")
        if not result.success:
            await self._mutex.release(account_id, contact_id, case.purchase_id)
            log.error("refund_failed", case_id=case.id, error=result.error)
            return f"ERRO: Falha ao processar reembolso — {result.error}"

        case.status = RefundCaseStatus.REFUNDED
        case.refund_processed_this_turn = True
        await self._repo.update(case)
        log.info("refund_processed", case_id=case.id, refund_id=result.refund_id)
        return _REFUND_MESSAGE
