from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    ContactModel,
    FollowupEnrollmentModel,
    FollowupEnrollmentStepModel,
)
from shared.domain.entities.followup import (
    EnrollmentStatus,
    EnrollmentStepStatus,
    FollowupEnrollment,
    FollowupEnrollmentStep,
)


def _enrollment_to_entity(m: FollowupEnrollmentModel) -> FollowupEnrollment:
    return FollowupEnrollment(
        id=m.id,
        account_id=m.account_id,
        flow_id=m.flow_id,
        contact_id=m.contact_id,
        conversation_id=m.conversation_id,
        contact_phone=m.contact_phone,
        purchase_id=m.purchase_id,
        customer_name=m.customer_name,
        product_name=m.product_name,
        status=EnrollmentStatus(m.status),
        created_at=m.created_at,
        purchase_time=m.created_at,
    )


def _step_to_entity(m: FollowupEnrollmentStepModel) -> FollowupEnrollmentStep:
    return FollowupEnrollmentStep(
        id=m.id,
        enrollment_id=m.enrollment_id,
        position=m.position,
        delay_from_purchase_hours=m.delay_from_purchase_hours,
        meta_template_name=m.meta_template_name,
        template_variables=dict(m.template_variables or {}),
        scheduled_job_id=m.scheduled_job_id,
        status=EnrollmentStepStatus(m.status),
        sent_at=m.sent_at,
        message_text=m.message_text,
        failure_reason=m.failure_reason,
        flow_step_id=m.flow_step_id,
    )


@dataclass
class FollowupEnrollmentRepository:
    session: AsyncSession

    async def rollback(self) -> None:
        """Roll back the underlying session after an aborted transaction."""
        await self.session.rollback()

    async def create_with_steps(
        self,
        enrollment: FollowupEnrollment,
        steps: list[FollowupEnrollmentStep],
    ) -> None:
        enrollment_model = FollowupEnrollmentModel(
            id=enrollment.id,
            account_id=enrollment.account_id,
            flow_id=enrollment.flow_id,
            contact_id=enrollment.contact_id,
            conversation_id=enrollment.conversation_id,
            contact_phone=enrollment.contact_phone,
            purchase_id=enrollment.purchase_id,
            customer_name=enrollment.customer_name,
            product_name=enrollment.product_name,
            status=enrollment.status.value,
        )
        self.session.add(enrollment_model)
        await self.session.flush()

        for step in steps:
            step_model = FollowupEnrollmentStepModel(
                id=step.id,
                enrollment_id=step.enrollment_id,
                position=step.position,
                delay_from_purchase_hours=step.delay_from_purchase_hours,
                meta_template_name=step.meta_template_name,
                template_variables=step.template_variables,
                message_text=step.message_text,
                scheduled_job_id=step.scheduled_job_id,
                status=step.status.value,
                sent_at=step.sent_at,
            )
            self.session.add(step_model)
        await self.session.flush()

    async def find_step_by_id(self, step_id: uuid.UUID) -> FollowupEnrollmentStep | None:
        model = await self.session.get(FollowupEnrollmentStepModel, step_id)
        return None if model is None else _step_to_entity(model)

    async def find_enrollment_by_id(self, enrollment_id: uuid.UUID) -> FollowupEnrollment | None:
        model = await self.session.get(FollowupEnrollmentModel, enrollment_id)
        return None if model is None else _enrollment_to_entity(model)

    async def find_by_dedup_key(
        self,
        *,
        account_id: uuid.UUID,
        contact_id: uuid.UUID,
        flow_id: uuid.UUID,
        purchase_id: str,
    ) -> FollowupEnrollment | None:
        """Busca enrollment por chave de dedup (account_id, contact_id, flow_id, purchase_id)."""
        result = await self.session.execute(
            select(FollowupEnrollmentModel).where(
                FollowupEnrollmentModel.account_id == account_id,
                FollowupEnrollmentModel.contact_id == contact_id,
                FollowupEnrollmentModel.flow_id == flow_id,
                FollowupEnrollmentModel.purchase_id == purchase_id,
            )
        )
        row = result.scalar_one_or_none()
        return _enrollment_to_entity(row) if row else None

    async def update_step(self, step: FollowupEnrollmentStep) -> None:
        model = await self.session.get(FollowupEnrollmentStepModel, step.id)
        if model is None:
            raise ValueError(f"FollowupEnrollmentStep {step.id} not found")
        model.status = step.status.value
        model.sent_at = step.sent_at
        model.scheduled_job_id = step.scheduled_job_id
        await self.session.flush()

    async def all_steps_sent(self, enrollment_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(FollowupEnrollmentStepModel)
            .where(
                FollowupEnrollmentStepModel.enrollment_id == enrollment_id,
                FollowupEnrollmentStepModel.status != EnrollmentStepStatus.SENT.value,
            )
        )
        return result.scalar_one() == 0

    async def update_enrollment_status(
        self, enrollment_id: uuid.UUID, status: EnrollmentStatus
    ) -> None:
        model = await self.session.get(FollowupEnrollmentModel, enrollment_id)
        if model is None:
            raise ValueError(f"FollowupEnrollment {enrollment_id} not found")
        model.status = status.value
        await self.session.flush()

    async def find_active_by_flow(
        self, *, account_id: uuid.UUID, flow_id: uuid.UUID
    ) -> list[FollowupEnrollment]:
        """Lista enrollments com status='active' de um flow específico de uma conta.

        Multi-tenant defense-in-depth: filtra também por account_id.
        Ordenação determinística por created_at ASC.
        """
        result = await self.session.execute(
            select(FollowupEnrollmentModel)
            .where(
                FollowupEnrollmentModel.account_id == account_id,
                FollowupEnrollmentModel.flow_id == flow_id,
                FollowupEnrollmentModel.status == EnrollmentStatus.ACTIVE.value,
            )
            .order_by(FollowupEnrollmentModel.created_at.asc())
        )
        rows = result.scalars().all()
        return [_enrollment_to_entity(row) for row in rows]

    async def list_with_filters(
        self,
        *,
        account_id: uuid.UUID,
        flow_id: uuid.UUID | None,
        contact_phone: str | None,
        status: EnrollmentStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[FollowupEnrollment], int]:
        """Lista enrollments paginados. Retorna (items, total)."""
        base = select(FollowupEnrollmentModel).where(
            FollowupEnrollmentModel.account_id == account_id
        )
        if flow_id is not None:
            base = base.where(FollowupEnrollmentModel.flow_id == flow_id)
        if status is not None:
            base = base.where(FollowupEnrollmentModel.status == status.value)
        if contact_phone:
            base = base.join(
                ContactModel,
                ContactModel.id == FollowupEnrollmentModel.contact_id,
            ).where(ContactModel.phone == contact_phone)

        total_result = await self.session.execute(select(func.count()).select_from(base.subquery()))
        total = int(total_result.scalar_one())

        paged = (
            base.order_by(FollowupEnrollmentModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(paged)).scalars().all()
        return [_enrollment_to_entity(r) for r in rows], total

    async def count_steps_by_status(self, enrollment_id: uuid.UUID) -> dict[str, int]:
        """Conta steps de um enrollment agrupados por status (lowercase)."""
        result = await self.session.execute(
            select(
                FollowupEnrollmentStepModel.status,
                func.count(FollowupEnrollmentStepModel.id),
            )
            .where(FollowupEnrollmentStepModel.enrollment_id == enrollment_id)
            .group_by(FollowupEnrollmentStepModel.status)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def cancel_step(self, step_id: uuid.UUID) -> None:
        """Marca o step como cancelado.

        Só atua em steps ainda PENDING — não sobrescreve SENT/FAILED/CANCELLED.
        Idempotente: chamar várias vezes em um step já não-PENDING é no-op.
        """
        await self.session.execute(
            update(FollowupEnrollmentStepModel)
            .where(
                FollowupEnrollmentStepModel.id == step_id,
                FollowupEnrollmentStepModel.status == EnrollmentStepStatus.PENDING.value,
            )
            .values(status=EnrollmentStepStatus.CANCELLED.value)
        )

    async def add_step_with_job(self, step: FollowupEnrollmentStep) -> None:
        """Persiste um novo enrollment_step (com flow_step_id e scheduled_job_id já setados)."""
        model = FollowupEnrollmentStepModel(
            id=step.id,
            enrollment_id=step.enrollment_id,
            flow_step_id=step.flow_step_id,
            position=step.position,
            delay_from_purchase_hours=step.delay_from_purchase_hours,
            meta_template_name=step.meta_template_name,
            message_text=step.message_text,
            template_variables=step.template_variables,
            status=step.status.value,
            scheduled_job_id=step.scheduled_job_id,
        )
        self.session.add(model)
        await self.session.flush()

    async def apply_step_update(
        self,
        *,
        step_id: uuid.UUID,
        delay_from_purchase_hours: int,
        meta_template_name: str | None,
        message_text: str | None,
        template_variables: dict,
        scheduled_job_id: uuid.UUID | None,
    ) -> None:
        """Atualiza campos de um enrollment_step PENDING in-place.

        Se scheduled_job_id=None, mantém o atual. Caso contrário, sobrescreve.
        """
        values: dict = {
            "delay_from_purchase_hours": delay_from_purchase_hours,
            "meta_template_name": meta_template_name,
            "message_text": message_text,
            "template_variables": template_variables,
        }
        if scheduled_job_id is not None:
            values["scheduled_job_id"] = scheduled_job_id
        await self.session.execute(
            update(FollowupEnrollmentStepModel)
            .where(
                FollowupEnrollmentStepModel.id == step_id,
                FollowupEnrollmentStepModel.status == EnrollmentStepStatus.PENDING.value,
            )
            .values(**values)
        )

    async def get_with_steps(
        self, enrollment_id: uuid.UUID
    ) -> FollowupEnrollment | None:
        """Carrega enrollment + todos os seus steps em uma só ida ao DB."""
        e_result = await self.session.execute(
            select(FollowupEnrollmentModel).where(
                FollowupEnrollmentModel.id == enrollment_id
            )
        )
        e_model = e_result.scalar_one_or_none()
        if e_model is None:
            return None
        s_result = await self.session.execute(
            select(FollowupEnrollmentStepModel)
            .where(FollowupEnrollmentStepModel.enrollment_id == enrollment_id)
            .order_by(FollowupEnrollmentStepModel.position)
        )
        step_rows = s_result.scalars().all()
        enrollment = _enrollment_to_entity(e_model)
        enrollment.steps = [_step_to_entity(r) for r in step_rows]
        return enrollment

    async def mark_failed(self, step_id: uuid.UUID, reason: str) -> None:
        """Marca step como FAILED com a razão (truncada a 500 chars).

        Só atua em steps PENDING — não sobrescreve SENT/CANCELLED.
        """
        truncated = (reason or "")[:500]
        await self.session.execute(
            update(FollowupEnrollmentStepModel)
            .where(
                FollowupEnrollmentStepModel.id == step_id,
                FollowupEnrollmentStepModel.status == EnrollmentStepStatus.PENDING.value,
            )
            .values(
                status=EnrollmentStepStatus.FAILED.value,
                failure_reason=truncated,
            )
        )
