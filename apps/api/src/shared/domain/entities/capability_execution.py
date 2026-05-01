from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    HANDOFF = "handoff"
    ERROR = "error"


@dataclass(slots=True)
class CapabilityExecution:
    id: UUID
    conversation_id: UUID
    capability_name: str
    intent_confidence: float
    tools_called: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    correlation_id: str | None = None
    created_at: datetime | None = None
