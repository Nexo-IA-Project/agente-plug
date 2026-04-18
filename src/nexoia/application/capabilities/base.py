from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CapabilityResult:
    outcome: str  # "success" | "handoff" | "error"
    response_text: str | None = None
    extra: dict[str, Any] | None = None


class Capability(ABC):
    name: str

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> CapabilityResult: ...
