from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared.domain.entities.user import UserRole


@dataclass
class Membership:
    identity_id: str
    account_id: UUID
    role: UserRole
    id: str = field(default_factory=lambda: str(uuid4()))
    profile_id: UUID | None = None
    is_owner: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
