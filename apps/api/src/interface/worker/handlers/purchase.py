from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog

from shared.application.purchase_handler import PurchaseHandler
from shared.domain.events.purchase_received import PurchaseReceived

log = structlog.get_logger(__name__)


def _get_purchase_handler() -> PurchaseHandler:
    raise NotImplementedError("_get_purchase_handler: configure DI em main.py")


async def handle_purchase(payload: dict) -> None:
    handler = _get_purchase_handler()
    event = PurchaseReceived(
        purchase_id=payload["purchase_id"],
        account_id=UUID(payload["account_id"]),
        contact_name=payload["contact_name"],
        contact_email=payload["contact_email"],
        contact_phone=payload["contact_phone"],
        product=payload["product"],
        amount_brl=int(payload["amount_brl"]),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )
    await handler.execute(event)
    log.info("purchase_job_done", purchase_id=payload["purchase_id"])
