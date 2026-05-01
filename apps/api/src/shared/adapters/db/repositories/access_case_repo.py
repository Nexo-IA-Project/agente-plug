from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.entities.access_case import AccessCase, AccessCaseStatus
from shared.adapters.db.models import AccessCaseModel


class AccessCaseRepository:
    # Session lifecycle is managed by the caller (Unit of Work pattern).
    # flush() sends SQL within the current transaction; commit() is the caller's responsibility.

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: AccessCase) -> None:
        model = AccessCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            access_link=case.access_link,
            status=case.status.value,
            access_confirmed=case.access_confirmed,
            scheduled_d1_job_id=case.scheduled_d1_job_id,
            student_cpf=case.student_cpf,
            search_attempts=case.search_attempts,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, case: AccessCase) -> None:
        model = await self._session.get(AccessCaseModel, case.id)
        if model is None:
            raise ValueError(f"AccessCase {case.id} not found")
        model.status = case.status.value
        model.access_confirmed = case.access_confirmed
        model.access_link = case.access_link
        model.scheduled_d1_job_id = case.scheduled_d1_job_id
        model.student_cpf = case.student_cpf
        model.search_attempts = case.search_attempts
        await self._session.flush()

    async def get_by_purchase_id(self, purchase_id: str) -> AccessCase | None:
        result = await self._session.execute(
            select(AccessCaseModel).where(AccessCaseModel.purchase_id == purchase_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    def _to_entity(self, model: AccessCaseModel) -> AccessCase:
        return AccessCase(
            id=str(model.id),
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            access_link=model.access_link,
            status=AccessCaseStatus(model.status),
            access_confirmed=model.access_confirmed,
            scheduled_d1_job_id=model.scheduled_d1_job_id,
            student_cpf=model.student_cpf,
            search_attempts=model.search_attempts,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def update_status(
        self,
        *,
        case_id: str,
        status: AccessCaseStatus,
        search_attempts: int,
    ) -> None:
        model = await self._session.get(AccessCaseModel, case_id)
        if model is None:
            raise ValueError(f"AccessCase {case_id} not found")
        model.status = status.value
        model.search_attempts = search_attempts
        await self._session.flush()

    async def find_by_phone(
        self, *, account_id: int, phone: str
    ) -> AccessCase | None:
        result = await self._session.execute(
            select(AccessCaseModel)
            .where(AccessCaseModel.account_id == account_id)
            .where(AccessCaseModel.contact_id == phone)
            .order_by(AccessCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)
