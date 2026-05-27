from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ContactModel
from shared.adapters.db.repositories.base import require_account_id
from shared.domain.entities.contact import Contact
from shared.domain.value_objects.phone import Phone


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

    async def find_by_id(self, contact_id: UUID) -> Contact | None:
        model = await self.session.get(ContactModel, contact_id)
        return _to_entity(model) if model else None

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
        """Insere ou atualiza contato de forma atômica via INSERT ... ON CONFLICT.

        Resolve race condition quando múltiplos jobs paralelos (ex: rajada de
        webhooks Hubla — subscription.created + activated + customer.member_added)
        tentam criar o mesmo contato.

        Atualiza apenas as colunas passadas com valor não-None — colunas omitidas
        preservam o valor existente em conflito.
        """
        require_account_id(account_id)
        clean_attrs = {k: v for k, v in attrs.items() if v is not None}

        stmt = pg_insert(ContactModel).values(
            id=uuid.uuid4(),
            account_id=account_id,
            phone=phone.e164,
            **clean_attrs,
        )

        update_cols = {k: stmt.excluded[k] for k in clean_attrs if hasattr(ContactModel, k)}
        if update_cols:
            update_cols["updated_at"] = func.now()
            stmt = stmt.on_conflict_do_update(
                index_elements=["account_id", "phone"],
                set_=update_cols,
            )
        else:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["account_id", "phone"],
            )
        stmt = stmt.returning(ContactModel)

        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        # ON CONFLICT DO NOTHING não retorna linha quando há conflito — refetch.
        if model is None:
            model = await self._fetch_model_by_phone(account_id=account_id, phone=phone)
            if model is None:
                raise RuntimeError("contact upsert returned no row and refetch failed")

        await self.session.flush()
        return _to_entity(model)

    async def _fetch_model_by_phone(self, *, account_id: UUID, phone: Phone) -> ContactModel | None:
        stmt = select(ContactModel).where(
            ContactModel.account_id == account_id,
            ContactModel.phone == phone.e164,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
