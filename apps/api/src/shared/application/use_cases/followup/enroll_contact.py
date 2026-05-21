from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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
      (mesmo account_id, contact_id, flow_id, purchase_id) e os jobs órfãos
      recém-criados foram cancelados.
    """

    enrollment: FollowupEnrollment | None
    deduped: bool = False


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
            # Nota: scheduled jobs criados antes do create_with_steps podem ficar órfãos
            # se create_with_steps falhar (exceto IntegrityError, que é o caso de dedup —
            # tratado abaixo cancelando os jobs).
            # Em uma futura iteração, refatorar para passar `session` aqui e usar begin_nested().
            job = await self._job_repo.schedule(
                account_id=account_id,
                conversation_id=None,  # chatnexo conversation ID está no payload abaixo
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

        try:
            await self._enrollment_repo.create_with_steps(enrollment, enrollment_steps)
        except IntegrityError:
            # A session entra em estado inativo após IntegrityError — precisamos
            # liberar com rollback antes de qualquer query subsequente.
            await self._enrollment_repo.rollback()
            existing = await self._enrollment_repo.find_by_dedup_key(
                account_id=account_id,
                contact_id=contact_id,
                flow_id=flow.id,
                purchase_id=purchase_id,
            )
            # Cancela jobs órfãos criados pelos enrollment_steps que tentaram inserir.
            for es in enrollment_steps:
                if es.scheduled_job_id:
                    try:
                        await self._job_repo.cancel(es.scheduled_job_id)
                    except SQLAlchemyError:
                        log.warning(
                            "orphan_job_cancel_failed",
                            job_id=str(es.scheduled_job_id),
                            exc_info=True,
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
