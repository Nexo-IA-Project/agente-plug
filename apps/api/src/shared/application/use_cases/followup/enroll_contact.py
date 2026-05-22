from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.entities.followup import (
    EnrollmentStepStatus,
    FollowupEnrollment,
    FollowupEnrollmentStep,
)
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EnrollResult:
    """Resultado de EnrollContact.execute.

    - enrollment: o enrollment criado (ou o existente em caso de dedup)
    - deduped: True se a tentativa de criar encontrou um enrollment duplicado
      (mesmo account_id, contact_id, flow_id, purchase_id). Como a criação roda
      dentro de um SAVEPOINT (``session.begin_nested()``), a falha por
      IntegrityError dá rollback APENAS da savepoint — a sessão pai segue válida,
      e os scheduled_jobs criados dentro da savepoint também são revertidos
      automaticamente (não há jobs órfãos para cancelar manualmente).
    """

    enrollment: FollowupEnrollment | None
    deduped: bool = False


class EnrollContact:
    def __init__(
        self,
        *,
        session: AsyncSession,
        flow_repo: Any,
        enrollment_repo: Any,
        job_repo: Any,
    ) -> None:
        self._session = session
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
        flow_id: UUID,
        customer_name: str,
        product_name: str,
        purchase_time: datetime,
    ) -> EnrollResult | None:
        flow = await self._flow_repo.find_by_id(flow_id)
        if flow is None:
            log.info("followup_flow_not_found", flow_id=str(flow_id))
            return None
        if not flow.is_active:
            log.info("followup_flow_inactive", flow_id=str(flow_id))
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
            customer_name=customer_name,
            product_name=product_name,
        )

        try:
            # SAVEPOINT isola a tentativa de criação: se UNIQUE constraint disparar,
            # apenas as inserções desta savepoint (enrollment, enrollment_steps,
            # scheduled_jobs) são revertidas — a sessão pai (contact upsert, outros
            # enrollments do mesmo handle_one) permanece intacta.
            async with self._session.begin_nested():
                enrollment_steps: list[FollowupEnrollmentStep] = []
                for step in steps:
                    run_at = purchase_time + timedelta(hours=step.delay_from_purchase_hours)
                    enrollment_step = FollowupEnrollmentStep(
                        enrollment_id=enrollment.id,
                        flow_step_id=step.id,
                        position=step.position,
                        delay_from_purchase_hours=step.delay_from_purchase_hours,
                        meta_template_name=step.meta_template_name,
                        template_variables=step.template_variables,
                        message_text=step.message_text,
                        status=EnrollmentStepStatus.PENDING,
                    )
                    job = await self._job_repo.schedule(
                        account_id=account_id,
                        conversation_id=None,
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
        except IntegrityError:
            # Savepoint já foi rolled back automaticamente — a sessão pai está ok.
            # Os scheduled_jobs criados aqui foram revertidos junto com a savepoint.
            existing = await self._enrollment_repo.find_by_dedup_key(
                account_id=account_id,
                contact_id=contact_id,
                flow_id=flow.id,
                purchase_id=purchase_id,
            )
            log.info(
                "followup_enrollment_deduped",
                account_id=str(account_id),
                flow_id=str(flow.id),
                purchase_id=purchase_id,
            )
            return EnrollResult(enrollment=existing, deduped=True)

        log.info(
            "followup_enrolled",
            enrollment_id=str(enrollment.id),
            flow_id=str(flow.id),
            customer_name=customer_name,
            product_name=product_name,
            steps=len(enrollment_steps),
        )
        return EnrollResult(enrollment=enrollment, deduped=False)
