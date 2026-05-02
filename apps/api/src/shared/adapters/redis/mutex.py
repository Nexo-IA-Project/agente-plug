from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from redis.asyncio import Redis


class MutexAcquisitionError(RuntimeError):
    pass


_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


@dataclass
class RedisMutex:
    redis: Redis

    @asynccontextmanager
    async def acquire(
        self, *, key: str, ttl_seconds: int, timeout: float = 5.0, retry_delay: float = 0.05
    ):
        full_key = f"mutex:{key}"
        token = uuid.uuid4().hex
        deadline = asyncio.get_event_loop().time() + timeout
        acquired = False
        while True:
            acquired = bool(await self.redis.set(full_key, token, nx=True, ex=ttl_seconds))
            if acquired:
                break
            if asyncio.get_event_loop().time() >= deadline:
                raise MutexAcquisitionError(f"Could not acquire mutex {key} within {timeout}s")
            await asyncio.sleep(retry_delay)
        try:
            yield
        finally:
            await self.redis.eval(_RELEASE_SCRIPT, 1, full_key, token)
