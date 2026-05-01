import pytest
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from shared.adapters.redis.dedup import RedisDedup


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as c:
        yield c


@pytest.fixture
async def redis_client(redis_container) -> Redis:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client = Redis.from_url(f"redis://{host}:{port}/0", decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.mark.integration
async def test_dedup_sets_first_time(redis_client: Redis) -> None:
    dedup = RedisDedup(redis_client)
    assert await dedup.try_mark(key="purchase:1", ttl_seconds=60) is True


@pytest.mark.integration
async def test_dedup_rejects_second_time(redis_client: Redis) -> None:
    dedup = RedisDedup(redis_client)
    await dedup.try_mark(key="purchase:2", ttl_seconds=60)
    assert await dedup.try_mark(key="purchase:2", ttl_seconds=60) is False
