"""Integration test: router /admin/followup (CRUD flows + steps).

Estratégia idêntica a test_products_router.py:
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


@pytest.fixture(scope="session")
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


@pytest.fixture(autouse=True)
async def _purge_other_accounts(db_session: AsyncSession, admin_account_id: uuid.UUID) -> None:
    """Garante que o `admin_account_id` é a ÚNICA account no DB.

    O endpoint `_get_account_uuid` faz `SELECT id FROM accounts LIMIT 1`
    sem ORDER BY. Como tests anteriores podem ter deixado accounts
    residuais, removemos tudo o que não seja a nossa antes de cada teste.
    """
    from sqlalchemy import delete

    from shared.adapters.db.models import (
        ContactModel,
        FollowupEnrollmentModel,
        FollowupEnrollmentStepModel,
        FollowupStepModel,
        ScheduledJobModel,
    )

    # Limpar dependentes primeiro (FK)
    await db_session.execute(delete(ScheduledJobModel))
    await db_session.execute(delete(FollowupEnrollmentStepModel))
    await db_session.execute(delete(FollowupEnrollmentModel))
    await db_session.execute(delete(FollowupStepModel))
    await db_session.execute(delete(FollowupFlowModel))
    await db_session.execute(delete(ProductModel))
    await db_session.execute(delete(ContactModel))
    await db_session.execute(delete(AccountModel).where(AccountModel.id != admin_account_id))
    await db_session.commit()


@pytest.fixture
async def seeded_account(db_session: AsyncSession, admin_account_id: uuid.UUID) -> AccountModel:
    existing = await db_session.get(AccountModel, admin_account_id)
    if existing is not None:
        return existing
    account = AccountModel(id=admin_account_id, name="T")
    db_session.add(account)
    await db_session.flush()
    await db_session.commit()
    return account


@pytest.fixture
async def seeded_product(db_session: AsyncSession, seeded_account: AccountModel) -> ProductModel:
    from datetime import UTC, datetime

    product = ProductModel(
        id=uuid.uuid4(),
        account_id=seeded_account.id,
        name="Curso Padrão",
        hubla_id=f"curso-{uuid.uuid4().hex[:8]}",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.commit()
    return product


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
    db_session: AsyncSession,
):
    from main import app

    class _SessionWrapper:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncSession:
            return self._session

        async def __aexit__(self, *exc: object) -> None:
            return None

        def __getattr__(self, name: str) -> Any:
            return getattr(self._session, name)

    class _FakeSessionmaker:
        def __call__(self):
            return _SessionWrapper(db_session)

    fake_sessionmaker = _FakeSessionmaker()

    # fake_sessionmaker existe apenas para compatibilidade com PostgresJobQueue legado;
    # após o outbox pattern, _enqueue_resync_in_session usa a própria session.
    _ = fake_sessionmaker
    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.followup.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ──────────────────────────────────────────────────────────────
# Testes: flows
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_create_flow(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    resp = await client.post(
        "/admin/followup/flows",
        json={"name": "Welcome Flow", "product_id": str(seeded_product.id)},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Welcome Flow"
    assert data["is_active"] is True
    assert data["steps_count"] == 0
    assert data["product"]["id"] == str(seeded_product.id)
    assert data["product"]["name"] == seeded_product.name
    assert data["product"]["hubla_id"] == seeded_product.hubla_id


@pytest.mark.integration
async def test_create_flow_with_unknown_course_returns_404(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,  # garante account+migrations
) -> None:
    fake_product_id = uuid.uuid4()
    resp = await client.post(
        "/admin/followup/flows",
        json={"name": "X", "product_id": str(fake_product_id)},
        headers=admin_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.integration
async def test_list_flows_returns_course_and_steps_count(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    create = await client.post(
        "/admin/followup/flows",
        json={"name": "F1", "product_id": str(seeded_product.id)},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text

    resp = await client.get("/admin/followup/flows", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    item = next(it for it in items if it["name"] == "F1")
    assert item["steps_count"] == 0
    assert item["product"]["id"] == str(seeded_product.id)
    assert item["product"]["hubla_id"] == seeded_product.hubla_id


@pytest.mark.integration
async def test_update_flow(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    create = await client.post(
        "/admin/followup/flows",
        json={"name": "Old", "product_id": str(seeded_product.id)},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    fid = create.json()["id"]

    resp = await client.put(
        f"/admin/followup/flows/{fid}",
        json={"name": "New", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "New"
    assert body["is_active"] is False


@pytest.mark.integration
async def test_update_flow_with_unknown_course_returns_404(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    create = await client.post(
        "/admin/followup/flows",
        json={"name": "F-up", "product_id": str(seeded_product.id)},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    fid = create.json()["id"]
    resp = await client.put(
        f"/admin/followup/flows/{fid}",
        json={"product_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.integration
async def test_delete_flow(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    create = await client.post(
        "/admin/followup/flows",
        json={"name": "to-del", "product_id": str(seeded_product.id)},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    fid = create.json()["id"]
    resp = await client.delete(f"/admin/followup/flows/{fid}", headers=admin_headers)
    assert resp.status_code == 204, resp.text


@pytest.mark.integration
async def test_delete_nonexistent_flow_returns_404(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    resp = await client.delete(
        f"/admin/followup/flows/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.integration
async def test_reorder_flows_endpoint_removed(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_product: ProductModel,
) -> None:
    """O endpoint PATCH /admin/followup/flows/reorder foi REMOVIDO."""
    resp = await client.patch(
        "/admin/followup/flows/reorder",
        json={"flows": []},
        headers=admin_headers,
    )
    assert resp.status_code in (404, 405), resp.text


# ──────────────────────────────────────────────────────────────
# Testes: steps
# ──────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_flow(
    db_session: AsyncSession,
    seeded_product: ProductModel,
) -> FollowupFlowModel:
    flow = FollowupFlowModel(
        id=uuid.uuid4(),
        account_id=seeded_product.account_id,
        product_id=seeded_product.id,
        name="Flow X",
        is_active=True,
    )
    db_session.add(flow)
    await db_session.flush()
    await db_session.commit()
    return flow


@pytest.mark.integration
async def test_create_step_with_meta_template(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    resp = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_minutes": 24,
            "meta_template_name": "welcome_v1",
            "template_variables": {
                "1": {"source": "customer_name"},
                "2": {"source": "static", "value": "Olá"},
            },
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["meta_template_name"] == "welcome_v1"
    assert data["message_text"] is None
    assert data["template_variables"] == {
        "1": {"source": "customer_name"},
        "2": {"source": "static", "value": "Olá"},
    }


@pytest.mark.integration
async def test_create_step_with_message_text(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    resp = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_minutes": 0,
            "message_text": "Olá! Obrigado pela compra.",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["message_text"] == "Olá! Obrigado pela compra."
    assert data["meta_template_name"] is None


@pytest.mark.integration
async def test_create_step_with_both_template_and_text_returns_422(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    resp = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_minutes": 0,
            "meta_template_name": "x",
            "message_text": "y",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
async def test_create_step_with_neither_template_nor_text_returns_422(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    resp = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={"delay_from_purchase_minutes": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
async def test_create_step_with_invalid_static_binding_returns_422(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    resp = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_minutes": 0,
            "meta_template_name": "x",
            "template_variables": {"1": {"source": "static"}},  # falta value
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
async def test_update_step(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    create = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={
            "delay_from_purchase_minutes": 1,
            "meta_template_name": "x",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    sid = create.json()["id"]

    resp = await client.put(
        f"/admin/followup/flows/{seeded_flow.id}/steps/{sid}",
        json={
            "delay_from_purchase_minutes": 2,
            "template_variables": {"1": {"source": "product_name"}},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["delay_from_purchase_minutes"] == 2
    assert data["template_variables"] == {"1": {"source": "product_name"}}


@pytest.mark.integration
async def test_list_and_delete_step(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_flow: FollowupFlowModel,
) -> None:
    create = await client.post(
        f"/admin/followup/flows/{seeded_flow.id}/steps",
        json={"delay_from_purchase_minutes": 0, "message_text": "oi"},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    sid = create.json()["id"]

    listing = await client.get(
        f"/admin/followup/flows/{seeded_flow.id}/steps", headers=admin_headers
    )
    assert listing.status_code == 200, listing.text
    assert any(s["id"] == sid for s in listing.json())

    rm = await client.delete(
        f"/admin/followup/flows/{seeded_flow.id}/steps/{sid}", headers=admin_headers
    )
    assert rm.status_code == 204, rm.text
