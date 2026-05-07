from __future__ import annotations

import structlog

from shared.application.lifecycle_handler import LifecycleHandler
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


def _get_followup_handler():
    raise NotImplementedError("_get_followup_handler: configure DI em main.py")


def _get_dispatch_followup_step_handler():
    raise NotImplementedError("_get_dispatch_followup_step_handler: configure DI em worker.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]
    contact_id: str = payload.get("contact_id", phone)

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
    elif job_type in (JobType.LOJA_EXPRESS_D1, "LOJA_EXPRESS_D1"):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=1,
        )
    elif job_type in (JobType.LOJA_EXPRESS_D3, "LOJA_EXPRESS_D3"):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=3,
        )
    elif job_type in (JobType.LOJA_EXPRESS_D5, "LOJA_EXPRESS_D5"):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=5,
        )
    elif job_type in (JobType.LOJA_EXPRESS_D7, "LOJA_EXPRESS_D7"):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=7,
        )
    elif job_type == "followup_step":
        from uuid import UUID as _UUID

        dispatch = _get_dispatch_followup_step_handler()
        await dispatch.execute(
            enrollment_step_id=_UUID(payload["enrollment_step_id"]),
            account_id=_UUID(payload["account_id"]),
            conversation_id=_UUID(payload["conversation_id"]),
            contact_phone=payload.get("contact_phone", ""),
        )
    else:
        log.warning("unknown_job_type", job_type=job_type)
