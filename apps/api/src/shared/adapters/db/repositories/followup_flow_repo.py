from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    FollowupEnrollmentModel,
    FollowupFlowModel,
    FollowupStepModel,
)
from shared.domain.entities.followup import FollowupFlow, FollowupStep


def _flow_to_entity(m: FollowupFlowModel) -> FollowupFlow:
    return FollowupFlow(
        id=m.id,
        account_id=m.account_id,
        course_id=m.course_id,
        name=m.name,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _step_to_entity(m: FollowupStepModel) -> FollowupStep:
    return FollowupStep(
        id=m.id,
        flow_id=m.flow_id,
        position=m.position,
        delay_from_purchase_hours=m.delay_from_purchase_hours,
        meta_template_name=m.meta_template_name,
        template_variables=dict(m.template_variables or {}),
        created_at=m.created_at,
        message_text=m.message_text,
    )


@dataclass
class FollowupFlowRepository:
    session: AsyncSession

    async def list_active_by_course(self, course_id: uuid.UUID) -> list[FollowupFlow]:
        stmt = select(FollowupFlowModel).where(
            FollowupFlowModel.course_id == course_id,
            FollowupFlowModel.is_active.is_(True),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_flow_to_entity(m) for m in rows]

    async def find_by_id(self, flow_id: uuid.UUID) -> FollowupFlow | None:
        model = await self.session.get(FollowupFlowModel, flow_id)
        return None if model is None else _flow_to_entity(model)

    async def get_steps(self, flow_id: uuid.UUID) -> list[FollowupStep]:
        result = await self.session.execute(
            select(FollowupStepModel)
            .where(FollowupStepModel.flow_id == flow_id)
            .order_by(FollowupStepModel.position)
        )
        return [_step_to_entity(m) for m in result.scalars().all()]

    async def list_flows(self, account_id: uuid.UUID) -> list[FollowupFlow]:
        result = await self.session.execute(
            select(FollowupFlowModel)
            .where(FollowupFlowModel.account_id == account_id)
            .order_by(FollowupFlowModel.created_at)
        )
        return [_flow_to_entity(m) for m in result.scalars().all()]

    async def create_flow(
        self,
        *,
        account_id: uuid.UUID,
        course_id: uuid.UUID,
        name: str,
        is_active: bool = True,
    ) -> FollowupFlow:
        now = datetime.now(UTC)
        model = FollowupFlowModel(
            id=uuid.uuid4(),
            account_id=account_id,
            course_id=course_id,
            name=name,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.flush()
        return _flow_to_entity(model)

    async def update_flow(
        self,
        flow_id: uuid.UUID,
        *,
        name: str | None = None,
        course_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> FollowupFlow | None:
        model = await self.session.get(FollowupFlowModel, flow_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if course_id is not None:
            model.course_id = course_id
        if is_active is not None:
            model.is_active = is_active
        model.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _flow_to_entity(model)

    async def delete_flow(self, flow_id: uuid.UUID) -> bool:
        model = await self.session.get(FollowupFlowModel, flow_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def create_step(
        self,
        *,
        flow_id: uuid.UUID,
        position: int,
        delay_from_purchase_hours: int,
        meta_template_name: str | None,
        template_variables: dict,
        message_text: str | None = None,
    ) -> FollowupStep:
        model = FollowupStepModel(
            id=uuid.uuid4(),
            flow_id=flow_id,
            position=position,
            delay_from_purchase_hours=delay_from_purchase_hours,
            meta_template_name=meta_template_name,
            template_variables=template_variables,
            message_text=message_text,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _step_to_entity(model)

    async def update_step(
        self,
        step_id: uuid.UUID,
        *,
        delay_from_purchase_hours: int | None = None,
        meta_template_name: str | None = None,
        template_variables: dict | None = None,
        position: int | None = None,
        message_text: str | None = None,
        clear_template: bool = False,
        clear_message_text: bool = False,
    ) -> FollowupStep | None:
        model = await self.session.get(FollowupStepModel, step_id)
        if model is None:
            return None
        if delay_from_purchase_hours is not None:
            model.delay_from_purchase_hours = delay_from_purchase_hours
        if meta_template_name is not None:
            model.meta_template_name = meta_template_name
        if clear_template:
            model.meta_template_name = None
        if template_variables is not None:
            model.template_variables = template_variables
        if position is not None:
            model.position = position
        if message_text is not None:
            model.message_text = message_text
        if clear_message_text:
            model.message_text = None
        await self.session.flush()
        await self.session.refresh(model)
        return _step_to_entity(model)

    async def delete_step(self, step_id: uuid.UUID) -> bool:
        model = await self.session.get(FollowupStepModel, step_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def get_step(self, step_id: uuid.UUID) -> FollowupStep | None:
        model = await self.session.get(FollowupStepModel, step_id)
        return None if model is None else _step_to_entity(model)

    async def stats_by_flows(
        self,
        *,
        account_id: uuid.UUID,
        flow_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, int]]:
        """Conta enrollments por status para cada flow_id em uma só query.

        Filtra por ``account_id`` para garantir tenant isolation — mesmo em
        single-tenant, evita vazamento se outros accounts vierem a existir.
        """
        if not flow_ids:
            return {}
        result = await self.session.execute(
            select(
                FollowupEnrollmentModel.flow_id,
                FollowupEnrollmentModel.status,
                func.count(FollowupEnrollmentModel.id),
            )
            .where(
                FollowupEnrollmentModel.account_id == account_id,
                FollowupEnrollmentModel.flow_id.in_(flow_ids),
            )
            .group_by(
                FollowupEnrollmentModel.flow_id,
                FollowupEnrollmentModel.status,
            )
        )
        out: dict[uuid.UUID, dict[str, int]] = {}
        for fid, st, n in result.all():
            out.setdefault(fid, {})[st] = int(n)
        return out
