from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI

    from interface.http.routers.admin.onboarding import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


@pytest.fixture
def client():
    app = _make_app()
    from interface.http.deps.admin_auth import AdminAuth, require_admin

    auth = AdminAuth(account_id=1, user_email="a@b.com", user_role="admin",
                     user_id="test-id", must_change_password=False)
    app.dependency_overrides[require_admin] = lambda: auth
    return TestClient(app)


def test_list_flows_returns_empty(client):
    fake_uuid = uuid4()

    with patch("interface.http.routers.admin.onboarding.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one=lambda: fake_uuid))
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "interface.http.routers.admin.onboarding.OnboardingFlowRepository"
            ) as MockFlowRepo,
            patch(
                "interface.http.routers.admin.onboarding.SqlProductRepository"
            ) as MockProductRepo,
        ):
            flow_instance = MockFlowRepo.return_value
            flow_instance.list_flows = AsyncMock(return_value=[])
            flow_instance.stats_by_flows = AsyncMock(return_value={})
            product_instance = MockProductRepo.return_value
            product_instance.find_by_id = AsyncMock(return_value=None)
            resp = client.get("/admin/onboarding/flows")

    assert resp.status_code == 200
    assert resp.json() == []


def test_reorder_flows_endpoint_was_removed(client):
    """Garantir que PATCH /admin/followup/flows/reorder não existe mais."""
    resp = client.patch("/admin/onboarding/flows/reorder", json={"flows": []})
    assert resp.status_code in (404, 405)
