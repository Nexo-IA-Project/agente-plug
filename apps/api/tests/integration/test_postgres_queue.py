from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.db.queue import PostgresJobQueue
from shared.domain.value_objects.priority import Priority

_DDL_UP = """
CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    attempt INTEGER NOT NULL DEFAULT 1,
    last_error TEXT,
    priority INTEGER NOT NULL DEFAULT 20,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS job_dlq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    attempt INTEGER NOT NULL,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@pytest.fixture
async def pg_queue(engine: AsyncEngine) -> PostgresJobQueue:
    async with engine.begin() as conn:
        for stmt in _DDL_UP.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    queue = PostgresJobQueue(sessionmaker=maker, poll_interval=0.05)
    yield queue
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE job_queue, job_dlq"))


@pytest.mark.integration
async def test_enqueue_dequeue_returns_envelope(pg_queue: PostgresJobQueue) -> None:
    job_id = await pg_queue.enqueue({"kind": "message", "payload": {"x": 1}})
    assert job_id

    envelope = await pg_queue.dequeue(timeout=1)
    assert envelope is not None
    assert envelope["id"] == job_id
    assert envelope["payload"] == {"kind": "message", "payload": {"x": 1}}
    assert envelope["attempt"] == 1


@pytest.mark.integration
async def test_dequeue_returns_none_when_empty(pg_queue: PostgresJobQueue) -> None:
    result = await pg_queue.dequeue(timeout=1)
    assert result is None


@pytest.mark.integration
async def test_fifo_order_same_priority(pg_queue: PostgresJobQueue) -> None:
    await pg_queue.enqueue({"kind": "job", "payload": {"n": 1}})
    await pg_queue.enqueue({"kind": "job", "payload": {"n": 2}})

    first = await pg_queue.dequeue(timeout=1)
    second = await pg_queue.dequeue(timeout=1)

    assert first is not None and first["payload"]["payload"]["n"] == 1
    assert second is not None and second["payload"]["payload"]["n"] == 2


@pytest.mark.integration
async def test_priority_ordering(pg_queue: PostgresJobQueue) -> None:
    await pg_queue.enqueue({"kind": "job", "payload": {"p": "low"}}, priority=Priority.LOW)
    await pg_queue.enqueue({"kind": "job", "payload": {"p": "urgent"}}, priority=Priority.URGENT)

    first = await pg_queue.dequeue(timeout=1)
    assert first is not None
    assert first["payload"]["payload"]["p"] == "urgent"


@pytest.mark.integration
async def test_nack_requeues_with_incremented_attempt(pg_queue: PostgresJobQueue) -> None:
    await pg_queue.enqueue({"kind": "test", "payload": {"x": 1}})

    envelope = await pg_queue.dequeue(timeout=1)
    assert envelope is not None
    assert envelope["attempt"] == 1

    await pg_queue.nack(envelope, error="boom")

    retried = await pg_queue.dequeue(timeout=1)
    assert retried is not None
    assert retried["attempt"] == 2
    assert retried["payload"] == {"kind": "test", "payload": {"x": 1}}


@pytest.mark.integration
async def test_to_dlq_inserts_into_dlq_table(
    pg_queue: PostgresJobQueue, engine: AsyncEngine
) -> None:
    await pg_queue.enqueue({"kind": "doomed", "payload": {"k": "v"}})
    envelope = await pg_queue.dequeue(timeout=1)
    assert envelope is not None

    await pg_queue.to_dlq(envelope, error="unrecoverable")

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT kind, last_error FROM job_dlq"))
        row = result.fetchone()
    assert row is not None
    assert row.kind == "doomed"
    assert row.last_error == "unrecoverable"


@pytest.mark.integration
async def test_depth_counts_pending(pg_queue: PostgresJobQueue) -> None:
    assert await pg_queue.depth() == 0
    await pg_queue.enqueue({"kind": "a", "payload": {}})
    await pg_queue.enqueue({"kind": "b", "payload": {}})
    assert await pg_queue.depth() == 2
    await pg_queue.dequeue(timeout=1)
    assert await pg_queue.depth() == 1
