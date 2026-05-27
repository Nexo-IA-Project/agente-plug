from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog

from shared.application.use_cases.onboarding.diff_flow_steps import compute_diff
from shared.domain.entities.onboarding import (
    EnrollmentStepStatus,
    OnboardingEnrollmentStep,
)
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


class ResyncEnrollmentUseCase:
    """Aplica diff entre flow.steps atual e enrollment.steps existente.

    Steps SENT/FAILED/CANCELLED nunca são modificados.
    """

    def __init__(
        self,
        *,
        enrollment_repo: Any,
        flow_step_repo: Any,
        scheduled_job_repo: Any,
    ) -> None:
        self._enrollment_repo = enrollment_repo
        self._flow_step_repo = flow_step_repo
        self._scheduled_job_repo = scheduled_job_repo

    async def execute(
        self,
        *,
        enrollment_id: uuid.UUID,
        flow_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> dict[str, int]:
        enrollment = await self._enrollment_repo.get_with_steps(enrollment_id)
        flow_steps = await self._flow_step_repo.get_steps(flow_id)
        diff = compute_diff(flow_steps, enrollment.steps)

        # Cálculo cumulativo dos run_at por position (semântica relativa).
        # Calcula UMA vez para todo o flow ordenado; cada run_at depende do anterior.
        run_at_by_position: dict[int, datetime] = {}
        base_time = enrollment.purchase_time
        for fs in sorted(flow_steps, key=lambda s: s.position):
            base_time = base_time + timedelta(minutes=fs.delay_from_previous_minutes)
            run_at_by_position[fs.position] = base_time

        audit = {
            "steps_added": 0,
            "steps_rescheduled": 0,
            "steps_content_updated": 0,
            "steps_cancelled": 0,
        }

        for fs in diff.to_add:
            new_step = OnboardingEnrollmentStep(
                enrollment_id=enrollment.id,
                flow_step_id=fs.id,
                position=fs.position,
                delay_from_previous_minutes=fs.delay_from_previous_minutes,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                status=EnrollmentStepStatus.PENDING,
            )
            run_at = run_at_by_position[fs.position]
            job = await self._scheduled_job_repo.schedule(
                account_id=account_id,
                conversation_id=None,
                job_type=JobType.FOLLOWUP_STEP,
                payload={
                    "enrollment_step_id": str(new_step.id),
                    "account_id": str(account_id),
                    "conversation_id": str(enrollment.conversation_id),
                    "contact_phone": enrollment.contact_phone,
                },
                run_at=run_at,
            )
            new_step.scheduled_job_id = job.id
            await self._enrollment_repo.add_step_with_job(new_step)
            audit["steps_added"] += 1

        for enr_step, fs in diff.to_reschedule:
            if enr_step.scheduled_job_id is not None:
                await self._scheduled_job_repo.cancel(enr_step.scheduled_job_id)
            run_at = run_at_by_position[fs.position]
            new_job = await self._scheduled_job_repo.schedule(
                account_id=account_id,
                conversation_id=None,
                job_type=JobType.FOLLOWUP_STEP,
                payload={
                    "enrollment_step_id": str(enr_step.id),
                    "account_id": str(account_id),
                    "conversation_id": str(enrollment.conversation_id),
                    "contact_phone": enrollment.contact_phone,
                },
                run_at=run_at,
            )
            await self._enrollment_repo.apply_step_update(
                step_id=enr_step.id,
                delay_from_previous_minutes=fs.delay_from_previous_minutes,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                scheduled_job_id=new_job.id,
            )
            audit["steps_rescheduled"] += 1

        for enr_step, fs in diff.to_update_content:
            await self._enrollment_repo.apply_step_update(
                step_id=enr_step.id,
                delay_from_previous_minutes=fs.delay_from_previous_minutes,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                scheduled_job_id=None,
            )
            audit["steps_content_updated"] += 1

        for enr_step in diff.to_cancel:
            if enr_step.scheduled_job_id is not None:
                await self._scheduled_job_repo.cancel(enr_step.scheduled_job_id)
            await self._enrollment_repo.cancel_step(enr_step.id)
            audit["steps_cancelled"] += 1

        log.info(
            "resync_enrollment_completed",
            enrollment_id=str(enrollment_id),
            flow_id=str(flow_id),
            **audit,
        )
        return audit
