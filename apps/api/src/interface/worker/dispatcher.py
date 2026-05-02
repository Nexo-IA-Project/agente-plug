from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from shared.adapters.observability.logger import bind_context, get_logger

StopSignal = object()
log = get_logger(__name__)

Handler = Callable[..., Awaitable[None]]


@dataclass
class WorkerDispatcher:
    queue: object
    handlers: dict[str, Handler]
    max_concurrency: int = 50
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

        async def _run_job(msg: dict[str, object]) -> None:
            async with self._sem:
                kind = str(msg.get("kind", ""))
                payload = msg.get("payload", {})
                bind_context(job_kind=kind)
                handler = self.handlers.get(kind)
                if handler is None:
                    log.warning("dispatcher_no_handler", kind=kind)
                    return
                try:
                    await handler(payload)
                    log.info("dispatcher_handled", kind=kind)
                except Exception as e:
                    log.exception("dispatcher_handler_failed", kind=kind, error=str(e))

        async with asyncio.TaskGroup() as tg:
            while True:
                if stop and stop.is_set():
                    log.info("dispatcher_stop_requested")
                    break

                msg = await self.queue.dequeue(timeout=2)  # type: ignore[attr-defined]

                if msg is StopSignal:
                    break
                if msg is None:
                    continue

                tg.create_task(_run_job(msg))
                dispatched += 1
                if iterations is not None and dispatched >= iterations:
                    break
        # TaskGroup.__aexit__ waits for all running _run_job tasks here
        log.info("dispatcher_drained", dispatched=dispatched)
