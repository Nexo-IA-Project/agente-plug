"""Integration test: SchedulerRunner commita a transação por tick.

Regressão do incidente de produção: o runner usava UMA sessão criada no boot e
nunca commitava → a transação ficava `idle in transaction` segurando os locks
das linhas, congelando o scheduler. Este teste prova que após um tick o job é
visível como EXECUTED em uma sessão NOVA (i.e., a transação foi commitada).

Pattern de fixtures: testcontainers Postgres + alembic migrations (igual a
test_followup_enrollment_repo_v2.py).
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.clock.system_clock import FrozenClock
from shared.adapters.db.models import AccountModel, ScheduledJobModel
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.application.scheduler.runner import SchedulerRunner
from shared.domain.entities.scheduled_job import JobStatus, JobType


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    from shared.config.settings import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


def _scope_factory(engine: AsyncEngine):
    """Replica session_scope (commit no exit / rollback em exceção) sobre o
    engine de teste — sem depender do sessionmaker global."""
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    @asynccontextmanager
    async def _scope():
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _scope


async def test_tick_commits_executed_status_visible_in_new_session(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    account_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)

    # seed: account + 1 scheduled_job PENDING vencido
    async with maker() as s:
        await s.execute(delete(ScheduledJobModel))
        await s.execute(delete(AccountModel))
        s.add(AccountModel(id=account_id, name="t"))
        s.add(
            ScheduledJobModel(
                id=job_id,
                account_id=account_id,
                conversation_id=None,
                job_type=JobType.FOLLOWUP_STEP.value,
                payload={},
                run_at=now - timedelta(hours=1),
                status=JobStatus.PENDING.value,
            )
        )
        await s.commit()

    runner = SchedulerRunner(
        repo_factory=lambda session: ScheduledJobRepository(session),
        clock=FrozenClock(now),
        handlers={JobType.FOLLOWUP_STEP: AsyncMock()},
        session_scope_factory=_scope_factory(engine),
    )

    processed = await runner.tick()
    assert processed == 1

    # Sessão NOVA enxerga EXECUTED → prova que o tick commitou (antes do fix: PENDING).
    async with maker() as verify:
        row = await verify.get(ScheduledJobModel, job_id)
        assert row is not None
        assert row.status == JobStatus.EXECUTED.value
        assert row.executed_at is not None

    # 2º tick não acha nada e não trava.
    assert await runner.tick() == 0


async def test_tick_rolls_back_when_handler_fails(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    account_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)

    async with maker() as s:
        await s.execute(delete(ScheduledJobModel))
        await s.execute(delete(AccountModel))
        s.add(AccountModel(id=account_id, name="t"))
        s.add(
            ScheduledJobModel(
                id=job_id,
                account_id=account_id,
                conversation_id=None,
                job_type=JobType.FOLLOWUP_STEP.value,
                payload={},
                run_at=now - timedelta(hours=1),
                status=JobStatus.PENDING.value,
            )
        )
        await s.commit()

    runner = SchedulerRunner(
        repo_factory=lambda session: ScheduledJobRepository(session),
        clock=FrozenClock(now),
        handlers={JobType.FOLLOWUP_STEP: AsyncMock(side_effect=RuntimeError("boom"))},
        session_scope_factory=_scope_factory(engine),
    )

    with pytest.raises(RuntimeError):
        await runner.tick()

    # rollback → job continua PENDING (mark_executed não persistiu).
    async with maker() as verify:
        row = await verify.get(ScheduledJobModel, job_id)
        assert row is not None
        assert row.status == JobStatus.PENDING.value
