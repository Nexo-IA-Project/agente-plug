from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class Account:
    id: UUID
    name: str
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
