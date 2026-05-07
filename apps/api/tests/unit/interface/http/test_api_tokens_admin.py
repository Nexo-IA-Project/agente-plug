from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.admin_auth import require_admin as _require_admin
from interface.http.routers.admin import api_tokens as tokens_router
from shared.adapters.db.models import ApiTokenModel


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(tokens_router.router, prefix="/admin")
    return app


def _auth_override() -> AdminAuth:
    return AdminAuth(account_id=1, user_email="admin@test.com", user_role="admin")


def _fake_token_model(name: str = "prod") -> ApiTokenModel:
    m = MagicMock(spec=ApiTokenModel)
    m.id = uuid.uuid4()
    m.name = name
    m.is_active = True
    m.created_at = datetime(2026, 5, 5, 12, 0, 0)
    m.last_used_at = None
    return m


def test_create_token_returns_token_value():
    app = _make_app()
    app.dependency_overrides[_require_admin] = _auth_override
    client = TestClient(app)

    fake_model = _fake_token_model("prod")
    with patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.create = AsyncMock(return_value=(fake_model, "nxia_abc123"))
            MockRepo.return_value = repo_instance

            r = client.post("/admin/api-tokens", json={"name": "prod"})

    assert r.status_code == 201
    data = r.json()
    assert data["raw_token"] == "nxia_abc123"
    assert data["name"] == "prod"
    assert data["is_active"] is True


def test_list_tokens_does_not_expose_token_value():
    app = _make_app()
    app.dependency_overrides[_require_admin] = _auth_override
    client = TestClient(app)

    with patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.list_all = AsyncMock(return_value=[_fake_token_model("prod")])
            MockRepo.return_value = repo_instance

            r = client.get("/admin/api-tokens")

    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert "token" not in items[0]
    assert items[0]["name"] == "prod"


def test_revoke_token_returns_204():
    app = _make_app()
    app.dependency_overrides[_require_admin] = _auth_override
    client = TestClient(app)
    token_id = str(uuid.uuid4())

    with patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.revoke = AsyncMock(return_value=True)
            MockRepo.return_value = repo_instance

            r = client.delete(f"/admin/api-tokens/{token_id}")

    assert r.status_code == 204


def test_revoke_token_returns_404_if_not_found():
    app = _make_app()
    app.dependency_overrides[_require_admin] = _auth_override
    client = TestClient(app)
    token_id = str(uuid.uuid4())

    with patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.revoke = AsyncMock(return_value=False)
            MockRepo.return_value = repo_instance

            r = client.delete(f"/admin/api-tokens/{token_id}")

    assert r.status_code == 404


def test_missing_auth_returns_401():
    app = _make_app()
    # No dependency override — _require_admin will run
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/admin/api-tokens", json={"name": "test"})
    assert r.status_code == 401
