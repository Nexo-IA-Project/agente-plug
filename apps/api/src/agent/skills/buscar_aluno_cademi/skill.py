from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.buscar_aluno_cademi.preconditions import PRECONDITIONS
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str


class BuscarAlunoCademiSkill(BaseSkill):
    def __init__(self, use_case: BuscarAlunoCademi) -> None:
        self._use_case = use_case

    @property
    def name(self) -> str:
        return "buscar_aluno_cademi"

    @property
    def description(self) -> str:
        return _load_instructions(__file__)

    def params_model(self) -> type[BaseModel]:
        return _Input

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(phone=kwargs["phone"], account_id=ctx.account_id)
        if not result["encontrado"]:
            return result["mensagem"]
        return (
            f"Aluno encontrado: {result['nome']} ({result['email']}). "
            f"Cursos ativos: {', '.join(result['cursos']) or 'nenhum'}."
        )
