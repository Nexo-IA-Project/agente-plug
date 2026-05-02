from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento_com_contexto.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    contexto_aluno: str


class BuscarConhecimentoComContextoSkill(BaseSkill):
    def __init__(self, use_case: BuscarConhecimentoComContexto) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "buscar_conhecimento_com_contexto"

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
            query=kwargs["query"],
            contexto_aluno=kwargs["contexto_aluno"],
            account_id=int(ctx.account_id),
        )
        if not result["encontrado"]:
            if result.get("escalar"):
                return (
                    "Não encontrei informações suficientes na base de conhecimento. "
                    "Vou escalar para um especialista humano."
                )
            return "Não encontrei informações sobre este tópico mesmo com contexto adicional."
        return "\n\n".join(result["chunks"])
