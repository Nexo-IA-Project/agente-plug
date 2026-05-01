from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from nexoia.domain.ports.chatnexo import ChatNexoPort


class EscalarParaHumanoInput(BaseModel):
    reason: str = "solicitado_pelo_usuario"


class EscalarParaHumanoTool(BaseTool):
    name: str = "escalar_para_humano"
    description: str = (
        "Transfere o atendimento para um humano.\n"
        "Use quando: aluno pede falar com humano, ou situação não pode ser resolvida automaticamente.\n"
        "Retorna: confirmação de transferência."
    )
    args_schema: Type[BaseModel] = EscalarParaHumanoInput

    chatnexo: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, reason: str = "solicitado_pelo_usuario") -> str:
        cfg = get_config()["configurable"]
        await self.chatnexo.transfer_to_human(
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id"),
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_core_skills(chatnexo: ChatNexoPort) -> list[BaseTool]:
    return [EscalarParaHumanoTool(chatnexo=chatnexo)]
