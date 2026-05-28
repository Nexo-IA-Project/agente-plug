# tests/unit/interface/admin/test_auth_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _make_mock_session(return_user):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=return_user))
    )
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    """Integration-lite: real router, mocked DB and JWT."""
    from shared.adapters.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.id = "user-1"
    mock_user_model.email = "admin@test.com"
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.account_id = 1
    mock_user_model.role = "admin"
    mock_user_model.is_active = True
    mock_user_model.must_change_password = False
    mock_user_model.name = "Admin"
    mock_user_model.last_login_at = None

    with (
        patch("interface.http.routers.admin.auth.get_db") as mock_get_db,
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_session = _make_mock_session(mock_user_model)
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "correctpass", "account_id": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_in" in data


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_password():
    from shared.adapters.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.email = "admin@test.com"
    mock_user_model.account_id = 1
    mock_user_model.is_active = True
    mock_user_model.must_change_password = False
    mock_user_model.name = "Admin"
    mock_user_model.last_login_at = None

    with (
        patch("interface.http.routers.admin.auth.get_db") as mock_get_db,
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_session = _make_mock_session(mock_user_model)
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "wrongpass", "account_id": 1},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_401_when_user_not_found():
    with (
        patch("interface.http.routers.admin.auth.get_db") as mock_get_db,
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_session = _make_mock_session(None)
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "nobody@test.com", "password": "pass", "account_id": 1},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_403_when_user_inactive():
    from shared.adapters.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.id = "user-2"
    mock_user_model.email = "inactive@test.com"
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.account_id = 1
    mock_user_model.role = "admin"
    mock_user_model.is_active = False
    mock_user_model.must_change_password = False
    mock_user_model.name = "Inactive"
    mock_user_model.last_login_at = None

    with (
        patch("interface.http.routers.admin.auth.get_db") as mock_get_db,
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_session = _make_mock_session(mock_user_model)
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "inactive@test.com", "password": "correctpass", "account_id": 1},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_sets_httponly_cookie():
    from shared.adapters.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.id = "user-1"
    mock_user_model.email = "admin@test.com"
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.account_id = 1
    mock_user_model.role = "admin"
    mock_user_model.is_active = True
    mock_user_model.must_change_password = False
    mock_user_model.name = "Admin"
    mock_user_model.last_login_at = None

    with (
        patch("interface.http.routers.admin.auth.get_db") as mock_get_db,
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_session = _make_mock_session(mock_user_model)
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "correctpass", "account_id": 1},
        )
        assert response.status_code == 200
        # Cookie HttpOnly deve ser setado pelo servidor
        set_cookie = response.headers.get("set-cookie", "")
        assert "nexoia_token=" in set_cookie
        assert "httponly" in set_cookie.lower()


@pytest.mark.asyncio
async def test_logout_clears_cookie():
    app = _make_app()
    client = TestClient(app)
    response = client.post("/admin/auth/logout")
    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "")
    assert "nexoia_token" in set_cookie
