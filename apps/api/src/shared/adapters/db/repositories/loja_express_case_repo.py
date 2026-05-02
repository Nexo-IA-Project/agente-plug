from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import LojaExpressCaseModel
from shared.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


class LojaExpressCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: LojaExpressCase) -> None:
        model = LojaExpressCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            student_email=case.student_email,
            form_submitted=case.form_submitted,
            loja_entregue=case.loja_entregue,
            status=case.status.value,
            scheduled_job_d1_id=case.scheduled_job_d1_id,
            scheduled_job_d3_id=case.scheduled_job_d3_id,
            scheduled_job_d5_id=case.scheduled_job_d5_id,
            scheduled_job_d7_id=case.scheduled_job_d7_id,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, case: LojaExpressCase) -> None:
        model = await self._session.get(LojaExpressCaseModel, case.id)
        if model is None:
            raise ValueError(f"LojaExpressCase {case.id} not found")
        model.status = case.status.value
        model.form_submitted = case.form_submitted
        model.loja_entregue = case.loja_entregue
        model.scheduled_job_d1_id = case.scheduled_job_d1_id
        model.scheduled_job_d3_id = case.scheduled_job_d3_id
        model.scheduled_job_d5_id = case.scheduled_job_d5_id
        model.scheduled_job_d7_id = case.scheduled_job_d7_id
        await self._session.flush()

    async def find_by_purchase_context(
        self, account_id: int, contact_id: str
    ) -> LojaExpressCase | None:
        """Return the most recent active (not ENTREGUE) case for account+contact."""
        result = await self._session.execute(
            select(LojaExpressCaseModel)
            .where(LojaExpressCaseModel.account_id == account_id)
            .where(LojaExpressCaseModel.contact_id == contact_id)
            .where(LojaExpressCaseModel.status != LojaExpressCaseStatus.ENTREGUE.value)
            .order_by(LojaExpressCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    async def find_by_id(self, case_id: str) -> LojaExpressCase | None:
        model = await self._session.get(LojaExpressCaseModel, case_id)
        return None if model is None else self._to_entity(model)

    def _to_entity(self, model: LojaExpressCaseModel) -> LojaExpressCase:
        return LojaExpressCase(
            id=str(model.id),
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            student_email=model.student_email,
            form_submitted=model.form_submitted,
            loja_entregue=model.loja_entregue,
            status=LojaExpressCaseStatus(model.status),
            scheduled_job_d1_id=model.scheduled_job_d1_id,
            scheduled_job_d3_id=model.scheduled_job_d3_id,
            scheduled_job_d5_id=model.scheduled_job_d5_id,
            scheduled_job_d7_id=model.scheduled_job_d7_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
