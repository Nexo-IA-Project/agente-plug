# apps/api/src/agent/skills/verificar_caso_acesso/use_case.py
from __future__ import annotations


class VerificarCasoAcesso:
    def __init__(self, access_repo: object) -> None:
        self._repo = access_repo

    async def execute(self, email: str, account_id: str) -> dict:
        caso = await self._repo.buscar_por_email(email=email, account_id=account_id)
        if caso is None:
            return {"tem_caso": False, "status": "inexistente", "caso_id": None}
        return {"tem_caso": True, "status": caso.status, "caso_id": str(caso.id)}
