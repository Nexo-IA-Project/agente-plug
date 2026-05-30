from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from shared.adapters.observability.logger import get_logger
from shared.adapters.observability.metrics import WEBHOOK_RECEIVED
from shared.domain.entities.webhook_event import WebhookSource

router = APIRouter(tags=["webhook-hubla"])
log = get_logger(__name__)


@dataclass
class _Config:
    dedup: object | None = None
    event_repo_factory: Callable[[], AbstractAsyncContextManager[object]] | None = None
    queue: object | None = None
    token_resolver: Callable[[], Awaitable[str]] | None = None


_cfg = _Config()


def configure(
    *,
    dedup,
    event_repo_factory: Callable[[], AbstractAsyncContextManager[object]],
    queue,
    token_resolver: Callable[[], Awaitable[str]],
) -> None:
    _cfg.dedup = dedup
    _cfg.event_repo_factory = event_repo_factory
    _cfg.queue = queue
    _cfg.token_resolver = token_resolver


async def _verify_token(request: Request) -> None:
    # Hubla não envia headers; token vai na query string.
    # token_resolver lê do IntegrationConfig (UI Settings) com fallback pro .env.
    if _cfg.token_resolver is None:
        raise RuntimeError("webhook_hubla router not configured; call configure() before serving")
    expected = await _cfg.token_resolver()
    token = request.query_params.get("token", "")
    if not secrets.compare_digest(token, expected):
        WEBHOOK_RECEIVED.labels(source="hubla-unified", status="401").inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


@router.post(
    "/webhook/hubla",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_token)],
)
async def receive(payload: dict = Body(...)) -> dict:
    if _cfg.dedup is None or _cfg.event_repo_factory is None or _cfg.queue is None:
        raise RuntimeError("webhook_hubla router not configured; call configure() before serving")

    event_type: str = payload.get("type", "unknown")
    event_obj: dict = payload.get("event", {}) or {}
    # Id único da venda: v2 manda em event.subscription.id; v1 ("NewSale" etc.)
    # manda em event.transactionId. Sem um id confiável, NÃO deduplicamos — colapsar
    # tudo no event_type derrubava todas as vendas (ex: external_id="NewSale" → 1ª passa,
    # resto vira "duplicado" por 24h). Melhor processar 2x (downstream é idempotente por
    # purchase_id) do que perder venda em silêncio.
    sale_id: str = (event_obj.get("subscription", {}) or {}).get("id", "") or event_obj.get(
        "transactionId", ""
    )

    if sale_id:
        external_id = f"{event_type}:{sale_id}"
        first = await _cfg.dedup.try_mark(key=f"hubla:{external_id}", ttl_seconds=24 * 3600)
        if not first:
            WEBHOOK_RECEIVED.labels(source="hubla-unified", status="202-dup").inc()
            log.info("hubla_webhook_duplicate", event_type=event_type, external_id=external_id)
            return {"accepted": True, "duplicate": True}
    else:
        # sem id de venda → não dá pra deduplicar com segurança; segue para enfileirar.
        external_id = event_type
        log.warning("hubla_webhook_no_sale_id", event_type=event_type)

    async with _cfg.event_repo_factory() as repo:
        await repo.insert_if_new(
            source=WebhookSource.HUBLA,
            external_id=f"hubla:{external_id}",
            payload=payload,
        )

    job_id = await _cfg.queue.enqueue({"kind": "hubla_event", "payload": payload})
    WEBHOOK_RECEIVED.labels(source="hubla-unified", status="202").inc()
    log.info(
        "hubla_webhook_enqueued",
        event_type=event_type,
        external_id=external_id,
        job_id=job_id,
    )
    return {"accepted": True, "duplicate": False, "job_id": job_id}
