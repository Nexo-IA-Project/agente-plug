from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MessageReceived:
    account_id: UUID
    conversation_id: UUID
    contact_id: UUID
    message_id: str
    text: str
    occurred_at: datetime | None = None
