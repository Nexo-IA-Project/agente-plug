from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import CourseModel, FollowupFlowModel
from shared.domain.entities.course import Course


def _to_entity(m: CourseModel) -> Course:
    return Course(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        hubla_id=m.hubla_id,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@dataclass
class SqlCourseRepository:
    session: AsyncSession

    async def list_by_account(self, account_id: UUID) -> list[Course]:
        stmt = (
            select(CourseModel)
            .where(CourseModel.account_id == account_id)
            .order_by(CourseModel.name)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_entity(m) for m in rows]

    async def find_by_id(self, course_id: UUID) -> Course | None:
        m = await self.session.get(CourseModel, course_id)
        return _to_entity(m) if m else None

    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Course | None:
        stmt = select(CourseModel).where(
            CourseModel.account_id == account_id,
            CourseModel.hubla_id == hubla_id,
            CourseModel.is_active.is_(True),
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def create(
        self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True
    ) -> Course:
        now = datetime.now(UTC)
        m = CourseModel(
            id=uuid4(),
            account_id=account_id,
            name=name,
            hubla_id=hubla_id,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self.session.add(m)
        await self.session.flush()
        return _to_entity(m)

    async def update(
        self,
        course_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Course | None:
        m = await self.session.get(CourseModel, course_id)
        if m is None:
            return None
        if name is not None:
            m.name = name
        if hubla_id is not None:
            m.hubla_id = hubla_id
        if is_active is not None:
            m.is_active = is_active
        m.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _to_entity(m)

    async def delete(self, course_id: UUID) -> bool:
        m = await self.session.get(CourseModel, course_id)
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    async def count_flows(self, course_id: UUID) -> int:
        stmt = select(func.count(FollowupFlowModel.id)).where(
            FollowupFlowModel.course_id == course_id
        )
        return int((await self.session.execute(stmt)).scalar_one())
