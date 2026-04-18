from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.infrastructure.db.models import ContactModel
from nexoia.infrastructure.db.repositories.base import require_account_id


@dataclass
class ContactFactsRepository:
    session: AsyncSession

    async def get_facts(self, *, account_id: UUID, contact_id: UUID) -> dict[str, Any]:
        require_account_id(account_id)
        stmt = select(ContactModel).where(
            ContactModel.account_id == account_id,
            ContactModel.id == contact_id,
        )
        model = (await self.session.execute(stmt)).scalar_one_or_none()
        return dict(model.long_term_facts or {}) if model else {}

    async def update_facts(
        self, *, account_id: UUID, contact_id: UUID, facts: dict[str, Any]
    ) -> None:
        require_account_id(account_id)
        stmt = select(ContactModel).where(
            ContactModel.account_id == account_id,
            ContactModel.id == contact_id,
        )
        model = (await self.session.execute(stmt)).scalar_one()
        model.long_term_facts = facts
        await self.session.flush()
