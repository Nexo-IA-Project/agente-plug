from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import factory

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
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
