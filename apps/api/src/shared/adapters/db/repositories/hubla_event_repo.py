from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import HublaEventModel


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
    ) -> HublaEventModel:
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
        return m
