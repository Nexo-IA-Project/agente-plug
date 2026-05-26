from __future__ import annotations

import random

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class RandomAgentSelection:
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent:
        return random.choice(agents)
