from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessagePayload(BaseModel):
    """Payload enriquecido enviado pelo ChatNexo para /webhook/message."""

    account_id: int
    conversation_id: int
    contact_id: int
    contact_phone: str
    contact_name: str | None = None
    chatnexo_message_id: str
    text: str
    media_urls: list[str] = Field(default_factory=list)
    classification_hint: str | None = None
    occurred_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
