from __future__ import annotations

from redis.asyncio import Redis


class RedisRefundMutex:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _key(self, account_id: int, contact_id: str, product_id: str) -> str:
        return f"refund:mutex:{account_id}:{contact_id}:{product_id}"

    async def acquire(self, account_id: int, contact_id: str, product_id: str) -> bool:
        key = self._key(account_id, contact_id, product_id)
        result = await self._redis.set(key, "1", nx=True, ex=self._ttl)
        return result is not None

    async def release(self, account_id: int, contact_id: str, product_id: str) -> None:
        key = self._key(account_id, contact_id, product_id)
        await self._redis.delete(key)
