from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, status

from shared.adapters.chatnexo.schemas import IncomingMessagePayload
from shared.adapters.observability.logger import get_logger
from shared.adapters.observability.metrics import WEBHOOK_RECEIVED
from shared.domain.entities.webhook_event import WebhookSource

router = APIRouter(tags=["webhook"])
log = get_logger(__name__)


@dataclass
class _Config:
    dedup: object | None = None
    event_repo_factory: Callable[[], object] | None = None
    queue: object | None = None
    expected_api_key: str = ""


_cfg = _Config()


def configure(
    *, dedup, event_repo_factory: Callable[[], object], queue, expected_api_key: str
) -> None:
    _cfg.dedup = dedup
    _cfg.event_repo_factory = event_repo_factory
    _cfg.queue = queue
    _cfg.expected_api_key = expected_api_key


async def _verify_api_key(request: Request) -> None:
    key = request.headers.get("x-api-key", "")
    if key != _cfg.expected_api_key:
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="401").inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")


@router.post(
    "/webhook/message",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_api_key)],
)
async def receive(
    payload: IncomingMessagePayload,
) -> dict:
    if _cfg.dedup is None or _cfg.event_repo_factory is None or _cfg.queue is None:
        raise RuntimeError("webhook_message router not configured; call configure() before serving")
    first = await _cfg.dedup.try_mark(
        key=f"message:{payload.chatnexo_message_id}", ttl_seconds=3600
    )
    if not first:
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="202-dup").inc()
        return {"accepted": True, "duplicate": True}

    repo = _cfg.event_repo_factory()
    await repo.insert_if_new(
        source=WebhookSource.CHATNEXO,
        external_id=payload.chatnexo_message_id,
        payload=payload.model_dump(),
    )

    job_id = await _cfg.queue.enqueue({"kind": "message", "payload": payload.model_dump()})
    WEBHOOK_RECEIVED.labels(source="chatnexo", status="202").inc()
    log.info(
        "message_webhook_enqueued",
        chatnexo_message_id=payload.chatnexo_message_id,
        job_id=job_id,
    )
    return {"accepted": True, "duplicate": False, "job_id": job_id}
