from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.models import RefundCaseModel


class RefundCaseRepository:
    # Session lifecycle managed by caller (Unit of Work).
    # flush() sends SQL within current transaction; commit() is caller's responsibility.

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: RefundCase) -> None:
        model = RefundCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            student_email=case.student_email,
            student_cpf=case.student_cpf,
            refund_reason=case.refund_reason,
            days_since_purchase=case.days_since_purchase,
            within_deadline=case.within_deadline,
            is_duplicate_purchase=case.is_duplicate_purchase,
            offers_made=list(case.offers_made),
            offer_accepted=case.offer_accepted,
            refund_processed_this_turn=case.refund_processed_this_turn,
            status=case.status.value,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, case: RefundCase) -> None:
        model = await self._session.get(RefundCaseModel, case.id)
        if model is None:
            raise ValueError(f"RefundCase {case.id} not found")
        model.status = case.status.value
        model.purchase_id = case.purchase_id
        model.product_name = case.product_name
        model.student_cpf = case.student_cpf
        model.refund_reason = case.refund_reason
        model.days_since_purchase = case.days_since_purchase
        model.within_deadline = case.within_deadline
        model.is_duplicate_purchase = case.is_duplicate_purchase
        model.offers_made = list(case.offers_made)
        model.offer_accepted = case.offer_accepted
        model.refund_processed_this_turn = case.refund_processed_this_turn
        await self._session.flush()

    async def find_by_phone(self, *, account_id: int, phone: str) -> RefundCase | None:
        result = await self._session.execute(
            select(RefundCaseModel)
            .where(RefundCaseModel.account_id == account_id)
            .where(RefundCaseModel.contact_id == phone)
            .order_by(RefundCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    def _to_entity(self, model: RefundCaseModel) -> RefundCase:
        return RefundCase(
            id=str(model.id),
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            student_email=model.student_email,
            student_cpf=model.student_cpf,
            refund_reason=model.refund_reason,
            days_since_purchase=model.days_since_purchase,
            within_deadline=model.within_deadline,
            is_duplicate_purchase=model.is_duplicate_purchase,
            offers_made=list(model.offers_made or []),
            offer_accepted=model.offer_accepted,
            refund_processed_this_turn=model.refund_processed_this_turn,
            status=RefundCaseStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
