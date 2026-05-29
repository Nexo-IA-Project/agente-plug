from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from shared.domain.entities.scheduled_job import JobType, ScheduledJob

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ScheduledJobRepoProto(Protocol):
    async def pick_due_jobs(self, *, now: datetime, limit: int = 50) -> list[ScheduledJob]: ...
    async def mark_executed(self, *, job_id: UUID, at: datetime) -> None: ...


class ClockProto(Protocol):
    def now(self) -> datetime: ...


JobHandler = Callable[[ScheduledJob], Awaitable[None]]
RepoFactory = Callable[["AsyncSession"], ScheduledJobRepoProto]
SessionScopeFactory = Callable[[], AbstractAsyncContextManager["AsyncSession"]]


@dataclass
class SchedulerRunner:
    """Despacha scheduled_jobs vencidos, com UMA transação por tick.

    Cada tick abre uma ``session_scope`` nova (commit no exit, rollback em
    exceção) e constrói o repo dentro dela. O lock ``FOR UPDATE SKIP LOCKED``
    de ``pick_due_jobs`` permanece válido durante a execução dos handlers e é
    liberado no commit ao fim do tick.

    Importante: a sessão NÃO é reaproveitada entre ticks. Reaproveitar deixava
    a transação ``idle in transaction`` para sempre, segurando os locks das
    linhas e congelando o scheduler (bug corrigido).
    """

    repo_factory: RepoFactory
    clock: ClockProto
    handlers: dict[JobType, JobHandler]
    session_scope_factory: SessionScopeFactory

    async def tick(self, *, limit: int = 50) -> int:
        now = self.clock.now()
        async with self.session_scope_factory() as session:
            repo = self.repo_factory(session)
            due = await repo.pick_due_jobs(now=now, limit=limit)
            for job in due:
                handler = self.handlers.get(job.job_type)
                if handler is None:
                    continue
                await handler(job)
                await repo.mark_executed(job_id=job.id, at=now)
            return len(due)
        # exit do `async with` → session_scope faz COMMIT → libera os locks
