from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.refund_case import RefundCaseStatus

log = structlog.get_logger(__name__)

# TODO CQ-R02: replace with real per-product offers (from config or DB)
_OFFERS: dict[str, str] = {
    "N1": "Oferta N1: acesso por mais 30 dias sem custo adicional.",
    "N2": "Oferta N2: desconto de 50% na próxima renovação.",
}


class IniciarRetencao:
    def __init__(self, refund_repo: Any) -> None:
        self._repo = refund_repo

    async def execute(self, account_id: int, phone: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "ERRO: Caso de reembolso não encontrado."

        if case.within_deadline is False:
            return "ERRO: Aluno fora do prazo CDC — não iniciar retenção."

        offers_made = list(case.offers_made)

        if "N1" not in offers_made:
            offers_made.append("N1")
            case.offers_made = offers_made
            case.status = RefundCaseStatus.IN_RETENTION
            await self._repo.update(case)
            log.info("retention_offer", offer="N1", case_id=case.id)
            return f"OFERTA_N1: {_OFFERS['N1']}"

        if "N2" not in offers_made:
            offers_made.append("N2")
            case.offers_made = offers_made
            case.status = RefundCaseStatus.IN_RETENTION
            await self._repo.update(case)
            log.info("retention_offer", offer="N2", case_id=case.id)
            return f"OFERTA_N2: {_OFFERS['N2']}"

        log.info("retention_exhausted", case_id=case.id)
        return "RETENCAO_ESGOTADA: N1 e N2 já oferecidos. Processar reembolso."
