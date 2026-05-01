from __future__ import annotations

from redis.asyncio import Redis

from nexoia.config.settings import get_settings


def create_redis_client(url: str | None = None) -> Redis:
    return Redis.from_url(
        url or get_settings().redis_url,
        decode_responses=True,
        encoding="utf-8",
    )


_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = create_redis_client()
    return _client
