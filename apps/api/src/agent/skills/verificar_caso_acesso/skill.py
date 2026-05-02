from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.verificar_caso_acesso.preconditions import PRECONDITIONS
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class VerificarCasoAcessoSkill(BaseSkill):
    def __init__(self, use_case: VerificarCasoAcesso) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "verificar_caso_acesso"

    @property
    def description(self) -> str:
        return _load_instructions(__file__)

    def params_model(self) -> type[BaseModel]:
        return _Input

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(email=kwargs["email"], account_id=ctx.account_id)
        if not result["tem_caso"]:
            return "Nenhum caso de acesso encontrado para este aluno."
        return f"Caso encontrado. Status: {result['status']}. ID: {result['caso_id']}."
