from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import AuditEventModel
from shared.domain.entities.audit_event import AuditEvent


def _to_entity(m: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=m.id,
        account_id=m.account_id,
        actor=m.actor,
        user_id=m.user_id,
        user_name=m.user_name,
        action=m.action,
        resource_type=m.resource_type,
        resource_id=m.resource_id,
        ip_address=m.ip_address,
        geo_city=m.geo_city,
        geo_country=m.geo_country,
        geo_region=m.geo_region,
        metadata=m.metadata_json,
        correlation_id=m.correlation_id,
        created_at=m.created_at,
    )


class SqlAuditRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def save(self, event: AuditEvent) -> None:
        model = AuditEventModel(
            id=event.id,
            account_id=event.account_id,
            actor=event.actor,
            user_id=event.user_id,
            user_name=event.user_name,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            ip_address=event.ip_address,
            geo_city=event.geo_city,
            geo_country=event.geo_country,
            geo_region=event.geo_region,
            metadata_json=event.metadata,
            correlation_id=event.correlation_id,
        )
        self.session.add(model)
        await self.session.commit()

    async def update_geo(
        self,
        event_id: UUID,
        *,
        city: str,
        country: str,
        region: str,
    ) -> None:
        await self.session.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == event_id)
            .values(geo_city=city, geo_country=country, geo_region=region)
        )
        await self.session.commit()

    async def paginate(
        self,
        account_id: UUID,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        exclude_auth: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[AuditEvent], int]:
        base = (
            select(AuditEventModel)
            .where(AuditEventModel.account_id == account_id)
            .where(AuditEventModel.actor != "system")
        )
        if resource_type is not None:
            base = base.where(AuditEventModel.resource_type == resource_type)
        if exclude_auth:
            base = base.where(AuditEventModel.resource_type != "auth")
        if user_id is not None:
            base = base.where(AuditEventModel.user_id == user_id)
        if action is not None:
            base = base.where(AuditEventModel.action == action)
        if date_from is not None:
            base = base.where(AuditEventModel.created_at >= date_from)
        if date_to is not None:
            base = base.where(AuditEventModel.created_at <= date_to)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        rows = (
            await self.session.execute(
                base.order_by(AuditEventModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return [_to_entity(r) for r in rows], total
