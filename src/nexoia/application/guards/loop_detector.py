from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoopDetectorGuard:
    threshold: int = 3

    def is_looping(self, recent_agent_replies: list[str]) -> bool:
        if len(recent_agent_replies) < self.threshold:
            return False
        last = recent_agent_replies[-self.threshold :]
        return len(set(last)) == 1
