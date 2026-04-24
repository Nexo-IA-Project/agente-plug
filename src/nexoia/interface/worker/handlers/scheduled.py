from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.lifecycle_handler import LifecycleHandler

log = structlog.get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]

    lifecycle = _get_lifecycle_handler()

    if job_type == "IDLE_PING":
        await lifecycle.send_ping(account_id=account_id, phone=phone, conversation_id=conversation_id)
    elif job_type == "IDLE_CLOSE":
        await lifecycle.send_close(account_id=account_id, phone=phone, conversation_id=conversation_id)
    else:
        log.warning("unknown_job_type", job_type=job_type)
