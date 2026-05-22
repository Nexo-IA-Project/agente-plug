from __future__ import annotations

import structlog
from cryptography.fernet import Fernet

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.contact import ContactRepository
from shared.adapters.db.repositories.followup_enrollment_repo import FollowupEnrollmentRepository
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import session_scope
from shared.adapters.hubla.event_parser import HublaEventParser
from shared.application.purchase_handler import PurchaseHandler
from shared.application.use_cases.followup.enroll_contact import EnrollContact
from shared.config.settings import get_settings

log = structlog.get_logger(__name__)


async def handle_purchase(payload: dict) -> None:
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())

    parsed = HublaEventParser().parse(payload)
    log.info(
        "purchase_received",
        purchase_id=parsed.purchase_id,
        products_count=len(parsed.products),
    )

    async with session_scope() as session:
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        # SISTEMA SINGLE-TENANT: account_id=1 hardcoded (mantém comportamento atual)
        account_config = await config_repo.get(account_id=1)

        chatnexo = ChatNexoClient.from_account_config(account_config)
        contact_repo = ContactRepository(session=session)
        access_case_repo = AccessCaseRepository(session=session)
        scheduler = ScheduledJobRepository(session=session)
        product_repo = SqlProductRepository(session=session)
        flow_repo = FollowupFlowRepository(session=session)
        enrollment_repo = FollowupEnrollmentRepository(session=session)

        enroll_uc = EnrollContact(
            session=session,
            flow_repo=flow_repo,
            enrollment_repo=enrollment_repo,
            job_repo=scheduler,
        )

        handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            product_repo=product_repo,
            flow_repo=flow_repo,
            enroll_contact_uc=enroll_uc,
        )

        for product in parsed.products:
            await handler.handle_one(
                hubla_product_id=product.hubla_id,
                product_name=product.name,
                purchase_id=parsed.purchase_id,
                activated_at=parsed.activated_at,
                payer_phone=parsed.payer_phone,
                payer_email=parsed.payer_email,
                payer_full_name=parsed.payer_full_name,
                payer_document=parsed.payer_document,
            )

    log.info("purchase_job_done", purchase_id=parsed.purchase_id)
