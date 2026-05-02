"""Unit tests for retry logic and DLQ in WorkerDispatcher (Task 7)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interface.worker.dispatcher import WorkerDispatcher

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_queue(envelopes: list) -> AsyncMock:
    """Mock queue that yields given envelopes then None forever."""
    call_count = 0

    async def _dequeue(**kwargs: object) -> object:
        nonlocal call_count
        if call_count < len(envelopes):
            val = envelopes[call_count]
            call_count += 1
            return val
        return None

    q = AsyncMock()
    q.dequeue = _dequeue
    q.nack = AsyncMock()
    q.to_dlq = AsyncMock()
    return q


def _envelope(kind: str = "test_job", attempt: int = 1, **extra: object) -> dict:
    return {
        "id": "job-1",
        "payload": {"kind": kind, "payload": {"x": 1}},
        "attempt": attempt,
        **extra,
    }


# ── successful dispatch ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handler_called_on_success() -> None:
    handler = AsyncMock()
    queue = _make_queue([_envelope()])

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={"test_job": handler},
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await dispatcher.run_forever(iterations=1)

    handler.assert_awaited_once_with({"x": 1})
    queue.nack.assert_not_called()
    queue.to_dlq.assert_not_called()


# ── retry on failure ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nack_called_on_first_failure() -> None:
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    envelope = _envelope(attempt=1)
    queue = _make_queue([envelope])

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={"test_job": handler},
        max_retries=3,
        base_delay=0.0,
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await dispatcher.run_forever(iterations=1)

    queue.nack.assert_awaited_once()
    call_args = queue.nack.call_args
    assert call_args[0][0]["id"] == "job-1"
    assert call_args[1]["error"] == "boom"
    queue.to_dlq.assert_not_called()


@pytest.mark.asyncio
async def test_nack_not_called_on_max_retry_attempt() -> None:
    handler = AsyncMock(side_effect=RuntimeError("still broken"))
    envelope = _envelope(attempt=3)
    queue = _make_queue([envelope])

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={"test_job": handler},
        max_retries=3,
        base_delay=0.0,
        dlq=None,
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await dispatcher.run_forever(iterations=1)

    queue.nack.assert_not_called()
    queue.to_dlq.assert_not_called()


@pytest.mark.asyncio
async def test_to_dlq_called_when_dlq_set_and_max_retries_exceeded() -> None:
    handler = AsyncMock(side_effect=RuntimeError("fatal"))
    envelope = _envelope(attempt=3)
    queue = _make_queue([envelope])
    dlq = MagicMock()

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={"test_job": handler},
        max_retries=3,
        base_delay=0.0,
        dlq=dlq,
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await dispatcher.run_forever(iterations=1)

    queue.to_dlq.assert_awaited_once()
    assert queue.to_dlq.call_args[1]["error"] == "fatal"
    queue.nack.assert_not_called()


# ── unknown kind ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_kind_skipped_without_retry() -> None:
    envelope = _envelope(kind="nonexistent")
    queue = _make_queue([envelope])

    dispatcher = WorkerDispatcher(queue=queue, handlers={})
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await dispatcher.run_forever(iterations=1)

    queue.nack.assert_not_called()
    queue.to_dlq.assert_not_called()


# ── exponential backoff delay ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backoff_delay_increases_with_attempt() -> None:
    handler = AsyncMock(side_effect=RuntimeError("err"))
    envelope_attempt1 = _envelope(attempt=1)
    queue = _make_queue([envelope_attempt1])

    sleep_calls: list[float] = []

    async def _fake_sleep(secs: float) -> None:
        sleep_calls.append(secs)

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={"test_job": handler},
        max_retries=3,
        base_delay=2.0,
    )
    with patch("asyncio.sleep", side_effect=_fake_sleep):
        await dispatcher.run_forever(iterations=1)

    # attempt=1 → delay = 2.0 * 2^0 = 2.0
    assert sleep_calls == [2.0]
