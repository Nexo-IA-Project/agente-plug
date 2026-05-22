from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import HublaEventModel
from shared.domain.entities.hubla_event import HublaEvent


def _to_entity(m: HublaEventModel) -> HublaEvent:
    return HublaEvent(
        id=m.id,
        account_id=m.account_id,
        event_type=m.event_type,
        hubla_subscription_id=m.hubla_subscription_id,
        hubla_product_id=m.hubla_product_id,
        product_name=m.product_name,
        payer_phone=m.payer_phone,
        payer_email=m.payer_email,
        payer_name=m.payer_name,
        contact_id=m.contact_id,
        payload=m.payload,
        received_at=m.received_at,
        processed_at=m.processed_at,
    )


@dataclass
class SqlHublaEventRepository:
    session: AsyncSession

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
    ) -> HublaEvent:
        m = HublaEventModel(
            id=uuid4(),
            account_id=account_id,
            event_type=event_type,
            hubla_subscription_id=hubla_subscription_id,
            hubla_product_id=hubla_product_id,
            product_name=product_name,
            payer_phone=payer_phone,
            payer_email=payer_email,
            payer_name=payer_name,
            contact_id=contact_id,
            payload=payload,
            received_at=datetime.now(UTC),
            processed_at=None,
        )
        self.session.add(m)
        await self.session.flush()
        return _to_entity(m)

    async def mark_processed(self, event_id: UUID, *, when: datetime | None = None) -> None:
        """Marca hubla_events.processed_at após o worker terminar de rotear o evento."""
        m = await self.session.get(HublaEventModel, event_id)
        if m is None:
            return
        m.processed_at = when or datetime.now(UTC)
        await self.session.flush()
