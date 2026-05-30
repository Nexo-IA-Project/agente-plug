"""Integration tests for /admin/unmapped-products endpoints (Task 7).

Estratégia idêntica ao test_leads_router.py:
- DB real: Postgres via testcontainers + db_session fixture
- session_scope patcheado para usar a session do teste
- Auth: JWT gerado inline com jwt_secret de teste
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
    HublaEventModel,
    JobQueueModel,
    LeadModel,
    ProductHublaAliasModel,
    ProductModel,
)
from shared.adapters.kb.jwt_handler import create_access_token

_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"
_UNMAPPED_HUBLA_ID = "hubla-prod-pendente"


# ──────────────────────────────────────────────────────────────
# Migrations no testcontainer (autouse)
# ──────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def admin_account_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def admin_token(admin_account_id: uuid.UUID) -> str:
    return create_access_token(
        data={
            "sub": "admin@test.com",
            "account_id": str(admin_account_id),
            "role": "admin",
        },
        secret=_JWT_SECRET,
        expire_minutes=60,
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def mock_settings() -> Any:
    settings = MagicMock()
    settings.jwt_secret = _JWT_SECRET
    settings.jwt_expire_minutes = 60
    settings.cors_origins = ["http://localhost:3000"]
    settings.cors_origin_regex = None
    settings.database_url = "postgresql+asyncpg://fake"
    return settings


@pytest.fixture
async def seeded_account(db_session: AsyncSession, admin_account_id: uuid.UUID) -> AccountModel:
    from sqlalchemy import delete

    from shared.config import single_tenant

    single_tenant.reset_cache()

    # Limpa dados de testes anteriores (DB compartilhado entre testes da sessão)
    await db_session.execute(delete(JobQueueModel))
    await db_session.execute(delete(ProductHublaAliasModel))
    await db_session.execute(delete(LeadModel))
    await db_session.execute(delete(HublaEventModel))
    await db_session.execute(delete(ConversationModel))
    await db_session.execute(delete(ContactModel))
    await db_session.execute(delete(ProductModel))
    await db_session.execute(delete(AccountModel))
    await db_session.commit()

    account = AccountModel(id=admin_account_id, name="T")
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()
    return account


@pytest.fixture
def patched_session_scope(db_session: AsyncSession):
    """Substitui session_scope para reutilizar a session do teste."""

    @asynccontextmanager
    async def _scope():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    return _scope


@pytest.fixture
async def client(
    seeded_account: AccountModel,
    mock_settings: Any,
    patched_session_scope,
):
    from main import app

    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.unmapped_products.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def _make_lead(account_id: uuid.UUID, **overrides) -> LeadModel:
    now = datetime.now(UTC)
    defaults: dict = {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "hubla_subscription_id": f"sub-{uuid.uuid4().hex[:8]}",
        "payer_phone": "+5511999990000",
        "payer_name": "Lead Pendente",
        "payer_email": "lead@test.com",
        "payer_document": None,
        "hubla_product_id": _UNMAPPED_HUBLA_ID,
        "product_name": "Produto Pendente",
        "offer_name": None,
        "amount_total_cents": None,
        "payment_method": None,
        "subscription_status": "active",
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
        "utm_term": None,
        "session_ip": None,
        "session_url": None,
        "fbp": None,
        "first_seen_at": now,
        "activated_at": now,
        "last_event_at": now,
        "last_event_type": "subscription.activated",
        "product_unmatched": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return LeadModel(**defaults)


def _make_event(account_id: uuid.UUID, **overrides) -> HublaEventModel:
    now = datetime.now(UTC)
    defaults: dict = {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "event_type": "subscription.activated",
        "hubla_subscription_id": f"sub-{uuid.uuid4().hex[:8]}",
        "hubla_product_id": _UNMAPPED_HUBLA_ID,
        "product_name": "Produto Pendente",
        "payer_phone": "+5511999990000",
        "payer_email": "lead@test.com",
        "payer_name": "Lead Pendente",
        "contact_id": None,
        "payload": {"type": "subscription.activated", "event": {}},
        "received_at": now,
        "processed_at": now,
    }
    defaults.update(overrides)
    return HublaEventModel(**defaults)


def _make_product(account_id: uuid.UUID, **overrides) -> ProductModel:
    now = datetime.now(UTC)
    defaults: dict = {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "name": "Produto Cadastrado",
        "hubla_id": "hubla-prod-cadastrado",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return ProductModel(**defaults)


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_list_unmapped_returns_grouped(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    db_session.add(_make_lead(seeded_account.id))
    db_session.add(_make_lead(seeded_account.id))
    # Lead casado não deve aparecer
    db_session.add(_make_lead(seeded_account.id, product_unmatched=False))
    await db_session.commit()

    r = await client.get("/admin/unmapped-products", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    groups = [g for g in body if g["hubla_product_id"] == _UNMAPPED_HUBLA_ID]
    assert len(groups) == 1
    assert groups[0]["affected_leads"] == 2
    assert groups[0]["product_name"] == "Produto Pendente"


@pytest.mark.integration
async def test_resolve_creates_alias(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    product = _make_product(seeded_account.id)
    db_session.add(product)
    db_session.add(_make_lead(seeded_account.id))
    await db_session.commit()

    r = await client.post(
        "/admin/unmapped-products/resolve",
        headers=admin_headers,
        json={"hubla_product_id": _UNMAPPED_HUBLA_ID, "product_id": str(product.id)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["affected_leads"] == 1

    alias = (
        await db_session.execute(
            select(ProductHublaAliasModel).where(
                ProductHublaAliasModel.account_id == seeded_account.id,
                ProductHublaAliasModel.hubla_id == _UNMAPPED_HUBLA_ID,
            )
        )
    ).scalar_one_or_none()
    assert alias is not None
    assert alias.product_id == product.id


@pytest.mark.integration
async def test_resolve_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    product = _make_product(seeded_account.id)
    db_session.add(product)
    await db_session.commit()

    payload = {"hubla_product_id": _UNMAPPED_HUBLA_ID, "product_id": str(product.id)}
    r1 = await client.post("/admin/unmapped-products/resolve", headers=admin_headers, json=payload)
    assert r1.status_code == 200, r1.text
    r2 = await client.post("/admin/unmapped-products/resolve", headers=admin_headers, json=payload)
    assert r2.status_code == 200, r2.text

    count = (
        await db_session.execute(
            select(func.count(ProductHublaAliasModel.id)).where(
                ProductHublaAliasModel.account_id == seeded_account.id,
                ProductHublaAliasModel.hubla_id == _UNMAPPED_HUBLA_ID,
            )
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.integration
async def test_reprocess_enqueues_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    # 3 leads pendentes (unmatched) + seus eventos correspondentes (mesmo
    # hubla_subscription_id). Estes DEVEM ser re-enfileirados.
    unmatched_subs = [f"sub-unmatched-{i}" for i in range(3)]
    for sub in unmatched_subs:
        db_session.add(_make_lead(seeded_account.id, hubla_subscription_id=sub))
        db_session.add(_make_event(seeded_account.id, hubla_subscription_id=sub))

    # Lead JÁ resolvido (product_unmatched=False) com mesmo hubla_product_id: seu
    # evento NÃO deve ser re-enfileirado.
    db_session.add(
        _make_lead(
            seeded_account.id,
            hubla_subscription_id="sub-matched",
            product_unmatched=False,
        )
    )
    db_session.add(_make_event(seeded_account.id, hubla_subscription_id="sub-matched"))

    # Evento de outro produto também não deve ser re-enfileirado
    db_session.add(
        _make_event(
            seeded_account.id,
            hubla_subscription_id="sub-other-product",
            hubla_product_id="outro-produto",
        )
    )
    await db_session.commit()

    r = await client.post(
        "/admin/unmapped-products/reprocess",
        headers=admin_headers,
        json={"hubla_product_id": _UNMAPPED_HUBLA_ID, "schedule_mode": "from_now"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["enqueued"] == 3

    jobs = (
        (await db_session.execute(select(JobQueueModel).where(JobQueueModel.kind == "hubla_event")))
        .scalars()
        .all()
    )
    assert len(jobs) == 3
    assert all(j.payload.get("_schedule_mode") == "from_now" for j in jobs)


@pytest.mark.integration
async def test_reprocess_default_schedule_mode_is_from_now(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    db_session.add(_make_lead(seeded_account.id, hubla_subscription_id="sub-default"))
    db_session.add(_make_event(seeded_account.id, hubla_subscription_id="sub-default"))
    await db_session.commit()

    r = await client.post(
        "/admin/unmapped-products/reprocess",
        headers=admin_headers,
        json={"hubla_product_id": _UNMAPPED_HUBLA_ID},
    )
    assert r.status_code == 200, r.text
    assert r.json()["enqueued"] == 1

    job = (
        await db_session.execute(select(JobQueueModel).where(JobQueueModel.kind == "hubla_event"))
    ).scalar_one()
    assert job.payload.get("_schedule_mode") == "from_now"
