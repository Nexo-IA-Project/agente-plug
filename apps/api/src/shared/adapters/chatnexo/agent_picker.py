from __future__ import annotations

from uuid import UUID

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.domain.entities.chatnexo_agent import ChatNexoAgent
from shared.domain.ports.agent_selection import AgentSelectionStrategy


def build_chatnexo_client(
    *,
    base_url: str,
    agents: list[ChatNexoAgent],
    strategy: AgentSelectionStrategy,
    fallback_api_key: str,
) -> tuple[ChatNexoClient, UUID | None]:
    """Constrói ChatNexoClient a partir de um agente selecionado ou do fallback.

    Retorna (client, agent_id). agent_id é None quando usa a chave de fallback.
    """
    if agents:
        agent = strategy.pick(agents)
        return ChatNexoClient.with_key(base_url, agent.api_key), agent.id
    return ChatNexoClient.with_key(base_url, fallback_api_key), None
