"""Integration tests for /admin/leads endpoints.

Estratégia idêntica ao test_products_router.py:
- DB real: Postgres via testcontainers + db_session fixture
- session_scope patcheado para usar a session do teste
- Auth: JWT gerado inline com jwt_secret de teste
- Settings: patcheado para injetar jwt_secret consistente
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    ContactModel,
    ConversationModel,
    LeadModel,
)
from shared.adapters.kb.jwt_handler import create_access_token

# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────
_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"


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
    # Reseta cache do resolver single-tenant para não reutilizar UUID de teste anterior
    from sqlalchemy import delete

    from shared.adapters.db.models import HublaEventModel
    from shared.config import single_tenant

    single_tenant.reset_cache()

    # Limpa dados de testes anteriores (DB compartilhado entre testes da sessão)
    await db_session.execute(delete(LeadModel))
    await db_session.execute(delete(HublaEventModel))
    await db_session.execute(delete(ConversationModel))
    await db_session.execute(delete(ContactModel))
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
            "interface.http.routers.admin.leads.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def _make_lead(account_id: uuid.UUID, **overrides) -> LeadModel:
    """Cria um LeadModel com defaults sensatos para testes."""
    now = datetime.now(UTC)
    defaults: dict = {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "hubla_subscription_id": f"sub-{uuid.uuid4().hex[:8]}",
        "payer_phone": "+5511999990000",
        "payer_name": "Lead Teste",
        "payer_email": "lead@test.com",
        "payer_document": None,
        "hubla_product_id": "prod-test",
        "product_name": "Produto Teste",
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
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return LeadModel(**defaults)


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_list_leads_returns_empty_when_no_leads(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get("/admin/leads", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 25


@pytest.mark.integration
async def test_list_leads_returns_seeded_lead(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    lead = _make_lead(seeded_account.id, payer_name="João Silva")
    db_session.add(lead)
    await db_session.flush()
    await db_session.commit()

    r = await client.get("/admin/leads", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(item["payer_name"] == "João Silva" for item in items)


@pytest.mark.integration
async def test_list_leads_filters_by_status(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    db_session.add(_make_lead(seeded_account.id, subscription_status="active"))
    db_session.add(_make_lead(seeded_account.id, subscription_status="refunded"))
    await db_session.flush()
    await db_session.commit()

    r = await client.get("/admin/leads?status=refunded", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(item["subscription_status"] == "refunded" for item in items)


@pytest.mark.integration
async def test_export_csv_returns_attachment(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    db_session.add(_make_lead(seeded_account.id, payer_name="Teste CSV", amount_total_cents=9700))
    await db_session.flush()
    await db_session.commit()

    r = await client.get("/admin/leads/export", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    text = r.text
    # UTF-8 BOM must be present for Excel to read accented chars (João, André) correctly
    assert text.startswith("﻿"), "CSV must start with UTF-8 BOM for Excel"
    # Header row present
    assert "nome" in text
    assert "Teste CSV" in text


@pytest.mark.integration
async def test_get_lead_returns_404_for_unknown(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get(f"/admin/leads/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404, r.text


@pytest.mark.integration
async def test_get_lead_returns_detail_with_events(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    lead = _make_lead(seeded_account.id)
    db_session.add(lead)
    await db_session.flush()
    await db_session.commit()

    r = await client.get(f"/admin/leads/{lead.id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(lead.id)
    assert body["payer_name"] == lead.payer_name
    assert "events" in body
    assert isinstance(body["events"], list)


@pytest.mark.integration
async def test_get_lead_returns_chatnexo_conversation_url_field(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    """O detail sempre expõe o campo chatnexo_conversation_url (mesmo None)."""
    lead = _make_lead(seeded_account.id)
    db_session.add(lead)
    await db_session.flush()
    await db_session.commit()

    r = await client.get(f"/admin/leads/{lead.id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "chatnexo_conversation_url" in body
    # Sem contact_id vinculado: URL deve ser None
    assert body["chatnexo_conversation_url"] is None


@pytest.mark.integration
async def test_get_lead_builds_chatnexo_conversation_url_from_integration(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    """Quando há contact + conversation + integration completa, monta a URL."""
    # Atualiza integration nas settings da account
    seeded_account.settings = {
        "integration": {
            "chatnexo_base_url": "https://chatnexo.com.br",
            "chatnexo_account_id": 5,
            "chatnexo_inbox_id": 111,
        }
    }
    await db_session.flush()

    contact = ContactModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        phone="+5511988887777",
        name="Lead com Conversa",
    )
    db_session.add(contact)
    await db_session.flush()

    now = datetime.now(UTC)
    conv = ConversationModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        contact_id=contact.id,
        chatnexo_conversation_id=16401,
        status="open",
        last_activity_at=now,
        window_expires_at=now,
        idle_state="none",
    )
    db_session.add(conv)
    await db_session.flush()

    lead = _make_lead(seeded_account.id, contact_id=contact.id, payer_phone=contact.phone)
    db_session.add(lead)
    await db_session.flush()
    await db_session.commit()

    r = await client.get(f"/admin/leads/{lead.id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chatnexo_conversation_url"] == (
        "https://chatnexo.com.br/app/accounts/5/inbox/111/conversations/16401"
    )


@pytest.mark.integration
async def test_utm_sources_suggest_returns_top_distinct(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    """Retorna até 10 valores distintos ordenados por frequência."""
    # facebook 3x, google 2x, tiktok 1x
    for _ in range(3):
        db_session.add(_make_lead(seeded_account.id, utm_source="facebook"))
    for _ in range(2):
        db_session.add(_make_lead(seeded_account.id, utm_source="google"))
    db_session.add(_make_lead(seeded_account.id, utm_source="tiktok"))
    await db_session.flush()
    await db_session.commit()

    res = await client.get("/admin/leads/utm-sources/suggest", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body, list)
    assert body[0] == "facebook"  # mais frequente
    assert "google" in body
    assert "tiktok" in body
    assert len(body) <= 10


@pytest.mark.integration
async def test_utm_sources_suggest_filters_by_q(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    """Filtra por substring case-insensitive."""
    db_session.add(_make_lead(seeded_account.id, utm_source="facebook"))
    db_session.add(_make_lead(seeded_account.id, utm_source="Facebook Ads"))
    db_session.add(_make_lead(seeded_account.id, utm_source="google"))
    await db_session.flush()
    await db_session.commit()

    res = await client.get("/admin/leads/utm-sources/suggest?q=face", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert all("face" in v.lower() for v in body)
    assert len(body) == 2


@pytest.mark.integration
async def test_list_leads_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_account: AccountModel,
    admin_headers: dict[str, str],
) -> None:
    for _ in range(5):
        db_session.add(_make_lead(seeded_account.id))
    await db_session.flush()
    await db_session.commit()

    r = await client.get("/admin/leads?page=1&page_size=2", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) <= 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 5
