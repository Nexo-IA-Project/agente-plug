"""Integration tests for /admin/platform-config endpoints.

Estratégia idêntica ao test_leads_router.py:
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
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import PlatformConfigModel
from shared.adapters.db.repositories.platform_config_repo import PlatformConfigRepository
from shared.adapters.kb.jwt_handler import create_access_token

_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"


# ──────────────────────────────────────────────────────────────
# Migrations no testcontainer (autouse)
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
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
def admin_token() -> str:
    return create_access_token(
        data={
            "sub": "admin@test.com",
            "account_id": str(uuid.uuid4()),
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
async def clean_config(db_session: AsyncSession) -> None:
    """Garante DB sem linha de platform_config antes de cada teste."""
    await db_session.execute(delete(PlatformConfigModel))
    await db_session.commit()


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
async def client(mock_settings: Any, patched_session_scope, clean_config):
    from main import app

    with (
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.platform_config.session_scope",
            new=patched_session_scope,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_get_returns_empty_when_not_configured(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get("/admin/platform-config", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["openai_api_key"] == ""
    assert body["openai_configured"] is False
    assert body["smtp"]["has_password"] is False
    assert body["smtp"]["host"] is None


@pytest.mark.integration
async def test_put_grava_openai_e_smtp(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    r = await client.put(
        "/admin/platform-config",
        headers=admin_headers,
        json={
            "openai_api_key": "sk-supersecret-12345",
            "smtp": {
                "host": "smtp.example.com",
                "port": 587,
                "use_tls": True,
                "username": "user@example.com",
                "password": "smtp-secret",
                "from_name": "NexoIA",
                "from_email": "no-reply@example.com",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # OpenAI mascarado, não em claro
    assert body["openai_configured"] is True
    assert body["openai_api_key"].startswith("sk-super")
    assert "supersecret" not in body["openai_api_key"]
    assert body["smtp"]["host"] == "smtp.example.com"
    assert body["smtp"]["has_password"] is True

    # Confere via repositório que cifrou (não armazenou em claro)
    repo = PlatformConfigRepository(db_session)
    cfg = await repo.get()
    assert cfg.openai_api_key != "sk-supersecret-12345"
    assert repo.decrypt(cfg.openai_api_key) == "sk-supersecret-12345"
    assert cfg.smtp_encrypted_password != "smtp-secret"
    assert repo.decrypt(cfg.smtp_encrypted_password) == "smtp-secret"
    assert cfg.smtp_host == "smtp.example.com"


@pytest.mark.integration
async def test_put_password_vazia_nao_zera(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    # Primeiro grava config com senha
    r1 = await client.put(
        "/admin/platform-config",
        headers=admin_headers,
        json={
            "openai_api_key": "sk-original",
            "smtp": {
                "host": "smtp.first.com",
                "port": 465,
                "use_tls": True,
                "username": "u@first.com",
                "password": "first-pass",
                "from_name": "NexoIA",
                "from_email": "from@first.com",
            },
        },
    )
    assert r1.status_code == 200, r1.text

    # Segundo PUT: senha vazia + openai vazio → NÃO devem zerar os valores existentes
    r2 = await client.put(
        "/admin/platform-config",
        headers=admin_headers,
        json={
            "openai_api_key": "",
            "smtp": {
                "host": "smtp.second.com",
                "port": 587,
                "use_tls": False,
                "username": "u@second.com",
                "password": "",
                "from_name": "NexoIA 2",
                "from_email": "from@second.com",
            },
        },
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["smtp"]["host"] == "smtp.second.com"  # campos não-secretos atualizam
    assert body["smtp"]["has_password"] is True  # senha preservada
    assert body["openai_configured"] is True  # openai preservado

    repo = PlatformConfigRepository(db_session)
    cfg = await repo.get()
    assert repo.decrypt(cfg.smtp_encrypted_password) == "first-pass"
    assert repo.decrypt(cfg.openai_api_key) == "sk-original"


@pytest.mark.integration
async def test_test_endpoint_returns_422_on_smtp_failure(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Sem SMTP configurado → SmtpNotConfiguredError vira 422 amigável."""
    r = await client.post(
        "/admin/platform-config/test",
        headers=admin_headers,
        json={"to": "dest@example.com"},
    )
    assert r.status_code == 422, r.text
    assert "SMTP test failed" in r.json()["detail"]
