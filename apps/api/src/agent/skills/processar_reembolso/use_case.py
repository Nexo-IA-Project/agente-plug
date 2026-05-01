# apps/api/src/agent/skills/processar_reembolso/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.refund_mutex import RefundMutexPort


class ProcessarReembolso:
    def __init__(self, hubla: HublaPort, refund_mutex: RefundMutexPort) -> None:
        self._hubla = hubla
        self._mutex = refund_mutex

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        lock_key = f"{account_id}:{email}:{produto_id}"
        async with self._mutex.lock(lock_key):
            resultado = await self._hubla.processar_reembolso(
                email=email, produto_id=produto_id, account_id=account_id
            )
            if not resultado.sucesso:
                return {"processado": False, "motivo": resultado.motivo_falha}
            return {
                "processado": True,
                "protocolo": resultado.protocolo,
                "valor": resultado.valor,
                "prazo_estorno": resultado.prazo_estorno,
            }
