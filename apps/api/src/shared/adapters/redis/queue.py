from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from shared.domain.value_objects.priority import Priority


@dataclass
class PriorityQueue:
    redis: Redis
    name: str
    priority_enabled: bool = False

    @property
    def _zset_key(self) -> str:
        return f"queue:{self.name}:zset"

    @property
    def _list_key(self) -> str:
        return f"queue:{self.name}:list"

    @property
    def _dlq_key(self) -> str:
        return f"dlq:{self.name}"

    async def enqueue(
        self, payload: dict[str, Any], *, priority: Priority = Priority.NORMAL
    ) -> str:
        job_id = uuid.uuid4().hex
        envelope = json.dumps({"id": job_id, "payload": payload, "attempt": 1})
        if self.priority_enabled:
            score = priority.score * (10**10) + int(time.time() * 1000)
            await self.redis.zadd(self._zset_key, {envelope: score})
        else:
            await self.redis.rpush(self._list_key, envelope)
        return job_id

    async def dequeue(self, *, timeout: int = 5) -> dict[str, Any] | None:
        """Return the full envelope: {"id": str, "payload": dict, "attempt": int}."""
        if self.priority_enabled:
            result = await self.redis.bzpopmin(self._zset_key, timeout=timeout)
            if result is None:
                return None
            _, raw, _ = result
            envelope = json.loads(raw)
        else:
            raw = await self.redis.blpop(self._list_key, timeout=timeout)
            if raw is None:
                return None
            _, value = raw
            envelope = json.loads(value)
        envelope.setdefault("attempt", 1)
        return envelope

    async def nack(self, envelope: dict[str, Any], *, error: str) -> None:
        """Re-enqueue with attempt incremented (retry)."""
        new_envelope = {**envelope, "attempt": envelope.get("attempt", 1) + 1, "last_error": error}
        await self.redis.rpush(self._list_key, json.dumps(new_envelope))

    async def to_dlq(self, envelope: dict[str, Any], *, error: str) -> None:
        """Move to the dead-letter queue for this queue."""
        entry = {**envelope, "last_error": error}
        await self.redis.rpush(self._dlq_key, json.dumps(entry))

    async def depth(self) -> int:
        if self.priority_enabled:
            return int(await self.redis.zcard(self._zset_key))
        return int(await self.redis.llen(self._list_key))
