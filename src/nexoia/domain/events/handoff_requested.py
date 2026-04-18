from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class HandoffRequested:
    conversation_id: UUID
    reason: str
    silent: bool = False
