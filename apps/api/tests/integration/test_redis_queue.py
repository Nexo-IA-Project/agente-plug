import pytest
from redis.asyncio import Redis

from shared.domain.value_objects.priority import Priority
from shared.adapters.redis.queue import PriorityQueue


@pytest.mark.integration
async def test_queue_enqueue_dequeue_fifo_when_priority_disabled(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="jobs", priority_enabled=False)
    await queue.enqueue({"job": "a"}, priority=Priority.LOW)
    await queue.enqueue({"job": "b"}, priority=Priority.URGENT)

    first = await queue.dequeue(timeout=1)
    second = await queue.dequeue(timeout=1)

    assert first == {"job": "a"}
    assert second == {"job": "b"}


@pytest.mark.integration
async def test_queue_honors_priority_when_enabled(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="jobs_p", priority_enabled=True)
    await queue.enqueue({"job": "low"}, priority=Priority.LOW)
    await queue.enqueue({"job": "urgent"}, priority=Priority.URGENT)

    first = await queue.dequeue(timeout=1)
    assert first == {"job": "urgent"}
