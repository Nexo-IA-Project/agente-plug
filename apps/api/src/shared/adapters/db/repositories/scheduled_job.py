from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ScheduledJobModel
from shared.adapters.db.repositories.base import require_account_id
from shared.domain.entities.scheduled_job import JobStatus, JobType, ScheduledJob


def _to_entity(model: ScheduledJobModel) -> ScheduledJob:
    return ScheduledJob(
        id=model.id,
        account_id=model.account_id,
        conversation_id=model.conversation_id,
        job_type=JobType(model.job_type),
        payload=dict(model.payload or {}),
        run_at=model.run_at,
        status=JobStatus(model.status),
        attempts=model.attempts,
        correlation_id=model.correlation_id,
        created_at=model.created_at,
        executed_at=model.executed_at,
    )


@dataclass
class ScheduledJobRepository:
    session: AsyncSession

    async def schedule(
        self,
        *,
        account_id: UUID,
        conversation_id: UUID | None,
        job_type: JobType,
        payload: dict,
        run_at: datetime,
        correlation_id: str | None = None,
    ) -> ScheduledJob:
        require_account_id(account_id)
        model = ScheduledJobModel(
            id=uuid.uuid4(),
            account_id=account_id,
            conversation_id=conversation_id,
            job_type=job_type.value,
            payload=payload,
            run_at=run_at,
            status=JobStatus.PENDING.value,
            correlation_id=correlation_id,
        )
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model)

    async def pick_due_jobs(self, *, now: datetime, limit: int = 50) -> list[ScheduledJob]:
        stmt = (
            select(ScheduledJobModel)
            .where(
                ScheduledJobModel.status == JobStatus.PENDING.value,
                ScheduledJobModel.run_at <= now,
            )
            .order_by(ScheduledJobModel.run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def cancel_by_conversation(
        self,
        *,
        account_id: UUID,
        conversation_id: UUID,
        job_types: list[JobType] | None = None,
    ) -> int:
        require_account_id(account_id)
        stmt = (
            update(ScheduledJobModel)
            .where(
                ScheduledJobModel.account_id == account_id,
                ScheduledJobModel.conversation_id == conversation_id,
                ScheduledJobModel.status == JobStatus.PENDING.value,
            )
            .values(status=JobStatus.CANCELLED.value)
        )
        if job_types:
            stmt = stmt.where(ScheduledJobModel.job_type.in_([t.value for t in job_types]))
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def mark_executed(self, *, job_id: UUID, at: datetime) -> None:
        stmt = (
            update(ScheduledJobModel)
            .where(ScheduledJobModel.id == job_id)
            .values(status=JobStatus.EXECUTED.value, executed_at=at)
        )
        await self.session.execute(stmt)
