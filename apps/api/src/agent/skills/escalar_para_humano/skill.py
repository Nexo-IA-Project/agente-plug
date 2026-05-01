# apps/api/src/agent/skills/escalar_para_humano/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.escalar_para_humano.preconditions import PRECONDITIONS
from shared.domain.ports.chatnexo import ChatNexoPort


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = "solicitado_pelo_usuario"


class EscalarParaHumanoTool(BaseTool):
    name: str = "escalar_para_humano"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _chatnexo: ChatNexoPort

    def __init__(self, chatnexo: ChatNexoPort) -> None:
        super().__init__()
        self._chatnexo = chatnexo

    def _run(self, reason: str = "solicitado_pelo_usuario") -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, reason: str = "solicitado_pelo_usuario") -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]
        conversation_id = cfg.get("conversation_id")

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        await self._chatnexo.transfer_to_human(
            account_id=account_id,
            conversation_id=conversation_id,
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"
