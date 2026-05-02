from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from agent.context import AgentContext
from agent.skill import BaseSkill
from agent.skills._utils import _load_instructions
from agent.skills.escalar_para_humano.preconditions import PRECONDITIONS
from shared.domain.ports.chatnexo import ChatNexoPort


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = "solicitado_pelo_usuario"


class EscalarParaHumanoSkill(BaseSkill):
    def __init__(self, chatnexo: ChatNexoPort) -> None:
        self._chatnexo = chatnexo

    @property
    def name(self) -> str:
        return "escalar_para_humano"

    @property
    def description(self) -> str:
        return _load_instructions(__file__)

    def params_model(self) -> type[BaseModel]:
        return _Input

    async def handle(self, ctx: AgentContext, **kwargs: Any) -> str:
        reason: str = kwargs.get("reason", "solicitado_pelo_usuario")

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        await self._chatnexo.transfer_to_human(
            account_id=ctx.account_id,
            conversation_id=ctx.conversation_id,
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"
