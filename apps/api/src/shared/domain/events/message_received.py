from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MessageReceived:
    account_id: UUID
    conversation_id: UUID
    contact_id: UUID
    chatnexo_message_id: str
    text: str
    media_urls: list[str] = field(default_factory=list)
    classification_hint: str | None = None
    occurred_at: datetime | None = None
