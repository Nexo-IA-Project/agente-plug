from __future__ import annotations

import asyncio
from dataclasses import dataclass

from nexoia.application.scheduler.runner import SchedulerRunner
from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


@dataclass
class SchedulerLoop:
    runner: SchedulerRunner
    mutex: object | None = None
    tick_seconds: float = 10.0

    async def run_forever(self, *, iterations: int | None = None) -> None:
        count = 0
        while True:
            try:
                if self.mutex is not None:
                    async with self.mutex.acquire(
                        key="scheduler-tick", ttl_seconds=30, timeout=0.1
                    ):
                        processed = await self.runner.tick()
                else:
                    processed = await self.runner.tick()
                if processed:
                    log.info("scheduler_tick", processed=processed)
            except Exception as e:  # noqa: BLE001
                log.exception("scheduler_tick_failed", error=str(e))

            count += 1
            if iterations and count >= iterations:
                return
            await asyncio.sleep(self.tick_seconds)
