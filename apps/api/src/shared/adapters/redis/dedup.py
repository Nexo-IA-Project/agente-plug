from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass
class RedisDedup:
    redis: Redis

    async def try_mark(self, *, key: str, ttl_seconds: int) -> bool:
        """Returns True if first time seeing key (owner). False if duplicate."""
        full_key = f"dedup:{key}"
        result = await self.redis.set(full_key, "1", nx=True, ex=ttl_seconds)
        return bool(result)
