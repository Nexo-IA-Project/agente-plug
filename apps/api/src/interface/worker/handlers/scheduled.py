from __future__ import annotations

import structlog

from shared.application.lifecycle_handler import LifecycleHandler
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


def _get_dispatch_followup_step_handler():
    raise NotImplementedError("_get_dispatch_followup_step_handler: configure DI em worker.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]

    if job_type == "IDLE_PING":
        lifecycle = _get_lifecycle_handler()
        await lifecycle.send_ping(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type == "IDLE_CLOSE":
        lifecycle = _get_lifecycle_handler()
        await lifecycle.send_close(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type == JobType.FOLLOWUP_STEP.value:
        from uuid import UUID as _UUID

        from cryptography.fernet import Fernet

        from agent.history import ConversationHistory
        from shared.adapters.chatnexo.client import ChatNexoClient
        from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
        from shared.adapters.db.repositories.contact import ContactRepository
        from shared.adapters.db.repositories.followup_enrollment_repo import (
            FollowupEnrollmentRepository,
        )
        from shared.adapters.db.repositories.meta_template_repo import MetaTemplateRepository
        from shared.adapters.db.session import session_scope
        from shared.application.use_cases.followup.dispatch_followup_step import (
            DispatchFollowupStep,
        )
        from shared.config.settings import get_settings

        settings_obj = get_settings()
        fernet = Fernet(settings_obj.integration_credentials_key.encode())
        async with session_scope() as session:
            config_repo = AccountConfigRepository(session=session, fernet=fernet)
            config = await config_repo.get(account_id=1)
            chatnexo = ChatNexoClient.from_account_config(config)
            dispatch = DispatchFollowupStep(
                enrollment_repo=FollowupEnrollmentRepository(session=session),
                contact_repo=ContactRepository(session=session),
                chatnexo=chatnexo,
                conversation_history=ConversationHistory(session=session),
                meta_template_repo=MetaTemplateRepository(session=session),
            )
            await dispatch.execute(
                enrollment_step_id=_UUID(payload["enrollment_step_id"]),
                account_id=_UUID(payload["account_id"]),
                conversation_id=payload["conversation_id"],
                contact_phone=payload.get("contact_phone", ""),
            )
    else:
        log.warning("unknown_job_type", job_type=job_type)
