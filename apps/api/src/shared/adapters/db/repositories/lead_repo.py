from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import HublaEventModel, LeadModel


@dataclass
class SqlLeadRepository:
    session: AsyncSession

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
    ) -> LeadModel:
        now = datetime.now(UTC)
        event_time = event_at or now

        values = {
            "id": uuid4(),
            "account_id": account_id,
            "hubla_subscription_id": hubla_subscription_id,
            "contact_id": contact_id,
            "payer_phone": payer_phone,
            "payer_name": payer_name,
            "payer_email": payer_email,
            "payer_document": payer_document,
            "hubla_product_id": hubla_product_id,
            "product_name": product_name,
            "offer_id": offer_id,
            "offer_name": offer_name,
            "amount_total_cents": amount_total_cents,
            "amount_subtotal_cents": amount_subtotal_cents,
            "payment_method": payment_method,
            "subscription_status": subscription_status,
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_content": utm_content,
            "utm_term": utm_term,
            "session_ip": session_ip,
            "session_url": session_url,
            "fbp": fbp,
            "first_seen_at": event_time,
            "activated_at": event_time if event_type == "subscription.activated" else None,
            "last_event_at": event_time,
            "last_event_type": event_type,
            "created_at": now,
            "updated_at": now,
        }

        stmt = pg_insert(LeadModel).values(**values)
        # Em conflito (mesmo (account_id, hubla_subscription_id)):
        # atualiza apenas status, last_event_*, updated_at — preserva UTMs originais.
        update_set: dict = {
            "subscription_status": stmt.excluded.subscription_status,
            "last_event_at": stmt.excluded.last_event_at,
            "last_event_type": stmt.excluded.last_event_type,
            "updated_at": stmt.excluded.updated_at,
        }
        if event_type == "subscription.activated":
            # Só seta activated_at quando o evento de ativação chega
            update_set["activated_at"] = stmt.excluded.activated_at
        if contact_id is not None:
            update_set["contact_id"] = stmt.excluded.contact_id

        stmt = stmt.on_conflict_do_update(
            constraint="uq_leads_account_subscription",
            set_=update_set,
        )
        await self.session.execute(stmt)
        await self.session.flush()

        # Buscar pelo natural key (id pode ter sido descartado por conflito)
        q = select(LeadModel).where(
            LeadModel.account_id == account_id,
            LeadModel.hubla_subscription_id == hubla_subscription_id,
        )
        return (await self.session.execute(q)).scalar_one()

    async def list(
        self,
        account_id: UUID,
        *,
        product_id: str | None = None,
        status: str | None = None,
        utm_source: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[LeadModel], int]:
        stmt = select(LeadModel).where(LeadModel.account_id == account_id)
        if product_id:
            stmt = stmt.where(LeadModel.hubla_product_id == product_id)
        if status:
            stmt = stmt.where(LeadModel.subscription_status == status)
        if utm_source:
            stmt = stmt.where(LeadModel.utm_source == utm_source)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            stmt.order_by(LeadModel.last_event_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_events(
        self, account_id: UUID, hubla_subscription_id: str
    ) -> list[HublaEventModel]:
        stmt = (
            select(HublaEventModel)
            .where(
                HublaEventModel.account_id == account_id,
                HublaEventModel.hubla_subscription_id == hubla_subscription_id,
            )
            .order_by(HublaEventModel.received_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
