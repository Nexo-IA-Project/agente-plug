# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.legal_history_port import LegalHistoryPort


class VerificarElegibilidadeReembolso:
    def __init__(self, hubla: HublaPort, legal_history: LegalHistoryPort) -> None:
        self._hubla = hubla
        self._legal_history = legal_history

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        compra = await self._hubla.buscar_compra(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if compra is None:
            return {"elegivel": False, "motivo": "Compra não encontrada na plataforma Hubla."}

        historico = await self._legal_history.buscar(email=email, account_id=account_id)
        if historico and historico.teve_reembolso:
            return {
                "elegivel": False,
                "motivo": "Aluno já utilizou o direito de reembolso anteriormente.",
            }

        if not compra.dentro_prazo_reembolso:
            return {
                "elegivel": False,
                "motivo": f"Prazo de reembolso expirado. Compra realizada em {compra.data_compra}.",
            }

        return {
            "elegivel": True,
            "motivo": None,
            "dias_restantes": compra.dias_restantes_reembolso,
            "valor": compra.valor,
        }
