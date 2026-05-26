from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ChatNexoAgent:
    id: UUID
    name: str
    api_key: str
    is_active: bool
    created_at: datetime | None = field(default=None)
