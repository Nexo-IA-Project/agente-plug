from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from nexoia.domain.entities.scheduled_job import JobType, ScheduledJob


class ScheduledJobRepoProto(Protocol):
    async def pick_due_jobs(self, *, now: datetime, limit: int = 50) -> list[ScheduledJob]: ...
    async def mark_executed(self, *, job_id: UUID, at: datetime) -> None: ...


class ClockProto(Protocol):
    def now(self) -> datetime: ...


JobHandler = Callable[[ScheduledJob], Awaitable[None]]


@dataclass
class SchedulerRunner:
    repo: ScheduledJobRepoProto
    clock: ClockProto
    handlers: dict[JobType, JobHandler]

    async def tick(self, *, limit: int = 50) -> int:
        now = self.clock.now()
        due = await self.repo.pick_due_jobs(now=now, limit=limit)
        for job in due:
            handler = self.handlers.get(job.job_type)
            if handler is None:
                continue
            await handler(job)
            await self.repo.mark_executed(job_id=job.id, at=now)
        return len(due)
