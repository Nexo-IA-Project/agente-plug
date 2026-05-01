import pytest
from unittest.mock import AsyncMock
from nexoia.infrastructure.hubla.client import HublaClient
from nexoia.infrastructure.redis.refund_mutex import RedisRefundMutex


@pytest.mark.asyncio
async def test_hubla_client_get_purchase_raises_not_implemented():
    client = HublaClient()
    with pytest.raises(NotImplementedError):
        await client.get_purchase_by_email("a@b.com", 1)


@pytest.mark.asyncio
async def test_hubla_client_process_refund_raises_not_implemented():
    client = HublaClient()
    with pytest.raises(NotImplementedError):
        await client.process_refund("p1", "nao gostei")


@pytest.mark.asyncio
async def test_redis_refund_mutex_acquire_returns_true_when_key_free():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    result = await mutex.acquire(1, "5511999990000", "prod-1")
    assert result is True
    redis.set.assert_called_once_with(
        "refund:mutex:1:5511999990000:prod-1", "1", nx=True, ex=3600
    )


@pytest.mark.asyncio
async def test_redis_refund_mutex_acquire_returns_false_when_key_taken():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=None)  # SETNX failed — key exists
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    result = await mutex.acquire(1, "5511999990000", "prod-1")
    assert result is False


@pytest.mark.asyncio
async def test_redis_refund_mutex_release_deletes_key():
    redis = AsyncMock()
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    await mutex.release(1, "5511999990000", "prod-1")
    redis.delete.assert_called_once_with("refund:mutex:1:5511999990000:prod-1")
