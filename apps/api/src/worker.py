from __future__ import annotations

import asyncio
import signal

from interface.worker.dispatcher import WorkerDispatcher
from interface.worker.handlers.hubla_event import handle_hubla_event
from interface.worker.handlers.message import handle_message
from interface.worker.handlers.process_purchase import handle_process_purchase_webhook
from interface.worker.handlers.purchase import handle_purchase
from interface.worker.handlers.resync import handle_resync_flow
from interface.worker.handlers.scheduled import handle_scheduled
from interface.worker.scheduler import SchedulerLoop
from shared.adapters.clock.system_clock import SystemClock
from shared.adapters.db.queue import PostgresJobQueue
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import get_sessionmaker
from shared.adapters.observability.logger import configure_logging, get_logger
from shared.adapters.redis.client import get_redis
from shared.adapters.redis.mutex import RedisMutex
from shared.application.scheduler.runner import SchedulerRunner
from shared.config.settings import get_settings
from shared.domain.entities.scheduled_job import JobType, ScheduledJob

log = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log.info("worker_starting")

    redis = get_redis()
    queue = PostgresJobQueue(sessionmaker=get_sessionmaker())
    mutex = RedisMutex(redis)

    dispatcher = WorkerDispatcher(
        queue=queue,
        dlq=queue,
        handlers={
            "purchase": handle_purchase,
            "message": handle_message,
            "scheduled": handle_scheduled,
            "ProcessPurchaseWebhook": handle_process_purchase_webhook,
            "resync_flow": handle_resync_flow,
            "hubla_event": handle_hubla_event,
        },
    )

    async def _scheduled_handler(job: ScheduledJob) -> None:
        flat_payload = {
            "job_type": job.job_type.value,
            "account_id": str(job.account_id),
            "conversation_id": str(job.conversation_id) if job.conversation_id else "",
            **job.payload,
        }
        await handle_scheduled(flat_payload)

    runner = SchedulerRunner(
        repo=ScheduledJobRepository(get_sessionmaker()()),
        clock=SystemClock(),
        handlers=dict.fromkeys(JobType, _scheduled_handler),
    )

    scheduler_loop = SchedulerLoop(runner=runner, mutex=mutex, tick_seconds=10)

    stop = asyncio.Event()

    def _sigterm(*_: object) -> None:
        log.info("worker_sigterm_received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _sigterm)

    dispatcher_task = asyncio.create_task(dispatcher.run_forever(stop=stop))
    scheduler_task = asyncio.create_task(scheduler_loop.run_forever())
    stop_task = asyncio.create_task(stop.wait())

    _done, pending = await asyncio.wait(
        {dispatcher_task, scheduler_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
