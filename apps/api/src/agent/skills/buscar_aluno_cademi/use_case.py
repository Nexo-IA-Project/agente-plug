# apps/api/src/agent/skills/buscar_aluno_cademi/use_case.py
from __future__ import annotations

from shared.domain.ports.cademi_port import CademiPort


class BuscarAlunoCademi:
    def __init__(self, cademi: CademiPort) -> None:
        self._cademi = cademi

    async def execute(self, phone: str, account_id: str) -> dict:
        aluno = await self._cademi.buscar_aluno(phone=phone, account_id=account_id)
        if aluno is None:
            return {"encontrado": False, "mensagem": "Aluno não encontrado na base Cademi."}
        return {
            "encontrado": True,
            "nome": aluno.nome,
            "email": aluno.email,
            "cursos": aluno.cursos_ativos,
        }
