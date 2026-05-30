from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class Profile:
    id: UUID
    account_id: UUID
    name: str
    is_system: bool
    permissions: list[str] = field(default_factory=list)
