from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Course:
    id: UUID
    account_id: UUID
    name: str
    hubla_id: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
