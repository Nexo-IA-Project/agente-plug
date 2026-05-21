from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessagePayload(BaseModel):
    """Payload enviado pelo serviço de processamento para /webhook/message."""

    account_id: int
    conversation_id: int
    inbox_id: int
    contact_id: int
    contact_phone: str
    contact_name: str | None = None
    message_id: str
    text: str
    occurred_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
