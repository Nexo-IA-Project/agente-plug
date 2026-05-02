import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from shared.adapters.clock.system_clock import FrozenClock
from shared.application.scheduler.runner import SchedulerRunner
from shared.domain.entities.scheduled_job import JobStatus, JobType, ScheduledJob


async def test_runner_executes_due_job() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FrozenClock(now)

    job = ScheduledJob(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        job_type=JobType.IDLE_PING,
        payload={"stage": "ping"},
        run_at=now,
        status=JobStatus.PENDING,
    )
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[job])
    repo.mark_executed = AsyncMock()

    handler = AsyncMock()

    runner = SchedulerRunner(repo=repo, clock=clock, handlers={JobType.IDLE_PING: handler})
    processed = await runner.tick()

    assert processed == 1
    handler.assert_awaited_once_with(job)
    repo.mark_executed.assert_awaited_once_with(job_id=job.id, at=now)


async def test_runner_returns_zero_when_no_due_jobs() -> None:
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[])
    clock = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    runner = SchedulerRunner(repo=repo, clock=clock, handlers={})
    assert await runner.tick() == 0
