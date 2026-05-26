from __future__ import annotations

from typing import Protocol

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class AgentSelectionStrategy(Protocol):
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent: ...
