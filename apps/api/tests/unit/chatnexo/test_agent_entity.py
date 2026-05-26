from uuid import UUID
from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def test_chatnexo_agent_is_frozen():
    agent = ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Ana",
        api_key="secret",
        is_active=True,
    )
    assert agent.name == "Ana"
    assert agent.is_active is True


def test_chatnexo_agent_immutable():
    import pytest
    agent = ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Ana",
        api_key="secret",
        is_active=True,
    )
    with pytest.raises((AttributeError, TypeError)):
        agent.name = "outro"  # type: ignore[misc]
