from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared.domain.entities.hubla_event import HublaEvent
from shared.domain.entities.lead import Lead


class LeadRepository(Protocol):
    async def upsert(
        self,
        *,
        account_id: UUID,
        hubla_subscription_id: str,
        event_type: str,
        contact_id: UUID | None = None,
        payer_phone: str = "",
        payer_name: str = "",
        payer_email: str = "",
        payer_document: str | None = None,
        hubla_product_id: str = "",
        product_name: str = "",
        offer_id: str | None = None,
        offer_name: str | None = None,
        amount_total_cents: int | None = None,
        amount_subtotal_cents: int | None = None,
        payment_method: str | None = None,
        subscription_status: str = "unknown",
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
        session_ip: str | None = None,
        session_url: str | None = None,
        fbp: str | None = None,
        event_at: datetime | None = None,
    ) -> Lead: ...

    async def paginate(
        self,
        account_id: UUID,
        *,
        product_id: str | None = None,
        status: str | None = None,
        utm_source: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Lead], int]: ...

    async def find_by_id(self, lead_id: UUID, account_id: UUID) -> Lead | None: ...

    async def get_events(
        self, account_id: UUID, hubla_subscription_id: str
    ) -> list[HublaEvent]: ...
