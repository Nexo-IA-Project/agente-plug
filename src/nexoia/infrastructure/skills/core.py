from __future__ import annotations

from langchain_core.tools import tool
from langgraph.config import get_config

from nexoia.domain.ports.chatnexo import ChatNexoPort


def make_core_skills(chatnexo: ChatNexoPort) -> list:
    @tool
    async def escalar_para_humano(reason: str = "solicitado_pelo_usuario") -> str:
        """
        Transfere o atendimento para um humano.
        Use quando: aluno pede falar com humano, ou situação não pode ser resolvida automaticamente.
        Retorna: confirmação de transferência.
        """
        cfg = get_config()["configurable"]
        await chatnexo.transfer_to_human(
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id"),
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"

    return [escalar_para_humano]
