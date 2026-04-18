from __future__ import annotations

from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


async def handle_purchase(payload: dict) -> None:
    """Stub handler for Hubla purchase webhook.

    Spec ② (Welcome capability) substitui este handler com a implementação real.
    """
    log.info("purchase_job_received_stub", purchase_id=payload.get("purchase_id"))
