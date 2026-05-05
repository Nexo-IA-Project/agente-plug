from __future__ import annotations

from collections.abc import Awaitable, Callable
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
    token_validator: Callable[[str], Awaitable[bool]] | None = None


_cfg = _Config()


def configure(
    *,
    dedup,
    event_repo_factory: Callable[[], object],
    queue,
    token_validator: Callable[[str], Awaitable[bool]],
) -> None:
    _cfg.dedup = dedup
    _cfg.event_repo_factory = event_repo_factory
    _cfg.queue = queue
    _cfg.token_validator = token_validator


async def _verify_bearer_token(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="401").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.removeprefix("Bearer ").strip()
    if _cfg.token_validator is None or not await _cfg.token_validator(token):
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="401").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/webhook/message",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_bearer_token)],
)
async def receive(
    payload: IncomingMessagePayload,
) -> dict:
    if _cfg.dedup is None or _cfg.event_repo_factory is None or _cfg.queue is None:
        raise RuntimeError("webhook_message router not configured; call configure() before serving")
    first = await _cfg.dedup.try_mark(
        key=f"message:{payload.message_id}", ttl_seconds=3600
    )
    if not first:
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="202-dup").inc()
        return {"accepted": True, "duplicate": True}

    repo = _cfg.event_repo_factory()
    await repo.insert_if_new(
        source=WebhookSource.CHATNEXO,
        external_id=payload.message_id,
        payload=payload.model_dump(),
    )

    job_id = await _cfg.queue.enqueue({"kind": "message", "payload": payload.model_dump()})
    WEBHOOK_RECEIVED.labels(source="chatnexo", status="202").inc()
    log.info(
        "message_webhook_enqueued",
        message_id=payload.message_id,
        job_id=job_id,
    )
    return {"accepted": True, "duplicate": False, "job_id": job_id}
