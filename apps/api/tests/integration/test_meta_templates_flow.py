"""Integration test: fluxo end-to-end de Meta Templates.

Estratégia:
- Mocks externos: R2Storage e MetaTemplateClient (APIs pagas/externas)
- DB: session_scope substituído por AsyncMock (não tocamos DB real); repositórios
  e helpers que tocam DB são patcheados nos pontos de uso.
- Auth: JWT gerado inline com jwt_secret controlado
- Settings: patched via monkeypatch para injetar meta_app_id e jwt_secret de teste
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.kb.jwt_handler import create_access_token

# ──────────────────────────────────────────────────────────────
# Constantes de teste
# ──────────────────────────────────────────────────────────────
_JWT_SECRET = "test-secret-jwt-do-not-use-in-prod"
_ACCOUNT_ID = uuid.uuid4()


# ──────────────────────────────────────────────────────────────
# Fixtures helpers
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def admin_token() -> str:
    """JWT válido para o admin_token fixture padrão do projeto."""
    return create_access_token(
        data={"sub": "test@test.com", "account_id": str(_ACCOUNT_ID), "role": "admin"},
        secret=_JWT_SECRET,
        expire_minutes=60,
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def mock_settings():
    """Settings mínimos para os endpoints de meta-templates funcionarem."""
    settings = MagicMock()
    settings.jwt_secret = _JWT_SECRET
    settings.jwt_expire_minutes = 60
    settings.meta_app_id = "fake_app_id"
    settings.meta_waba_id = "fake_waba_id"
    settings.integration_credentials_key = "fake_key"
    settings.database_url = "postgresql+asyncpg://fake"
    settings.cors_origins = ["http://localhost:3000"]
    settings.cors_origin_regex = None
    return settings


@pytest.fixture
def fake_meta_client():
    """Mock do MetaTemplateClient com todos os métodos usados nos use cases."""
    client = AsyncMock()
    client.create_resumable_upload_session = AsyncMock(return_value="upload_session_id")
    client.upload_media_resumable = AsyncMock(return_value="4::MEDIA_HANDLE")
    # create_template retorna um MetaTemplate-like com .id e .status
    fake_meta_template = MagicMock()
    fake_meta_template.id = "meta_id_1"
    fake_meta_template.status = "PENDING"
    client.create_template = AsyncMock(return_value=fake_meta_template)
    client.list_templates = AsyncMock(return_value=[])
    client.delete_template = AsyncMock()
    return client


@pytest.fixture
def fake_r2():
    """Mock do R2Storage cobrindo upload, download e delete."""
    r2 = AsyncMock()
    obj = MagicMock()
    obj.url = "https://media.example.com/test.jpg"
    obj.object_key = f"accounts/{_ACCOUNT_ID}/templates/test.jpg"
    obj.size = 1024
    obj.sha256 = "abc123"
    obj.content_type = "image/jpeg"
    r2.upload = AsyncMock(return_value=obj)
    r2.download = AsyncMock(return_value=b"x" * 1024)
    r2.delete = AsyncMock()
    return r2


def _make_fake_template_model(
    *,
    account_id: UUID,
    name: str,
    media_url: str | None = None,
    media_object_key: str | None = None,
    media_kind: str | None = None,
) -> Any:
    """Cria um objeto fake que simula MetaTemplateModel."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.account_id = account_id
    m.name = name
    m.meta_template_id = "meta_id_1"
    m.category = "UTILITY"
    m.language = "pt_BR"
    m.components = []
    m.variables_schema = {}
    m.media_url = media_url
    m.media_object_key = media_object_key
    m.media_kind = media_kind
    m.status = "PENDING"
    m.rejection_reason = None
    m.last_synced_at = None
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_flow_upload_create_list_delete(
    admin_headers: dict[str, str],
    mock_settings: Any,
    fake_meta_client: Any,
    fake_r2: Any,
) -> None:
    """Fluxo completo: upload mídia → create → list → delete."""
    from main import app

    # Template fake que será "criado" no banco
    fake_template = _make_fake_template_model(
        account_id=_ACCOUNT_ID,
        name="test_int",
        media_url="https://media.example.com/test.jpg",
        media_object_key=f"accounts/{_ACCOUNT_ID}/templates/test.jpg",
        media_kind="IMAGE",
    )

    # Repo mock — cobre todos os métodos chamados pelos 3 use cases
    repo_mock = AsyncMock()
    repo_mock.create = AsyncMock(return_value=fake_template)
    repo_mock.list_by_account = AsyncMock(return_value=[fake_template])
    repo_mock.find_pending = AsyncMock(return_value=[])
    repo_mock.get = AsyncMock(return_value=fake_template)
    repo_mock.delete = AsyncMock()
    repo_mock.update_status = AsyncMock()

    @asynccontextmanager
    async def fake_session_scope():
        session = AsyncMock(spec=AsyncSession)
        yield session

    with (
        patch(
            "interface.http.routers.admin.meta_templates.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.meta_templates.R2Storage.from_settings",
            return_value=fake_r2,
        ),
        patch(
            "interface.http.routers.admin.meta_templates.R2Storage.from_settings_or_null",
            return_value=fake_r2,
        ),
        patch(
            "interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
            new=AsyncMock(return_value=(fake_meta_client, "waba_test", "fake_app_id")),
        ),
        patch(
            "interface.http.routers.admin.meta_templates._get_account_uuid",
            new=AsyncMock(return_value=_ACCOUNT_ID),
        ),
        patch(
            "interface.http.routers.admin.meta_templates.session_scope",
            new=fake_session_scope,
        ),
        patch(
            "interface.http.routers.admin.meta_templates._flow_usage_check",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "interface.http.routers.admin.meta_templates.MetaTemplateRepository",
            return_value=repo_mock,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Upload de mídia
            files = {"file": ("test.jpg", b"x" * 1024, "image/jpeg")}
            r = await ac.post(
                "/admin/meta-templates/upload-media",
                files=files,
                data={"kind": "IMAGE"},
                headers=admin_headers,
            )
            assert r.status_code == 201, f"upload-media falhou: {r.text}"
            uploaded = r.json()
            assert uploaded["media_url"] == "https://media.example.com/test.jpg"
            assert uploaded["media_kind"] == "IMAGE"

            # 2. Criar template
            r = await ac.post(
                "/admin/meta-templates",
                json={
                    "name": "test_int",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "components": [
                        {
                            "type": "HEADER",
                            "format": "IMAGE",
                            "example": {"header_handle": []},
                        },
                        {
                            "type": "BODY",
                            "text": "Olá {{1}}",
                            "example": {"body_text": [["Fabio"]]},
                        },
                    ],
                    "media_url": uploaded["media_url"],
                    "media_object_key": uploaded["media_object_key"],
                    "media_kind": uploaded["media_kind"],
                },
                headers=admin_headers,
            )
            assert r.status_code == 201, f"create template falhou: {r.text}"
            template = r.json()
            assert template["name"] == "test_int"
            assert template["status"] == "PENDING"

            # 3. Listar templates
            r = await ac.get("/admin/meta-templates", headers=admin_headers)
            assert r.status_code == 200, f"list templates falhou: {r.text}"
            templates_list = r.json()
            assert any(t["id"] == template["id"] for t in templates_list)

            # 4. Deletar template
            r = await ac.delete(
                f"/admin/meta-templates/{template['id']}",
                headers=admin_headers,
            )
            assert r.status_code == 204, f"delete template falhou: {r.text}"
            fake_meta_client.delete_template.assert_awaited()


@pytest.mark.asyncio
async def test_create_meta_failure_returns_502(
    admin_headers: dict[str, str],
    mock_settings: Any,
    fake_r2: Any,
) -> None:
    """Verifica que falha na Meta API retorna 502."""
    from main import app

    # Meta client que falha no upload resumable
    broken_meta = AsyncMock()
    broken_meta.create_resumable_upload_session = AsyncMock(side_effect=RuntimeError("meta down"))

    repo_mock = AsyncMock()
    repo_mock.get_by_name = AsyncMock(return_value=None)
    repo_mock.create = AsyncMock()

    @asynccontextmanager
    async def fake_session_scope():
        session = AsyncMock(spec=AsyncSession)
        yield session

    with (
        patch(
            "interface.http.routers.admin.meta_templates.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.deps.admin_auth.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "interface.http.routers.admin.meta_templates.R2Storage.from_settings",
            return_value=fake_r2,
        ),
        patch(
            "interface.http.routers.admin.meta_templates.R2Storage.from_settings_or_null",
            return_value=fake_r2,
        ),
        patch(
            "interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
            new=AsyncMock(return_value=(broken_meta, "waba_test", "fake_app_id")),
        ),
        patch(
            "interface.http.routers.admin.meta_templates._get_account_uuid",
            new=AsyncMock(return_value=_ACCOUNT_ID),
        ),
        patch(
            "interface.http.routers.admin.meta_templates.session_scope",
            new=fake_session_scope,
        ),
        patch(
            "interface.http.routers.admin.meta_templates.MetaTemplateRepository",
            return_value=repo_mock,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                "/admin/meta-templates",
                json={
                    "name": "test_fail",
                    "category": "UTILITY",
                    "language": "pt_BR",
                    "components": [
                        {
                            "type": "HEADER",
                            "format": "IMAGE",
                            "example": {"header_handle": []},
                        },
                        {
                            "type": "BODY",
                            "text": "Olá {{1}}",
                            "example": {"body_text": [["Fabio"]]},
                        },
                    ],
                    "media_url": "https://media.example.com/test.jpg",
                    "media_object_key": f"accounts/{_ACCOUNT_ID}/templates/test.jpg",
                    "media_kind": "IMAGE",
                },
                headers=admin_headers,
            )
            assert r.status_code == 502, f"esperado 502, recebido {r.status_code}: {r.text}"
            body = r.json()
            assert body["detail"]["code"] == "META_API_ERROR"
