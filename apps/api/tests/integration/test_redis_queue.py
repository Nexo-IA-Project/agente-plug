import pytest
from redis.asyncio import Redis

from shared.adapters.redis.queue import PriorityQueue
from shared.domain.value_objects.priority import Priority


@pytest.mark.integration
async def test_queue_enqueue_dequeue_fifo_when_priority_disabled(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="jobs", priority_enabled=False)
    await queue.enqueue({"job": "a"}, priority=Priority.LOW)
    await queue.enqueue({"job": "b"}, priority=Priority.URGENT)

    first = await queue.dequeue(timeout=1)
    second = await queue.dequeue(timeout=1)

    assert first is not None
    assert first["payload"] == {"job": "a"}
    assert first["attempt"] == 1
    assert second is not None
    assert second["payload"] == {"job": "b"}


@pytest.mark.integration
async def test_queue_honors_priority_when_enabled(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="jobs_p", priority_enabled=True)
    await queue.enqueue({"job": "low"}, priority=Priority.LOW)
    await queue.enqueue({"job": "urgent"}, priority=Priority.URGENT)

    first = await queue.dequeue(timeout=1)
    assert first is not None
    assert first["payload"] == {"job": "urgent"}


@pytest.mark.integration
async def test_queue_nack_requeues_with_incremented_attempt(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="retry_q", priority_enabled=False)
    await queue.enqueue({"kind": "test", "payload": {"x": 1}})

    envelope = await queue.dequeue(timeout=1)
    assert envelope is not None
    assert envelope["attempt"] == 1

    await queue.nack(envelope, error="simulated failure")

    retried = await queue.dequeue(timeout=1)
    assert retried is not None
    assert retried["attempt"] == 2
    assert retried["payload"] == {"kind": "test", "payload": {"x": 1}}
    assert retried["last_error"] == "simulated failure"


@pytest.mark.integration
async def test_queue_to_dlq_moves_envelope(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="dlq_q", priority_enabled=False)
    await queue.enqueue({"kind": "job", "payload": {}})

    envelope = await queue.dequeue(timeout=1)
    assert envelope is not None

    await queue.to_dlq(envelope, error="unrecoverable")

    # original queue is now empty
    assert await queue.depth() == 0

    # DLQ has one entry
    raw = await redis_client.lpop("dlq:dlq_q")
    assert raw is not None
    import json

    entry = json.loads(raw)
    assert entry["last_error"] == "unrecoverable"


@pytest.mark.integration
async def test_queue_depth_reflects_pending_items(redis_client: Redis) -> None:
    queue = PriorityQueue(redis_client, name="depth_q", priority_enabled=False)
    assert await queue.depth() == 0
    await queue.enqueue({"kind": "a", "payload": {}})
    await queue.enqueue({"kind": "b", "payload": {}})
    assert await queue.depth() == 2
