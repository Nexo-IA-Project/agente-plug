import pytest
from redis.asyncio import Redis

from shared.adapters.redis.mutex import MutexAcquisitionError, RedisMutex


@pytest.mark.integration
async def test_mutex_acquires_and_releases(redis_client: Redis) -> None:
    mutex = RedisMutex(redis_client)
    async with mutex.acquire(key="job-x", ttl_seconds=5):
        pass


@pytest.mark.integration
async def test_mutex_blocks_concurrent_acquire(redis_client: Redis) -> None:
    mutex = RedisMutex(redis_client)
    async with mutex.acquire(key="job-y", ttl_seconds=10):
        with pytest.raises(MutexAcquisitionError):
            async with mutex.acquire(key="job-y", ttl_seconds=10, timeout=0.1):
                pass
