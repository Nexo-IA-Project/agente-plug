from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
    LeadModel,
)
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão."""
    import os

    from shared.config.settings import get_settings

    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
async def _clean_db(db_session: AsyncSession) -> None:
    """Limpa tabelas relevantes antes de cada teste."""
    await db_session.execute(delete(LeadModel))
    await db_session.execute(delete(ConversationModel))
    await db_session.execute(delete(ContactModel))
    await db_session.execute(delete(AccountModel))
    await db_session.commit()


@pytest.mark.asyncio
async def test_find_by_id_includes_chatnexo_url_when_conversation_exists(
    db_session: AsyncSession,
):
    account = AccountModel(
        id=uuid4(),
        name="Test",
        settings={
            "integration": {
                "chatnexo_base_url": "https://chatnexo.com.br",
                "chatnexo_account_id": 5,
                "chatnexo_inbox_id": 111,
            }
        },
    )
    db_session.add(account)
    await db_session.flush()

    contact = ContactModel(id=uuid4(), account_id=account.id, phone="+5511999999999", name="X")
    now = datetime.now(UTC)
    conv = ConversationModel(
        id=uuid4(),
        account_id=account.id,
        contact_id=contact.id,
        chatnexo_conversation_id=16401,
        status="open",
        last_activity_at=now,
        window_expires_at=now,
    )
    db_session.add_all([contact, conv])
    await db_session.flush()

    lead = LeadModel(
        id=uuid4(),
        account_id=account.id,
        hubla_subscription_id="sub_1",
        contact_id=contact.id,
        payer_phone="+5511999999999",
        payer_name="X",
        payer_email="",
        hubla_product_id="prod_x",
        product_name="P",
        subscription_status="active",
        first_seen_at=now,
        last_event_at=now,
        last_event_type="subscription.activated",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    found = await repo.find_by_id(lead.id, account.id)

    assert found is not None
    assert found.chatnexo_conversation_url == (
        "https://chatnexo.com.br/app/accounts/5/inbox/111/conversations/16401"
    )


@pytest.mark.asyncio
async def test_find_by_id_url_is_none_when_no_conversation(
    db_session: AsyncSession,
):
    account = AccountModel(id=uuid4(), name="T", settings={})
    db_session.add(account)
    await db_session.flush()

    now = datetime.now(UTC)
    lead = LeadModel(
        id=uuid4(),
        account_id=account.id,
        hubla_subscription_id="sub_2",
        contact_id=None,
        payer_phone="",
        payer_name="",
        payer_email="",
        hubla_product_id="",
        product_name="",
        subscription_status="unknown",
        first_seen_at=now,
        last_event_at=now,
        last_event_type="lead.abandoned",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    found = await repo.find_by_id(lead.id, account.id)

    assert found is not None
    assert found.chatnexo_conversation_url is None


@pytest.mark.asyncio
async def test_find_by_id_url_is_none_when_chatnexo_base_url_is_empty(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Quando chatnexo_base_url for vazio (conta + env), find_by_id devolve URL None.

    AccountConfigRepository.get() aplica defaults vindos do settings/env, então
    chatnexo_account_id/inbox_id sempre vêm preenchidos (default 1). O único
    caminho real em que a URL fica None é base_url vazia em ambos os níveis.
    """
    from shared.config.settings import get_settings

    monkeypatch.setenv("CHATNEXO_BASE_URL", "")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    try:
        account = AccountModel(
            id=uuid4(),
            name="NoBase",
            settings={"integration": {}},  # sem chatnexo_base_url na conta
        )
        db_session.add(account)
        await db_session.flush()

        contact = ContactModel(id=uuid4(), account_id=account.id, phone="+5511988888888", name="Y")
        now = datetime.now(UTC)
        conv = ConversationModel(
            id=uuid4(),
            account_id=account.id,
            contact_id=contact.id,
            chatnexo_conversation_id=777,
            status="open",
            last_activity_at=now,
            window_expires_at=now,
        )
        db_session.add_all([contact, conv])
        await db_session.flush()

        lead = LeadModel(
            id=uuid4(),
            account_id=account.id,
            hubla_subscription_id="sub_no_base",
            contact_id=contact.id,
            payer_phone="+5511988888888",
            payer_name="Y",
            payer_email="",
            hubla_product_id="prod_y",
            product_name="P",
            subscription_status="active",
            first_seen_at=now,
            last_event_at=now,
            last_event_type="subscription.activated",
            created_at=now,
            updated_at=now,
        )
        db_session.add(lead)
        await db_session.commit()

        repo = SqlLeadRepository(session=db_session)
        found = await repo.find_by_id(lead.id, account.id)

        assert found is not None
        assert found.chatnexo_conversation_url is None
    finally:
        get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_paginate_filters_by_product_id(db_session: AsyncSession):
    """product_id filtra por hubla_product_id exato."""
    account = AccountModel(id=uuid4(), name="T", settings={})
    db_session.add(account)
    await db_session.flush()

    now = datetime.now(UTC)
    base_lead_kwargs: dict = {
        "account_id": account.id,
        "payer_phone": "",
        "payer_name": "",
        "payer_email": "",
        "product_name": "",
        "subscription_status": "active",
        "first_seen_at": now,
        "last_event_at": now,
        "last_event_type": "subscription.activated",
        "created_at": now,
        "updated_at": now,
    }
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s1",
            hubla_product_id="prod_abc",
            **base_lead_kwargs,
        )
    )
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s2",
            hubla_product_id="prod_xyz",
            **base_lead_kwargs,
        )
    )
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    items, total = await repo.paginate(account.id, product_id="prod_abc")
    assert total == 1
    assert items[0].hubla_product_id == "prod_abc"


@pytest.mark.asyncio
async def test_paginate_filters_utm_source_case_insensitive(db_session: AsyncSession):
    """utm_source filtra com ILIKE %substring%."""
    account = AccountModel(id=uuid4(), name="T", settings={})
    db_session.add(account)
    await db_session.flush()

    now = datetime.now(UTC)
    base_lead_kwargs: dict = {
        "account_id": account.id,
        "payer_phone": "",
        "payer_name": "",
        "payer_email": "",
        "hubla_product_id": "",
        "product_name": "",
        "subscription_status": "active",
        "first_seen_at": now,
        "last_event_at": now,
        "last_event_type": "subscription.activated",
        "created_at": now,
        "updated_at": now,
    }
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s1",
            utm_source="facebook",
            **base_lead_kwargs,
        )
    )
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s2",
            utm_source="Facebook Ads",
            **base_lead_kwargs,
        )
    )
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s3",
            utm_source="google",
            **base_lead_kwargs,
        )
    )
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    items, total = await repo.paginate(account.id, utm_source="FACEBOOK")
    assert total == 2  # facebook + Facebook Ads (case-insensitive)
    sources = sorted([i.utm_source for i in items if i.utm_source])
    assert sources == ["Facebook Ads", "facebook"]


@pytest.mark.asyncio
async def test_paginate_filters_by_date_range(db_session: AsyncSession):
    """date_from/date_to filtra por last_event_at."""
    account = AccountModel(id=uuid4(), name="T", settings={})
    db_session.add(account)
    await db_session.flush()

    now = datetime.now(UTC)
    base: dict = {
        "account_id": account.id,
        "payer_phone": "",
        "payer_name": "",
        "payer_email": "",
        "hubla_product_id": "",
        "product_name": "",
        "subscription_status": "active",
        "last_event_type": "subscription.activated",
        "created_at": now,
        "updated_at": now,
    }
    d1 = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
    d2 = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
    d3 = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s1",
            first_seen_at=d1,
            last_event_at=d1,
            **base,
        )
    )
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s2",
            first_seen_at=d2,
            last_event_at=d2,
            **base,
        )
    )
    db_session.add(
        LeadModel(
            id=uuid4(),
            hubla_subscription_id="s3",
            first_seen_at=d3,
            last_event_at=d3,
            **base,
        )
    )
    await db_session.commit()

    df = datetime(2026, 5, 27, 0, 0, tzinfo=UTC)
    dt = datetime(2026, 5, 27, 23, 59, 59, tzinfo=UTC)
    repo = SqlLeadRepository(session=db_session)
    items, total = await repo.paginate(account.id, date_from=df, date_to=dt)
    assert total == 1
    assert items[0].hubla_subscription_id == "s2"
