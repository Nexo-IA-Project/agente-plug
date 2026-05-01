from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.entities.webhook_event import (
    WebhookEvent,
    WebhookSource,
    WebhookStatus,
)
from shared.adapters.db.models import WebhookEventModel


@dataclass
class WebhookEventRepository:
    session: AsyncSession

    async def insert_if_new(
        self,
        *,
        source: WebhookSource,
        external_id: str,
        payload: dict,
        correlation_id: str | None = None,
    ) -> WebhookEvent | None:
        """Insert or return None if already exists (idempotency)."""
        stmt = (
            insert(WebhookEventModel)
            .values(
                id=uuid.uuid4(),
                source=source.value,
                external_id=external_id,
                payload=payload,
                status=WebhookStatus.PENDING.value,
                correlation_id=correlation_id,
            )
            .on_conflict_do_nothing(index_elements=["source", "external_id"])
            .returning(WebhookEventModel)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return WebhookEvent(
            id=model.id,
            source=WebhookSource(model.source),
            external_id=model.external_id,
            payload=dict(model.payload),
            status=WebhookStatus(model.status),
            correlation_id=model.correlation_id,
            created_at=model.created_at,
            processed_at=model.processed_at,
        )
