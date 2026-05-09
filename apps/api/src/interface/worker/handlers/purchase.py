from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from cryptography.fernet import Fernet

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.contact import ContactRepository
from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from shared.adapters.db.repositories.followup_enrollment_repo import FollowupEnrollmentRepository
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import session_scope
from shared.application.purchase_handler import PurchaseHandler
from shared.application.use_cases.followup.enroll_contact import EnrollContact
from shared.config.settings import get_settings
from shared.domain.events.purchase_received import PurchaseReceived

log = structlog.get_logger(__name__)


async def handle_purchase(payload: dict) -> None:
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())

    event = PurchaseReceived(
        purchase_id=payload["purchase_id"],
        account_id=UUID(payload["account_id"]),
        customer_name=payload["customer_name"],
        contact_email=payload["contact_email"],
        contact_phone=payload["contact_phone"],
        product_id=payload["product_id"],
        product_name=payload["product_name"],
        amount_brl=int(payload["amount_brl"]),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )

    async with session_scope() as session:
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        account_config = await config_repo.get(account_id=1)

        chatnexo = ChatNexoClient.from_account_config(account_config)
        contact_repo = ContactRepository(session=session)
        access_case_repo = AccessCaseRepository(session=session)
        scheduler = ScheduledJobRepository(session=session)
        course_repo = SqlCourseRepository(session=session)
        flow_repo = FollowupFlowRepository(session=session)
        enrollment_repo = FollowupEnrollmentRepository(session=session)

        enroll_uc = EnrollContact(
            flow_repo=flow_repo,
            enrollment_repo=enrollment_repo,
            job_repo=scheduler,
        )

        handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            course_repo=course_repo,
            flow_repo=flow_repo,
            enroll_contact_uc=enroll_uc,
        )
        await handler.execute(event)

    log.info("purchase_job_done", purchase_id=payload["purchase_id"])
