from __future__ import annotations

from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


async def handle_scheduled(payload: dict) -> None:
    """Router de jobs agendados. Spec ② adiciona FOLLOWUP_D1."""
    log.info("scheduled_job_received_stub", job_type=payload.get("job_type"))
