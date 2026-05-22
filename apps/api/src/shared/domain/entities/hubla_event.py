from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class HublaEvent:
    """Log imutável de um evento Hubla recebido. Uma linha por evento."""

    id: UUID
    account_id: UUID
    event_type: str
    hubla_subscription_id: str
    hubla_product_id: str
    product_name: str
    payer_phone: str
    payer_email: str
    payer_name: str
    payload: dict[str, Any]
    received_at: datetime
    contact_id: UUID | None = None
    processed_at: datetime | None = None
