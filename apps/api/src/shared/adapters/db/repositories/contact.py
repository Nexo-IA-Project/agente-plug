from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.entities.contact import Contact
from shared.domain.value_objects.phone import Phone
from shared.adapters.db.models import ContactModel
from shared.adapters.db.repositories.base import require_account_id


def _to_entity(model: ContactModel) -> Contact:
    return Contact(
        id=model.id,
        account_id=model.account_id,
        phone=Phone(e164=model.phone),
        name=model.name,
        email=model.email,
        long_term_facts=dict(model.long_term_facts or {}),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@dataclass
class ContactRepository:
    session: AsyncSession

    async def get_by_phone(self, *, account_id: UUID, phone: Phone) -> Contact | None:
        require_account_id(account_id)
        stmt = select(ContactModel).where(
            ContactModel.account_id == account_id,
            ContactModel.phone == phone.e164,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def upsert(self, *, account_id: UUID, phone: Phone, **attrs: object) -> Contact:
        require_account_id(account_id)
        existing = await self.get_by_phone(account_id=account_id, phone=phone)
        if existing:
            model_stmt = select(ContactModel).where(ContactModel.id == existing.id)
            model = (await self.session.execute(model_stmt)).scalar_one()
            for k, v in attrs.items():
                if v is not None and hasattr(model, k):
                    setattr(model, k, v)
            await self.session.flush()
            return _to_entity(model)

        new_model = ContactModel(
            id=uuid.uuid4(),
            account_id=account_id,
            phone=phone.e164,
            **{k: v for k, v in attrs.items() if v is not None},
        )
        self.session.add(new_model)
        await self.session.flush()
        return _to_entity(new_model)
