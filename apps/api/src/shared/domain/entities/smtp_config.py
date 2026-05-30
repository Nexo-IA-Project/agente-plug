from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class SmtpConfig:
    account_id: UUID
    host: str
    port: int
    username: str
    encrypted_password: str
    use_tls: bool
    from_name: str
    from_email: str
    id: str = field(default_factory=lambda: str(uuid4()))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
