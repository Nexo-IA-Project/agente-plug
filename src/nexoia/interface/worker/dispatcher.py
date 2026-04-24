from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nexoia.infrastructure.observability.logger import bind_context, get_logger

StopSignal = object()
log = get_logger(__name__)

Handler = Callable[[dict], Awaitable[None]]


@dataclass
class WorkerDispatcher:
    queue: object
    handlers: dict[str, Handler]

    async def run_forever(self, *, iterations: int | None = None) -> None:
        count = 0
        while True:
            msg = await self.queue.dequeue(timeout=5)  # type: ignore[attr-defined]
            if msg is StopSignal:
                return
            if msg is None:
                if iterations and count >= iterations:
                    return
                continue

            kind = msg.get("kind", "")
            payload = msg.get("payload", {})
            bind_context(job_kind=kind)

            handler = self.handlers.get(kind)
            if handler is None:
                log.warning("dispatcher_no_handler", kind=kind)
                continue
            try:
                await handler(payload)
                log.info("dispatcher_handled", kind=kind)
            except Exception as e:
                log.exception("dispatcher_handler_failed", kind=kind, error=str(e))
            count += 1
            if iterations and count >= iterations:
                return
