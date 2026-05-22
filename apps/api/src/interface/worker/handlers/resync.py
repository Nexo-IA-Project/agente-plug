from __future__ import annotations

import uuid

import structlog

from shared.adapters.db.models import AuditEventModel
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepository,
)
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import session_scope
from shared.application.use_cases.followup.resync_enrollment import (
    ResyncEnrollmentUseCase,
)

log = structlog.get_logger(__name__)


async def handle_resync_flow(payload: dict) -> None:
    flow_id = uuid.UUID(payload["flow_id"])
    account_id = uuid.UUID(payload["account_id"])
    log.info("resync_flow_started", flow_id=str(flow_id))

    async with session_scope() as session:
        enrollment_repo = FollowupEnrollmentRepository(session=session)
        flow_step_repo = FollowupFlowRepository(session=session)
        scheduled_job_repo = ScheduledJobRepository(session=session)

        enrollments = await enrollment_repo.find_active_by_flow(
            account_id=account_id,
            flow_id=flow_id,
        )
        totals = {
            "enrollments_affected": 0,
            "steps_added": 0,
            "steps_rescheduled": 0,
            "steps_content_updated": 0,
            "steps_cancelled": 0,
        }

        for enrollment in enrollments:
            try:
                async with session.begin_nested():
                    use_case = ResyncEnrollmentUseCase(
                        enrollment_repo=enrollment_repo,
                        flow_step_repo=flow_step_repo,
                        scheduled_job_repo=scheduled_job_repo,
                    )
                    audit = await use_case.execute(
                        enrollment_id=enrollment.id,
                        flow_id=flow_id,
                        account_id=account_id,
                    )
                    for k in (
                        "steps_added",
                        "steps_rescheduled",
                        "steps_content_updated",
                        "steps_cancelled",
                    ):
                        totals[k] += audit[k]
                    totals["enrollments_affected"] += 1
            except Exception:
                log.exception(
                    "resync_enrollment_failed",
                    enrollment_id=str(enrollment.id),
                    flow_id=str(flow_id),
                )

        # Persistir audit event no mesmo session_scope — atomicidade com os updates
        # feitos pelos savepoints de cada ResyncEnrollmentUseCase.
        session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                account_id=account_id,
                actor="system",
                action="flow_resynced",
                resource_type="followup_flow",
                resource_id=str(flow_id),
                metadata_json=dict(totals),
            )
        )
        log.info("resync_flow_completed", flow_id=str(flow_id), **totals)
