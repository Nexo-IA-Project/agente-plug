from __future__ import annotations

import structlog
from cryptography.fernet import Fernet

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.contact import ContactRepository
from shared.adapters.db.repositories.hubla_event_repo import SqlHublaEventRepository
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository
from shared.adapters.db.repositories.onboarding_enrollment_repo import (
    OnboardingEnrollmentRepository,
)
from shared.adapters.db.repositories.onboarding_flow_repo import OnboardingFlowRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import session_scope
from shared.application.hubla_event_handler import HublaEventHandler
from shared.application.purchase_handler import PurchaseHandler
from shared.application.use_cases.onboarding.enroll_contact import EnrollContact
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid

log = structlog.get_logger(__name__)


async def handle_hubla_event(payload: dict) -> None:
    """Worker job kind 'hubla_event' — processa qualquer evento Hubla via HublaEventHandler."""
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())

    event_type = payload.get("type", "unknown")
    log.info("hubla_event_received", event_type=event_type)

    async with session_scope() as session:
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        account_config = await config_repo.get(account_id=1)
        chatnexo = ChatNexoClient.from_account_config(account_config)

        contact_repo = ContactRepository(session=session)
        access_case_repo = AccessCaseRepository(session=session)
        scheduler = ScheduledJobRepository(session=session)
        product_repo = SqlProductRepository(session=session)
        flow_repo = OnboardingFlowRepository(session=session)
        enrollment_repo = OnboardingEnrollmentRepository(session=session)
        hubla_event_repo = SqlHublaEventRepository(session=session)
        lead_repo = SqlLeadRepository(session=session)

        enroll_uc = EnrollContact(
            session=session,
            flow_repo=flow_repo,
            enrollment_repo=enrollment_repo,
            job_repo=scheduler,
        )

        purchase_handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            product_repo=product_repo,
            chatnexo_account_id=account_config.integration.chatnexo_account_id,
        )

        account_uuid = await get_default_account_uuid(session)

        handler = HublaEventHandler(
            product_repo=product_repo,
            flow_repo=flow_repo,
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            enroll_contact_uc=enroll_uc,
            purchase_handler=purchase_handler,
            lead_repo=lead_repo,
            hubla_event_repo=hubla_event_repo,
            account_id=account_uuid,
        )

        await handler.handle(payload)

    log.info("hubla_event_job_done", event_type=event_type)
