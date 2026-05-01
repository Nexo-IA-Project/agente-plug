from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ActorType(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    HUMAN = "human"


@dataclass(slots=True)
class AuditEvent:
    id: UUID
    account_id: UUID
    actor: ActorType
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime | None = None
