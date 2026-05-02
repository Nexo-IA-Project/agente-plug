from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from shared.adapters.observability.logger import bind_context, get_logger

StopSignal = object()
log = get_logger(__name__)

Handler = Callable[..., Awaitable[None]]


@dataclass
class WorkerDispatcher:
    queue: object
    handlers: dict[str, Handler]
    max_concurrency: int = 50
    max_retries: int = 3
    base_delay: float = 1.0
    dlq: object = None  # DeadLetterQueue | None
    # semaphore is created lazily so it belongs to the correct event loop
    _sem: asyncio.Semaphore = field(init=False, repr=False, default=None)  # type: ignore[assignment]

    async def run_forever(
        self,
        *,
        stop: asyncio.Event | None = None,
        iterations: int | None = None,
    ) -> None:
        """Dequeue jobs and process them concurrently up to *max_concurrency*.

        Exits when:
        - StopSignal is dequeued
        - *stop* event is set (checked between dequeues)
        - *iterations* jobs have been dispatched (test escape hatch)

        On exit the TaskGroup waits for all in-flight tasks to finish before
        returning — this is the graceful shutdown guarantee.
        """
        self._sem = asyncio.Semaphore(self.max_concurrency)
        dispatched = 0

        async def _run_job(envelope: dict[str, Any]) -> None:
            inner: dict[str, Any] = dict(envelope.get("payload", {}))
            attempt = int(envelope.get("attempt", 1))
            kind = str(inner.get("kind", ""))
            payload: Any = inner.get("payload", {})

            bind_context(job_kind=kind, attempt=attempt)
            handler = self.handlers.get(kind)
            if handler is None:
                log.warning("dispatcher_no_handler", kind=kind)
                return

            error_msg: str | None = None
            try:
                async with self._sem:
                    await handler(payload)
                log.info("dispatcher_handled", kind=kind, attempt=attempt)
                return
            except Exception as exc:
                error_msg = str(exc)
                log.exception(
                    "dispatcher_handler_failed", kind=kind, attempt=attempt, error=error_msg
                )

            # Retry with exponential back-off or send to DLQ
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** (attempt - 1))
                log.info(
                    "dispatcher_retrying",
                    kind=kind,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                await self.queue.nack(envelope, error=error_msg)  # type: ignore[attr-defined]
            else:
                log.error(
                    "dispatcher_max_retries_exceeded", kind=kind, attempt=attempt, error=error_msg
                )
                if self.dlq is not None:
                    await self.queue.to_dlq(envelope, error=error_msg)  # type: ignore[attr-defined]

        async with asyncio.TaskGroup() as tg:
            while True:
                if stop and stop.is_set():
                    log.info("dispatcher_stop_requested")
                    break

                envelope = await self.queue.dequeue(timeout=2)  # type: ignore[attr-defined]

                if envelope is StopSignal:
                    break
                if envelope is None:
                    continue

                tg.create_task(_run_job(envelope))
                dispatched += 1
                if iterations is not None and dispatched >= iterations:
                    break
        # TaskGroup.__aexit__ waits for all running _run_job tasks here
        log.info("dispatcher_drained", dispatched=dispatched)
