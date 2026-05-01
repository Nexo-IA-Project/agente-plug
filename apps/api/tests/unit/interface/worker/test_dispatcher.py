from unittest.mock import AsyncMock

from interface.worker.dispatcher import StopSignal, WorkerDispatcher


async def test_dispatcher_routes_to_handler_by_kind():
    calls: list[dict] = []

    async def purchase_handler(payload):
        calls.append({"kind": "purchase", "payload": payload})

    async def message_handler(payload):
        calls.append({"kind": "message", "payload": payload})

    queue = AsyncMock()
    queue.dequeue = AsyncMock(
        side_effect=[
            {"kind": "purchase", "payload": {"p": 1}},
            {"kind": "message", "payload": {"m": 2}},
            StopSignal,
        ]
    )

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={
            "purchase": purchase_handler,
            "message": message_handler,
        },
    )
    await dispatcher.run_forever(iterations=3)

    assert calls == [
        {"kind": "purchase", "payload": {"p": 1}},
        {"kind": "message", "payload": {"m": 2}},
    ]
