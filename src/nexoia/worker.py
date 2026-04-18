from __future__ import annotations

import asyncio
import signal

from nexoia.application.scheduler.runner import SchedulerRunner
from nexoia.config.settings import get_settings
from nexoia.domain.entities.scheduled_job import JobType, ScheduledJob
from nexoia.infrastructure.clock.system_clock import SystemClock
from nexoia.infrastructure.db.repositories.scheduled_job import ScheduledJobRepository
from nexoia.infrastructure.db.session import get_sessionmaker
from nexoia.infrastructure.observability.logger import configure_logging, get_logger
from nexoia.infrastructure.redis.client import get_redis
from nexoia.infrastructure.redis.mutex import RedisMutex
from nexoia.infrastructure.redis.queue import PriorityQueue
from nexoia.interface.worker.dispatcher import WorkerDispatcher
from nexoia.interface.worker.handlers.message import handle_message
from nexoia.interface.worker.handlers.purchase import handle_purchase
from nexoia.interface.worker.handlers.scheduled import handle_scheduled
from nexoia.interface.worker.scheduler import SchedulerLoop

log = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log.info("worker_starting")

    redis = get_redis()
    queue = PriorityQueue(
        redis, name="jobs", priority_enabled=settings.enable_priority_queue
    )
    mutex = RedisMutex(redis)

    dispatcher = WorkerDispatcher(
        queue=queue,
        handlers={
            "purchase": handle_purchase,
            "message": handle_message,
            "scheduled": handle_scheduled,
        },
    )

    async def _scheduled_handler(job: ScheduledJob) -> None:
        await handle_scheduled({"job_type": job.job_type.value, "payload": job.payload})

    runner = SchedulerRunner(
        repo=ScheduledJobRepository(get_sessionmaker()()),
        clock=SystemClock(),
        handlers={jt: _scheduled_handler for jt in JobType},
    )

    scheduler_loop = SchedulerLoop(runner=runner, mutex=mutex, tick_seconds=10)

    stop = asyncio.Event()

    def _sigterm(*_: object) -> None:
        log.info("worker_sigterm_received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _sigterm)

    dispatcher_task = asyncio.create_task(dispatcher.run_forever())
    scheduler_task = asyncio.create_task(scheduler_loop.run_forever())
    stop_task = asyncio.create_task(stop.wait())

    done, pending = await asyncio.wait(
        {dispatcher_task, scheduler_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
