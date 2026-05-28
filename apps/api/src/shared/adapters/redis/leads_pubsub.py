from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis as AsyncRedis

from shared.config.settings import get_settings

log = structlog.get_logger(__name__)


def _channel(account_id: UUID) -> str:
    return f"leads:events:{account_id}"


class LeadsPubSub:
    """Pub/sub helper para eventos de lead em tempo real.

    Cada account tem um canal Redis dedicado (`leads:events:{account_id}`).
    Publishers (HublaEventHandler, DispatchOnboardingStep) publicam envelopes
    JSON; o endpoint SSE assina o canal e repassa pro frontend.
    """

    def __init__(self) -> None:
        url = get_settings().redis_url
        self._async: AsyncRedis = AsyncRedis.from_url(url, decode_responses=True)

    async def publish(self, account_id: UUID, envelope: dict[str, Any]) -> None:
        try:
            payload = json.dumps(envelope, default=str)
            await self._async.publish(_channel(account_id), payload)
        except Exception as exc:
            # Pub/sub não pode quebrar o pipeline de eventos; só loga.
            log.warning(
                "leads_pubsub.publish_failed",
                account_id=str(account_id),
                error=str(exc),
            )

    async def subscribe(self, account_id: UUID) -> AsyncIterator[dict[str, Any]]:
        """Yield envelopes recebidos no canal do account."""
        pubsub = self._async.pubsub()
        await pubsub.subscribe(_channel(account_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    log.warning("leads_pubsub.invalid_json", data=str(data)[:200])
                    continue
        finally:
            try:
                await pubsub.unsubscribe(_channel(account_id))
                await pubsub.close()
            except Exception:
                pass

    async def close(self) -> None:
        await self._async.aclose()
