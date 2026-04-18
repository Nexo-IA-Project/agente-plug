from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from nexoia.domain.value_objects.phone import Phone


@dataclass(slots=True)
class Contact:
    id: UUID
    account_id: UUID
    phone: Phone
    name: str | None = None
    email: str | None = None
    long_term_facts: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
