from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import HublaEventModel, LeadModel
from shared.domain.entities.hubla_event import HublaEvent
from shared.domain.entities.lead import Lead


def _to_lead_entity(m: LeadModel) -> Lead:
    return Lead(
        id=m.id,
        account_id=m.account_id,
        hubla_subscription_id=m.hubla_subscription_id,
        contact_id=m.contact_id,
        payer_phone=m.payer_phone,
        payer_name=m.payer_name,
        payer_email=m.payer_email,
        payer_document=m.payer_document,
        hubla_product_id=m.hubla_product_id,
        product_name=m.product_name,
        offer_id=m.offer_id,
        offer_name=m.offer_name,
        amount_total_cents=m.amount_total_cents,
        amount_subtotal_cents=m.amount_subtotal_cents,
        payment_method=m.payment_method,
        subscription_status=m.subscription_status,
        utm_source=m.utm_source,
        utm_medium=m.utm_medium,
        utm_campaign=m.utm_campaign,
        utm_content=m.utm_content,
        utm_term=m.utm_term,
        session_ip=m.session_ip,
        session_url=m.session_url,
        fbp=m.fbp,
        first_seen_at=m.first_seen_at,
        activated_at=m.activated_at,
        last_event_at=m.last_event_at,
        last_event_type=m.last_event_type,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_event_entity(m: HublaEventModel) -> HublaEvent:
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
    ) -> Lead:
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
        update_set: dict[str, Any] = {
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
        m = (await self.session.execute(q)).scalar_one()
        return _to_lead_entity(m)

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
    ) -> tuple[list[Lead], int]:
        stmt = select(LeadModel).where(LeadModel.account_id == account_id)
        if product_id:
            stmt = stmt.where(LeadModel.hubla_product_id == product_id)
        if status:
            stmt = stmt.where(LeadModel.subscription_status == status)
        if utm_source:
            stmt = stmt.where(LeadModel.utm_source == utm_source)
        if date_from is not None:
            stmt = stmt.where(LeadModel.last_event_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(LeadModel.last_event_at <= date_to)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            stmt.order_by(LeadModel.last_event_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_lead_entity(m) for m in rows], total

    async def find_by_id(self, lead_id: UUID, account_id: UUID) -> Lead | None:
        m = await self.session.get(LeadModel, lead_id)
        if m is None or m.account_id != account_id:
            return None
        return _to_lead_entity(m)

    async def get_events(self, account_id: UUID, hubla_subscription_id: str) -> list[HublaEvent]:
        stmt = (
            select(HublaEventModel)
            .where(
                HublaEventModel.account_id == account_id,
                HublaEventModel.hubla_subscription_id == hubla_subscription_id,
            )
            .order_by(HublaEventModel.received_at.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_event_entity(m) for m in rows]

    async def get_enrollments(
        self, account_id: UUID, hubla_subscription_id: str
    ) -> list[dict[str, Any]]:
        """Retorna enrollments + steps de um lead (purchase_id = hubla_subscription_id).

        Cada step inclui o `scheduled_for` resolvido via JOIN com scheduled_jobs
        (campo `run_at`). Steps sem job associado retornam scheduled_for=None.
        """
        from shared.adapters.db.models import (
            OnboardingEnrollmentModel,
            OnboardingEnrollmentStepModel,
            OnboardingFlowModel,
            ScheduledJobModel,
        )

        # 1. Busca enrollments do lead (purchase_id = hubla_subscription_id)
        enr_stmt = (
            select(OnboardingEnrollmentModel, OnboardingFlowModel.name)
            .outerjoin(
                OnboardingFlowModel, OnboardingFlowModel.id == OnboardingEnrollmentModel.flow_id
            )
            .where(
                OnboardingEnrollmentModel.account_id == account_id,
                OnboardingEnrollmentModel.purchase_id == hubla_subscription_id,
            )
            .order_by(OnboardingEnrollmentModel.created_at.asc())
        )
        enr_rows = (await self.session.execute(enr_stmt)).all()

        if not enr_rows:
            return []

        enrollment_ids = [row[0].id for row in enr_rows]

        # 2. Busca steps de todos os enrollments + JOIN com scheduled_jobs pra run_at
        step_stmt = (
            select(
                OnboardingEnrollmentStepModel,
                ScheduledJobModel.run_at,
            )
            .outerjoin(
                ScheduledJobModel,
                ScheduledJobModel.id == OnboardingEnrollmentStepModel.scheduled_job_id,
            )
            .where(OnboardingEnrollmentStepModel.enrollment_id.in_(enrollment_ids))
            .order_by(
                OnboardingEnrollmentStepModel.enrollment_id,
                OnboardingEnrollmentStepModel.position,
            )
        )
        step_rows = (await self.session.execute(step_stmt)).all()

        # 3. Agrupa steps por enrollment
        steps_by_enrollment: dict[UUID, list[dict[str, Any]]] = {}
        for step_model, run_at in step_rows:
            steps_by_enrollment.setdefault(step_model.enrollment_id, []).append(
                {
                    "id": step_model.id,
                    "position": step_model.position,
                    "template_name": step_model.meta_template_name,
                    "message_text": step_model.message_text,
                    "status": step_model.status,
                    "delay_from_previous_minutes": step_model.delay_from_previous_minutes,
                    "scheduled_for": run_at,
                    "sent_at": step_model.sent_at,
                    "failure_reason": step_model.failure_reason,
                    "rendered_preview": None,  # TODO: renderizar preview ao mostrar
                }
            )

        # 4. Monta resposta final
        result: list[dict[str, Any]] = []
        for enrollment_model, flow_name in enr_rows:
            result.append(
                {
                    "id": enrollment_model.id,
                    "flow_id": enrollment_model.flow_id,
                    "flow_name": flow_name or "Flow removido",
                    "product_name": enrollment_model.product_name,
                    "trigger_event_type": "subscription.activated",  # snapshot histórico
                    "enrolled_at": enrollment_model.created_at,
                    "steps": steps_by_enrollment.get(enrollment_model.id, []),
                }
            )
        return result
