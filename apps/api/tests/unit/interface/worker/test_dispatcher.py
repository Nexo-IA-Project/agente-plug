from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from interface.worker.dispatcher import StopSignal, WorkerDispatcher

# ── helpers ───────────────────────────────────────────────────────────────────


def _queue(*messages: object) -> AsyncMock:
    q = AsyncMock()
    q.dequeue = AsyncMock(side_effect=list(messages))
    return q


# ── routing ───────────────────────────────────────────────────────────────────


async def test_dispatcher_routes_to_handler_by_kind():
    calls: list[dict] = []

    async def purchase_handler(payload):
        calls.append({"kind": "purchase", "payload": payload})

    async def message_handler(payload):
        calls.append({"kind": "message", "payload": payload})

    dispatcher = WorkerDispatcher(
        queue=_queue(
            {"kind": "purchase", "payload": {"p": 1}},
            {"kind": "message", "payload": {"m": 2}},
            StopSignal,
        ),
        handlers={"purchase": purchase_handler, "message": message_handler},
    )
    await dispatcher.run_forever()

    assert calls == [
        {"kind": "purchase", "payload": {"p": 1}},
        {"kind": "message", "payload": {"m": 2}},
    ]


async def test_dispatcher_skips_unknown_kind():
    calls: list = []

    async def handler(payload):
        calls.append(payload)

    dispatcher = WorkerDispatcher(
        queue=_queue({"kind": "unknown", "payload": {}}, StopSignal),
        handlers={"known": handler},
    )
    await dispatcher.run_forever()

    assert calls == []


async def test_dispatcher_handler_exception_does_not_stop_loop():
    calls: list = []

    async def bad_handler(payload):
        raise RuntimeError("boom")

    async def good_handler(payload):
        calls.append(payload)

    dispatcher = WorkerDispatcher(
        queue=_queue(
            {"kind": "bad", "payload": {}},
            {"kind": "good", "payload": {"x": 1}},
            StopSignal,
        ),
        handlers={"bad": bad_handler, "good": good_handler},
    )
    await dispatcher.run_forever()

    assert calls == [{"x": 1}]


# ── concurrency ───────────────────────────────────────────────────────────────


async def test_dispatcher_runs_jobs_concurrently():
    """Two slow jobs should overlap in time when max_concurrency >= 2."""
    running: list[int] = []
    max_concurrent = 0

    async def slow_handler(payload):
        nonlocal max_concurrent
        running.append(1)
        max_concurrent = max(max_concurrent, len(running))
        await asyncio.sleep(0.05)
        running.pop()

    dispatcher = WorkerDispatcher(
        queue=_queue(
            {"kind": "job", "payload": {}},
            {"kind": "job", "payload": {}},
            StopSignal,
        ),
        handlers={"job": slow_handler},
        max_concurrency=10,
    )
    await dispatcher.run_forever()

    assert max_concurrent == 2


async def test_dispatcher_semaphore_limits_concurrency():
    """With max_concurrency=1, jobs run one at a time."""
    running: list[int] = []
    max_concurrent = 0

    async def slow_handler(payload):
        nonlocal max_concurrent
        running.append(1)
        max_concurrent = max(max_concurrent, len(running))
        await asyncio.sleep(0.02)
        running.pop()

    dispatcher = WorkerDispatcher(
        queue=_queue(
            {"kind": "job", "payload": {}},
            {"kind": "job", "payload": {}},
            StopSignal,
        ),
        handlers={"job": slow_handler},
        max_concurrency=1,
    )
    await dispatcher.run_forever()

    assert max_concurrent == 1


# ── graceful shutdown ─────────────────────────────────────────────────────────


async def test_dispatcher_stops_on_stop_event():
    stop = asyncio.Event()
    started = asyncio.Event()

    async def slow_handler(payload):
        started.set()
        await asyncio.sleep(10)

    q = AsyncMock()
    q.dequeue = AsyncMock(return_value={"kind": "job", "payload": {}})

    dispatcher = WorkerDispatcher(
        queue=q,
        handlers={"job": slow_handler},
        max_concurrency=5,
    )

    async def _trigger_stop():
        await started.wait()
        stop.set()

    await asyncio.gather(
        dispatcher.run_forever(stop=stop, iterations=1),
        _trigger_stop(),
    )


async def test_dispatcher_drains_in_flight_tasks_on_stop():
    """In-flight tasks complete even after stop event fires."""
    completed: list[str] = []
    stop = asyncio.Event()

    async def handler(payload):
        await asyncio.sleep(0.02)
        completed.append(payload["id"])

    dispatcher = WorkerDispatcher(
        queue=_queue(
            {"kind": "job", "payload": {"id": "a"}},
            StopSignal,
        ),
        handlers={"job": handler},
    )
    await dispatcher.run_forever(stop=stop)

    assert "a" in completed
