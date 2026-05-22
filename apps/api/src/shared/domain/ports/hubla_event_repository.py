from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from shared.domain.entities.hubla_event import HublaEvent


class HublaEventRepository(Protocol):
    async def insert(
        self,
        *,
        account_id: UUID,
        event_type: str,
        hubla_subscription_id: str,
        payload: dict[str, Any],
        hubla_product_id: str = "",
        product_name: str = "",
        payer_phone: str = "",
        payer_email: str = "",
        payer_name: str = "",
        contact_id: UUID | None = None,
    ) -> HublaEvent: ...

    async def mark_processed(
        self, event_id: UUID, *, when: datetime | None = None
    ) -> None: ...
