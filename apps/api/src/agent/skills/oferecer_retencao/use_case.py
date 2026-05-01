# apps/api/src/agent/skills/oferecer_retencao/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort


class OfereceRetencao:
    def __init__(self, hubla: HublaPort, refund_repo: object) -> None:
        self._hubla = hubla
        self._refund_repo = refund_repo

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        oferta = await self._hubla.buscar_oferta_retencao(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if oferta is None:
            return {"tem_oferta": False}

        await self._refund_repo.registrar_tentativa_retencao(
            email=email, produto_id=produto_id, account_id=account_id, oferta_id=oferta.id
        )
        return {
            "tem_oferta": True,
            "descricao": oferta.descricao,
            "valor_desconto": oferta.valor_desconto,
            "tipo": oferta.tipo,
        }
