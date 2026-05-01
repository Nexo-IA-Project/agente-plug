from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class IdleStage(StrEnum):
    PING = "ping"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class IdleDetected:
    conversation_id: UUID
    stage: IdleStage
