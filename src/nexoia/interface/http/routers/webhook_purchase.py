from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from nexoia.domain.entities.webhook_event import WebhookSource
from nexoia.infrastructure.observability.metrics import WEBHOOK_RECEIVED
from nexoia.infrastructure.observability.logger import get_logger

router = APIRouter(tags=["webhook"])
log = get_logger(__name__)


class PurchasePayload(BaseModel):
    purchase_id: str
    account_id: int
    name: str
    email: str
    phone: str
    product: str
    amount_brl: int
    occurred_at: str = Field(..., description="ISO 8601")


@dataclass
class _Config:
    dedup: object | None = None
    event_repo_factory: Callable[[], object] | None = None
    queue: object | None = None
    expected_token: str = ""


_cfg = _Config()


def configure(
    *,
    dedup,
    event_repo_factory: Callable[[], object],
    queue,
    expected_token: str,
) -> None:
    _cfg.dedup = dedup
    _cfg.event_repo_factory = event_repo_factory
    _cfg.queue = queue
    _cfg.expected_token = expected_token


async def _verify_token(request: Request) -> None:
    token = request.headers.get("x-hubla-token", "")
    if token != _cfg.expected_token:
        WEBHOOK_RECEIVED.labels(source="hubla", status="401").inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


@router.post(
    "/webhook/purchase",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_token)],
)
async def receive(
    payload: PurchasePayload,
) -> dict:
    if _cfg.dedup is None or _cfg.event_repo_factory is None or _cfg.queue is None:
        raise RuntimeError("webhook_purchase router not configured; call configure() before serving")
    first = await _cfg.dedup.try_mark(
        key=f"purchase:{payload.purchase_id}", ttl_seconds=24 * 3600
    )
    if not first:
        WEBHOOK_RECEIVED.labels(source="hubla", status="202-dup").inc()
        log.info("purchase_webhook_duplicate", purchase_id=payload.purchase_id)
        return {"accepted": True, "duplicate": True}

    repo = _cfg.event_repo_factory()
    await repo.insert_if_new(
        source=WebhookSource.HUBLA,
        external_id=payload.purchase_id,
        payload=payload.model_dump(),
    )

    job_id = await _cfg.queue.enqueue({"kind": "purchase", "payload": payload.model_dump()})
    WEBHOOK_RECEIVED.labels(source="hubla", status="202").inc()
    log.info("purchase_webhook_enqueued", purchase_id=payload.purchase_id, job_id=job_id)
    return {"accepted": True, "duplicate": False, "job_id": job_id}
