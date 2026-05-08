from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import FollowupEnrollmentModel, FollowupEnrollmentStepModel
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
        status=EnrollmentStatus(m.status),
        created_at=m.created_at,
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
    )


@dataclass
class FollowupEnrollmentRepository:
    session: AsyncSession

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
