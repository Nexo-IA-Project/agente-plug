from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    OnboardingEnrollmentModel,
    OnboardingFlowModel,
    OnboardingStepModel,
)
from shared.domain.entities.onboarding import OnboardingFlow, OnboardingStep


def _flow_to_entity(m: OnboardingFlowModel) -> OnboardingFlow:
    return OnboardingFlow(
        id=m.id,
        account_id=m.account_id,
        product_id=m.product_id,
        name=m.name,
        trigger_event_type=m.trigger_event_type,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _step_to_entity(m: OnboardingStepModel) -> OnboardingStep:
    return OnboardingStep(
        id=m.id,
        flow_id=m.flow_id,
        position=m.position,
        delay_from_purchase_minutes=m.delay_from_purchase_minutes,
        meta_template_name=m.meta_template_name,
        template_variables=dict(m.template_variables or {}),
        created_at=m.created_at,
        message_text=m.message_text,
    )


@dataclass
class OnboardingFlowRepository:
    session: AsyncSession

    async def list_active_by_product(self, product_id: uuid.UUID) -> list[OnboardingFlow]:
        stmt = select(OnboardingFlowModel).where(
            OnboardingFlowModel.product_id == product_id,
            OnboardingFlowModel.is_active.is_(True),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_flow_to_entity(m) for m in rows]

    async def list_active_by_product_and_event(
        self, product_id: uuid.UUID, event_type: str
    ) -> list[OnboardingFlow]:
        stmt = select(OnboardingFlowModel).where(
            OnboardingFlowModel.product_id == product_id,
            OnboardingFlowModel.trigger_event_type == event_type,
            OnboardingFlowModel.is_active.is_(True),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_flow_to_entity(m) for m in rows]

    async def find_by_id(self, flow_id: uuid.UUID) -> OnboardingFlow | None:
        model = await self.session.get(OnboardingFlowModel, flow_id)
        return None if model is None else _flow_to_entity(model)

    async def get_steps(self, flow_id: uuid.UUID) -> list[OnboardingStep]:
        result = await self.session.execute(
            select(OnboardingStepModel)
            .where(OnboardingStepModel.flow_id == flow_id)
            .order_by(OnboardingStepModel.position)
        )
        return [_step_to_entity(m) for m in result.scalars().all()]

    async def list_flows(self, account_id: uuid.UUID) -> list[OnboardingFlow]:
        result = await self.session.execute(
            select(OnboardingFlowModel)
            .where(OnboardingFlowModel.account_id == account_id)
            .order_by(OnboardingFlowModel.created_at)
        )
        return [_flow_to_entity(m) for m in result.scalars().all()]

    async def create_flow(
        self,
        *,
        account_id: uuid.UUID,
        product_id: uuid.UUID,
        name: str,
        trigger_event_type: str = "subscription.activated",
        is_active: bool = True,
    ) -> OnboardingFlow:
        now = datetime.now(UTC)
        model = OnboardingFlowModel(
            id=uuid.uuid4(),
            account_id=account_id,
            product_id=product_id,
            name=name,
            trigger_event_type=trigger_event_type,
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
        product_id: uuid.UUID | None = None,
        trigger_event_type: str | None = None,
        is_active: bool | None = None,
    ) -> OnboardingFlow | None:
        model = await self.session.get(OnboardingFlowModel, flow_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if product_id is not None:
            model.product_id = product_id
        if trigger_event_type is not None:
            model.trigger_event_type = trigger_event_type
        if is_active is not None:
            model.is_active = is_active
        model.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _flow_to_entity(model)

    async def delete_flow(self, flow_id: uuid.UUID) -> bool:
        model = await self.session.get(OnboardingFlowModel, flow_id)
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
        delay_from_purchase_minutes: int,
        meta_template_name: str | None,
        template_variables: dict,
        message_text: str | None = None,
    ) -> OnboardingStep:
        model = OnboardingStepModel(
            id=uuid.uuid4(),
            flow_id=flow_id,
            position=position,
            delay_from_purchase_minutes=delay_from_purchase_minutes,
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
        delay_from_purchase_minutes: int | None = None,
        meta_template_name: str | None = None,
        template_variables: dict | None = None,
        position: int | None = None,
        message_text: str | None = None,
        clear_template: bool = False,
        clear_message_text: bool = False,
    ) -> OnboardingStep | None:
        model = await self.session.get(OnboardingStepModel, step_id)
        if model is None:
            return None
        if delay_from_purchase_minutes is not None:
            model.delay_from_purchase_minutes = delay_from_purchase_minutes
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
        model = await self.session.get(OnboardingStepModel, step_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def find_steps_by_template_name(
        self, *, account_id: uuid.UUID, template_name: str
    ) -> list[tuple[OnboardingStep, OnboardingFlowModel]]:
        """Retorna steps que usam o template + o flow correspondente.

        Filtra por account_id pra tenant isolation (mesmo single-tenant).
        Usado pelo SyncMetaTemplates pra avisar/limpar quando um template
        é removido.
        """
        result = await self.session.execute(
            select(OnboardingStepModel, OnboardingFlowModel)
            .join(OnboardingFlowModel, OnboardingFlowModel.id == OnboardingStepModel.flow_id)
            .where(
                OnboardingFlowModel.account_id == account_id,
                OnboardingStepModel.meta_template_name == template_name,
            )
        )
        return [(_step_to_entity(step), flow) for step, flow in result.all()]

    async def get_step(self, step_id: uuid.UUID) -> OnboardingStep | None:
        model = await self.session.get(OnboardingStepModel, step_id)
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
                OnboardingEnrollmentModel.flow_id,
                OnboardingEnrollmentModel.status,
                func.count(OnboardingEnrollmentModel.id),
            )
            .where(
                OnboardingEnrollmentModel.account_id == account_id,
                OnboardingEnrollmentModel.flow_id.in_(flow_ids),
            )
            .group_by(
                OnboardingEnrollmentModel.flow_id,
                OnboardingEnrollmentModel.status,
            )
        )
        out: dict[uuid.UUID, dict[str, int]] = {}
        for fid, st, n in result.all():
            out.setdefault(fid, {})[st] = int(n)
        return out
