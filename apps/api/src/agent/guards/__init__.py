from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    response: str = ""
    reason: str = ""
    forced_instruction: str = ""


class Guard(Protocol):
    def check(self, message: str, state: dict) -> GuardResult: ...


class GuardService:
    def __init__(self, guards: list[Guard]) -> None:
        self._guards = guards

    def check(self, message: str, state: dict) -> GuardResult:
        for guard in self._guards:
            result = guard.check(message, state)
            if result.blocked:
                return result
        return GuardResult(blocked=False)


# Deferred imports to avoid circular dependency (submodules import GuardResult from here)
from nexoia.domain.policies.guards.legal_mention import LegalMentionGuard  # noqa: E402
from nexoia.domain.policies.guards.loop_detector import LoopDetectorGuard  # noqa: E402

__all__ = [
    "GuardResult",
    "GuardService",
    "LegalMentionGuard",
    "LoopDetectorGuard",
]
