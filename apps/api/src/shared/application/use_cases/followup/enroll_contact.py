from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog

from shared.domain.entities.followup import (
    EnrollmentStepStatus,
    FollowupEnrollment,
    FollowupEnrollmentStep,
)
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


class EnrollContact:
    def __init__(self, *, flow_repo: Any, enrollment_repo: Any, job_repo: Any) -> None:
        self._flow_repo = flow_repo
        self._enrollment_repo = enrollment_repo
        self._job_repo = job_repo

    async def execute(
        self,
        *,
        account_id: UUID,
        contact_id: UUID,
        conversation_id: str,
        contact_phone: str,
        purchase_id: str,
        product: str,
        purchase_time: Any,
    ) -> FollowupEnrollment | None:
        flow = await self._flow_repo.find_active_by_product(account_id=account_id, product=product)
        if flow is None:
            log.info("followup_no_flow_found", account_id=str(account_id), product=product)
            return None

        steps = await self._flow_repo.get_steps(flow.id)
        if not steps:
            log.info("followup_flow_has_no_steps", flow_id=str(flow.id))
            return None

        enrollment = FollowupEnrollment(
            account_id=account_id,
            flow_id=flow.id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            contact_phone=contact_phone,
            purchase_id=purchase_id,
        )

        enrollment_steps: list[FollowupEnrollmentStep] = []
        for step in steps:
            run_at = purchase_time + timedelta(hours=step.delay_from_purchase_hours)
            enrollment_step = FollowupEnrollmentStep(
                enrollment_id=enrollment.id,
                position=step.position,
                delay_from_purchase_hours=step.delay_from_purchase_hours,
                meta_template_name=step.meta_template_name,
                template_variables=step.template_variables,
                status=EnrollmentStepStatus.PENDING,
            )
            job = await self._job_repo.schedule(
                account_id=account_id,
                conversation_id=None,  # chatnexo ID está no payload abaixo
                job_type=JobType.FOLLOWUP_STEP,
                payload={
                    "enrollment_step_id": str(enrollment_step.id),
                    "account_id": str(account_id),
                    "conversation_id": str(conversation_id),
                    "contact_phone": contact_phone,
                },
                run_at=run_at,
            )
            enrollment_step.scheduled_job_id = job.id
            enrollment_steps.append(enrollment_step)

        await self._enrollment_repo.create_with_steps(enrollment, enrollment_steps)

        log.info(
            "followup_enrolled",
            enrollment_id=str(enrollment.id),
            flow_id=str(flow.id),
            steps=len(enrollment_steps),
        )
        return enrollment
