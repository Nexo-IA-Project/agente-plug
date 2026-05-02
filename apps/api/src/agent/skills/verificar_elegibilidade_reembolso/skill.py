from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.verificar_elegibilidade_reembolso.preconditions import PRECONDITIONS
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class VerificarElegibilidadeReembolsoSkill(BaseSkill):
    def __init__(self, use_case: VerificarElegibilidadeReembolso) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "verificar_elegibilidade_reembolso"

    @property
    def description(self) -> str:
        return _load_instructions(__file__)

    def params_model(self) -> type[BaseModel]:
        return _Input

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=kwargs["email"], produto_id=kwargs["produto_id"], account_id=ctx.account_id
        )
        if not result["elegivel"]:
            return f"Reembolso não elegível: {result['motivo']}"
        return (
            f"Aluno elegível para reembolso. "
            f"Valor: R$ {result['valor']:.2f}. "
            f"Prazo restante: {result['dias_restantes']} dias."
        )
