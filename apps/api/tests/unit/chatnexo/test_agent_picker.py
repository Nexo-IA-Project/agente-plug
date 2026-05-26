from __future__ import annotations

import pytest
from uuid import UUID

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def _agent(name: str, key: str) -> ChatNexoAgent:
    return ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name=name,
        api_key=key,
        is_active=True,
    )


def test_random_selection_returns_one_of_the_agents():
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    agents = [_agent("Ana", "key-a"), _agent("Bob", "key-b")]
    strategy = RandomAgentSelection()
    result = strategy.pick(agents)
    assert result in agents


def test_random_selection_raises_if_empty():
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    strategy = RandomAgentSelection()
    with pytest.raises(IndexError):
        strategy.pick([])


def test_build_returns_agent_client_when_agents_available():
    from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    agents = [_agent("Ana", "key-ana")]
    client, agent_id = build_chatnexo_client(
        base_url="https://chat.example.com",
        agents=agents,
        strategy=RandomAgentSelection(),
        fallback_api_key="fallback-key",
    )
    assert agent_id == agents[0].id
    assert client is not None


def test_build_returns_fallback_client_when_no_agents():
    from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    client, agent_id = build_chatnexo_client(
        base_url="https://chat.example.com",
        agents=[],
        strategy=RandomAgentSelection(),
        fallback_api_key="fallback-key",
    )
    assert agent_id is None
    assert client is not None
