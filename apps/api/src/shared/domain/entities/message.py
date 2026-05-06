from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class MessageDirection(StrEnum):
    IN = "in"
    OUT = "out"


class MessageSource(StrEnum):
    STUDENT = "student"
    AGENT_IA = "agent_ia"
    AGENT_HUMAN = "agent_human"


@dataclass(slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    direction: MessageDirection
    source: MessageSource
    content: str
    correlation_id: str | None = None
    created_at: datetime | None = None
