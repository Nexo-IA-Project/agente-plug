from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class AdminRole(StrEnum):
    ADMIN  = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AdminUser:
    account_id: int
    email: str
    password_hash: str
    role: AdminRole
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
