from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


def test_list_templates_returns_502_on_meta_error(client):
    with patch(
        "interface.http.routers.admin.meta_templates._get_client",
        new_callable=AsyncMock,
    ) as mock_get:
        from shared.adapters.meta.template_client import MetaTemplateClient

        mock_client = AsyncMock(spec=MetaTemplateClient)
        mock_client.list_templates.side_effect = Exception("meta down")
        mock_get.return_value = (mock_client, "waba-123")

        resp = client.get("/admin/meta-templates")

    assert resp.status_code == 502
    assert "Meta" in resp.json()["detail"]


def test_list_templates_returns_422_when_no_waba_id(client):
    with patch(
        "interface.http.routers.admin.meta_templates._get_client",
        new_callable=AsyncMock,
    ) as mock_get:
        from shared.adapters.meta.template_client import MetaTemplateClient

        mock_client = AsyncMock(spec=MetaTemplateClient)
        mock_get.return_value = (mock_client, "")  # empty waba_id

        resp = client.get("/admin/meta-templates")

    assert resp.status_code == 422
    assert "META_WABA_ID" in resp.json()["detail"]
