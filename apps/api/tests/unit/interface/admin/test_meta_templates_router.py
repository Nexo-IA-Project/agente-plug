from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI

    from interface.http.routers.admin.meta_templates import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _mock_auth_override():
    from interface.http.deps.admin_auth import AdminAuth

    auth = AdminAuth(account_id=1, user_email="a@b.com", user_role="admin")

    def _override():
        return auth

    return _override


@pytest.fixture
def client():
    app = _make_app()
    from interface.http.deps.admin_auth import require_admin

    app.dependency_overrides[require_admin] = _mock_auth_override()
    return TestClient(app)


def _make_template_record(**kwargs):
    """Cria um objeto fake de MetaTemplateModel para uso nos testes."""
    record = MagicMock()
    record.id = kwargs.get("id", uuid4())
    record.name = kwargs.get("name", "test_template")
    record.category = kwargs.get("category", "MARKETING")
    record.language = kwargs.get("language", "pt_BR")
    record.status = kwargs.get("status", "APPROVED")
    record.components = kwargs.get("components", [])
    record.media_url = kwargs.get("media_url", None)
    record.media_kind = kwargs.get("media_kind", None)
    record.rejection_reason = kwargs.get("rejection_reason", None)
    record.meta_template_id = kwargs.get("meta_template_id", "meta-123")
    from datetime import datetime
    record.created_at = kwargs.get("created_at", datetime(2024, 1, 1))
    return record


def test_list_templates_returns_empty_when_no_waba_id(client):
    """Sem WABA_ID configurado, retorna lista vazia em vez de 422 — UX para
    primeiro acesso antes do admin cadastrar credenciais Meta."""
    with (
        patch(
            "interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
            new_callable=AsyncMock,
        ) as mock_get,
        patch(
            "interface.http.routers.admin.meta_templates.session_scope",
        ) as mock_scope,
        patch(
            "interface.http.routers.admin.meta_templates.MetaTemplateRepository",
        ) as mock_repo_cls,
        patch(
            "interface.http.routers.admin.meta_templates.ListTemplates",
        ) as mock_list_cls,
    ):
        from shared.adapters.meta.template_client import MetaTemplateClient

        mock_client = AsyncMock(spec=MetaTemplateClient)
        mock_get.return_value = (mock_client, "")  # empty waba_id

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_scope.return_value = mock_session

        mock_list_instance = AsyncMock()
        mock_list_instance.execute = AsyncMock(return_value=[])
        mock_list_cls.return_value = mock_list_instance

        resp = client.get("/admin/meta-templates")

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_templates_returns_records(client):
    """Quando ListTemplates retorna registros, o endpoint serializa corretamente."""
    record = _make_template_record()

    with (
        patch(
            "interface.http.routers.admin.meta_templates._get_meta_client_and_waba",
            new_callable=AsyncMock,
        ) as mock_get,
        patch(
            "interface.http.routers.admin.meta_templates.session_scope",
        ) as mock_scope,
        patch(
            "interface.http.routers.admin.meta_templates.MetaTemplateRepository",
        ),
        patch(
            "interface.http.routers.admin.meta_templates.ListTemplates",
        ) as mock_list_cls,
    ):
        from shared.adapters.meta.template_client import MetaTemplateClient

        mock_client = AsyncMock(spec=MetaTemplateClient)
        mock_get.return_value = (mock_client, "waba-123")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_scope.return_value = mock_session

        mock_list_instance = AsyncMock()
        mock_list_instance.execute = AsyncMock(return_value=[record])
        mock_list_cls.return_value = mock_list_instance

        resp = client.get("/admin/meta-templates")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == record.name
    assert data[0]["status"] == record.status
