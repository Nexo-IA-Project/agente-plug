from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"


@dataclass
class User:
    account_id: int
    name: str
    email: str
    password_hash: str
    role: UserRole
    id: str = field(default_factory=lambda: str(uuid4()))
    avatar: bytes | None = None
    must_change_password: bool = True
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None
