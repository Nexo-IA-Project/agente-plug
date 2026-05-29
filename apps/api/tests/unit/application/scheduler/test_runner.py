import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from shared.adapters.clock.system_clock import FrozenClock
from shared.application.scheduler.runner import SchedulerRunner
from shared.domain.entities.scheduled_job import JobStatus, JobType, ScheduledJob


class _FakeScope:
    """session_scope fake: registra commit/rollback como o session_scope real.

    Commita ao sair sem exceção, faz rollback (e propaga) quando há exceção.
    """

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.session = object()

    @asynccontextmanager
    async def __call__(self):
        try:
            yield self.session
        except Exception:
            self.rolled_back = True
            raise
        else:
            self.committed = True


def _make_job() -> ScheduledJob:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ScheduledJob(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        job_type=JobType.IDLE_PING,
        payload={"stage": "ping"},
        run_at=now,
        status=JobStatus.PENDING,
    )


async def test_runner_executes_due_job() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job = _make_job()
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[job])
    repo.mark_executed = AsyncMock()
    handler = AsyncMock()
    scope = _FakeScope()

    runner = SchedulerRunner(
        repo_factory=lambda _session: repo,
        clock=FrozenClock(now),
        handlers={JobType.IDLE_PING: handler},
        session_scope_factory=scope,
    )
    processed = await runner.tick()

    assert processed == 1
    handler.assert_awaited_once_with(job)
    repo.mark_executed.assert_awaited_once_with(job_id=job.id, at=now)


async def test_runner_returns_zero_when_no_due_jobs() -> None:
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[])
    scope = _FakeScope()
    runner = SchedulerRunner(
        repo_factory=lambda _session: repo,
        clock=FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
        handlers={},
        session_scope_factory=scope,
    )
    assert await runner.tick() == 0


async def test_runner_commits_after_tick() -> None:
    """Regressão do leak: cada tick precisa COMMITAR a transação.

    Antes da correção a sessão era única e nunca commitava → transação ficava
    `idle in transaction` segurando os locks. Agora o session_scope commita.
    """
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job = _make_job()
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[job])
    repo.mark_executed = AsyncMock()
    scope = _FakeScope()

    runner = SchedulerRunner(
        repo_factory=lambda _session: repo,
        clock=FrozenClock(now),
        handlers={JobType.IDLE_PING: AsyncMock()},
        session_scope_factory=scope,
    )
    await runner.tick()

    assert scope.committed is True
    assert scope.rolled_back is False


async def test_runner_rolls_back_on_handler_error() -> None:
    """Se um handler lança, o tick faz rollback e propaga (não deixa lock preso)."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    job = _make_job()
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[job])
    repo.mark_executed = AsyncMock()
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    scope = _FakeScope()

    runner = SchedulerRunner(
        repo_factory=lambda _session: repo,
        clock=FrozenClock(now),
        handlers={JobType.IDLE_PING: handler},
        session_scope_factory=scope,
    )
    with pytest.raises(RuntimeError):
        await runner.tick()

    assert scope.rolled_back is True
    assert scope.committed is False


async def test_runner_builds_repo_from_tick_session() -> None:
    """O repo é construído a partir da sessão do scope do tick (sessão nova por tick)."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    repo = AsyncMock()
    repo.pick_due_jobs = AsyncMock(return_value=[])
    scope = _FakeScope()
    seen_sessions = []

    def _factory(session):
        seen_sessions.append(session)
        return repo

    runner = SchedulerRunner(
        repo_factory=_factory,
        clock=FrozenClock(now),
        handlers={},
        session_scope_factory=scope,
    )
    await runner.tick()

    assert seen_sessions == [scope.session]
