from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class MetaTemplate:
    id: UUID
    account_id: UUID
    name: str
    meta_template_id: str
    language: str
    variables_schema: dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    last_synced_at: datetime | None = None
