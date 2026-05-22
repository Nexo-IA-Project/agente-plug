"""Integration test: router /admin/products (CRUD).

Estratégia:
- DB real: Postgres via testcontainers + db_session fixture
- session_scope patcheado para usar a session do teste
- Auth: JWT gerado inline com jwt_secret de teste
- Settings: patcheado para injetar jwt_secret consistente
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel,
    FollowupFlowModel,
    ProductModel,
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
    """Aplica alembic migrations no testcontainer Postgres uma vez por sessão.

    A fixture conftest do projeto não roda migrations automaticamente. O
    `migrations/env.py` lê a URL via `get_settings().database_url`, então
    sobrescrevemos `DATABASE_URL` antes de invocar o alembic e limpamos
    o cache de settings para releitura.
    """
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
            "interface.http.routers.admin.products.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def seed_product_with_flow(
    db_session: AsyncSession, seeded_account: AccountModel
) -> tuple[uuid.UUID, uuid.UUID]:
    """Cria produto + flow vinculado e retorna (product_id, flow_id)."""
    from datetime import UTC, datetime

    product = ProductModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        name="Produto Com Flow",
        hubla_id="produto-flow",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(product)
    await db_session.flush()

    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        product_id=product.id,
        name="Flow X",
        is_active=True,
    )
    db_session.add(flow)
    await db_session.flush()
    await db_session.commit()
    return product.id, flow.id


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_create_product(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.post(
        "/admin/products",
        json={"name": "Marketing 360", "hubla_id": "prod-mkt-360"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Marketing 360"
    assert data["hubla_id"] == "prod-mkt-360"
    assert data["is_active"] is True
    assert data["flow_count"] == 0


@pytest.mark.integration
async def test_create_duplicate_returns_409(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    body = {"name": "A", "hubla_id": "dup-1"}
    r1 = await client.post("/admin/products", json=body, headers=admin_headers)
    assert r1.status_code == 201, r1.text
    r2 = await client.post("/admin/products", json=body, headers=admin_headers)
    assert r2.status_code == 409, r2.text


@pytest.mark.integration
async def test_list_products(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    await client.post(
        "/admin/products",
        json={"name": "A", "hubla_id": "list-x1"},
        headers=admin_headers,
    )
    await client.post(
        "/admin/products",
        json={"name": "B", "hubla_id": "list-x2"},
        headers=admin_headers,
    )
    resp = await client.get("/admin/products", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 2
    assert all("flow_count" in it for it in items)


@pytest.mark.integration
async def test_update_product(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    create = await client.post(
        "/admin/products",
        json={"name": "Old", "hubla_id": "upd-x"},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    pid = create.json()["id"]
    resp = await client.put(
        f"/admin/products/{pid}",
        json={"name": "New"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "New"
    assert resp.json()["hubla_id"] == "upd-x"


@pytest.mark.integration
async def test_delete_product_with_flow_returns_409(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seed_product_with_flow: tuple[uuid.UUID, uuid.UUID],
) -> None:
    pid, _ = seed_product_with_flow
    resp = await client.delete(f"/admin/products/{pid}", headers=admin_headers)
    assert resp.status_code == 409, resp.text


@pytest.mark.integration
async def test_delete_product_no_flows_returns_204(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/admin/products",
        json={"name": "to-del", "hubla_id": "del-x"},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    pid = create.json()["id"]
    resp = await client.delete(f"/admin/products/{pid}", headers=admin_headers)
    assert resp.status_code == 204, resp.text


@pytest.mark.integration
async def test_update_nonexistent_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"/admin/products/{fake_id}",
        json={"name": "X"},
        headers=admin_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.integration
async def test_delete_nonexistent_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    fake_id = uuid.uuid4()
    resp = await client.delete(f"/admin/products/{fake_id}", headers=admin_headers)
    assert resp.status_code == 404, resp.text
