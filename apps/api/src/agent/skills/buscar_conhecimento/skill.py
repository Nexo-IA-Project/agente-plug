from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class BuscarConhecimentoSkill(BaseSkill):
    def __init__(self, use_case: BuscarConhecimento) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "buscar_conhecimento"

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
            query=kwargs["query"], account_id=UUID(ctx.account_id)
        )
        if not result["encontrado"]:
            return "Não encontrei informações sobre este tópico na base de conhecimento."
        return "\n\n".join(result["chunks"])
