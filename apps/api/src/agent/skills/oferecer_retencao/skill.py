from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.oferecer_retencao.preconditions import PRECONDITIONS
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class OfereceRetencaoSkill(BaseSkill):
    def __init__(self, use_case: OfereceRetencao) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "oferecer_retencao"

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
        if not result["tem_oferta"]:
            return "Nenhuma oferta de retenção disponível para este perfil."
        return (
            f"Oferta de retenção disponível: {result['descricao']}. "
            f"Tipo: {result['tipo']}. "
            f"Desconto: R$ {result['valor_desconto']:.2f}."
        )
