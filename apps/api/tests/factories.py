from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import factory

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
    ProductModel,
)


class AccountFactory(factory.Factory):
    class Meta:
        model = AccountModel

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Tenant {n}")


class ContactFactory(factory.Factory):
    class Meta:
        model = ContactModel

    id = factory.LazyFunction(uuid.uuid4)
    account_id = factory.LazyFunction(uuid.uuid4)
    phone = factory.Sequence(lambda n: f"+55119900{n:05d}")
    name = factory.Faker("name")


class ConversationFactory(factory.Factory):
    class Meta:
        model = ConversationModel

    id = factory.LazyFunction(uuid.uuid4)
    account_id = factory.LazyFunction(uuid.uuid4)
    contact_id = factory.LazyFunction(uuid.uuid4)
    chatnexo_conversation_id = factory.Sequence(lambda n: n + 1)
    status = "active"
    last_activity_at = factory.LazyFunction(lambda: datetime.now(UTC))
    window_expires_at = factory.LazyFunction(lambda: datetime.now(UTC) + timedelta(hours=24))


async def make_account(session, *, name: str = "Tenant Test") -> AccountModel:
    """Helper async para criar e persistir um Account no DB."""
    m = AccountModel(id=uuid.uuid4(), name=name)
    session.add(m)
    await session.flush()
    return m


async def make_product(
    session,
    *,
    account_id: uuid.UUID | None = None,
    name: str = "Produto Teste",
    hubla_id: str = "prod-test",
    is_active: bool = True,
) -> ProductModel:
    """Helper async para criar e persistir um Product no DB.

    Se ``account_id`` não for fornecido, cria um Account novo via ``make_account``.
    """
    if account_id is None:
        account = await make_account(session)
        account_id = account.id
    now = datetime.now(UTC)
    m = ProductModel(
        id=uuid.uuid4(),
        account_id=account_id,
        name=name,
        hubla_id=hubla_id,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(m)
    await session.flush()
    return m
