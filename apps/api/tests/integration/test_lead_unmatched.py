"""Integration: SqlLeadRepository product-unmatched helpers.

Cobre set_product_unmatched / list_unmapped / count_unmapped_by_product sobre
Postgres real (testcontainers + alembic migrations). Mesmo pattern de fixtures
de test_scheduler_runner_commit.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.db.models import AccountModel, LeadModel
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    from shared.config.settings import get_settings

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


def _lead(
    *,
    lead_id: uuid.UUID,
    account_id: uuid.UUID,
    hubla_product_id: str,
    product_unmatched: bool,
    now: datetime,
    sub_suffix: str,
) -> LeadModel:
    return LeadModel(
        id=lead_id,
        account_id=account_id,
        hubla_subscription_id=f"sub-{sub_suffix}",
        contact_id=None,
        payer_phone="5511999999999",
        payer_name="Fulano",
        payer_email="fulano@example.com",
        payer_document=None,
        hubla_product_id=hubla_product_id,
        product_unmatched=product_unmatched,
        product_name=f"Produto {hubla_product_id}",
        offer_id=None,
        offer_name=None,
        amount_total_cents=None,
        amount_subtotal_cents=None,
        payment_method=None,
        subscription_status="active",
        utm_source=None,
        utm_medium=None,
        utm_campaign=None,
        utm_content=None,
        utm_term=None,
        session_ip=None,
        session_url=None,
        fbp=None,
        first_seen_at=now,
        activated_at=None,
        last_event_at=now,
        last_event_type="subscription.activated",
        created_at=now,
        updated_at=now,
    )


async def test_unmatched_repo_helpers(engine: AsyncEngine) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    account_id = uuid.uuid4()
    now = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)

    lead_x1 = uuid.uuid4()
    lead_x2 = uuid.uuid4()
    lead_y = uuid.uuid4()

    async with maker() as s:
        await s.execute(delete(LeadModel))
        await s.execute(delete(AccountModel))
        s.add(AccountModel(id=account_id, name="t"))
        s.add(
            _lead(
                lead_id=lead_x1,
                account_id=account_id,
                hubla_product_id="X",
                product_unmatched=True,
                now=now,
                sub_suffix="x1",
            )
        )
        s.add(
            _lead(
                lead_id=lead_x2,
                account_id=account_id,
                hubla_product_id="X",
                product_unmatched=True,
                now=now,
                sub_suffix="x2",
            )
        )
        s.add(
            _lead(
                lead_id=lead_y,
                account_id=account_id,
                hubla_product_id="Y",
                product_unmatched=False,
                now=now,
                sub_suffix="y",
            )
        )
        await s.commit()

    # list_unmapped → 1 grupo (X) com 2 leads afetados
    async with maker() as s:
        repo = SqlLeadRepository(session=s)
        groups = await repo.list_unmapped(account_id)
        assert len(groups) == 1
        assert groups[0]["hubla_product_id"] == "X"
        assert groups[0]["affected_leads"] == 2

    # count_unmapped_by_product
    async with maker() as s:
        repo = SqlLeadRepository(session=s)
        assert await repo.count_unmapped_by_product(account_id, "X") == 2
        assert await repo.count_unmapped_by_product(account_id, "Y") == 0

    # set_product_unmatched(False) num dos X → count cai pra 1
    async with maker() as s:
        repo = SqlLeadRepository(session=s)
        await repo.set_product_unmatched(lead_id=lead_x1, value=False)
        await s.commit()

    async with maker() as s:
        repo = SqlLeadRepository(session=s)
        assert await repo.count_unmapped_by_product(account_id, "X") == 1
