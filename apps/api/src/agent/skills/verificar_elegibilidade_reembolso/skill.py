# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.verificar_elegibilidade_reembolso.preconditions import PRECONDITIONS
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class VerificarElegibilidadeReembolsoTool(BaseTool):
    name: str = "verificar_elegibilidade_reembolso"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: VerificarElegibilidadeReembolso

    def __init__(self, use_case: VerificarElegibilidadeReembolso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, produto_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, produto_id: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if not result["elegivel"]:
            return f"Reembolso não elegível: {result['motivo']}"
        return (
            f"Aluno elegível para reembolso. "
            f"Valor: R$ {result['valor']:.2f}. "
            f"Prazo restante: {result['dias_restantes']} dias."
        )
