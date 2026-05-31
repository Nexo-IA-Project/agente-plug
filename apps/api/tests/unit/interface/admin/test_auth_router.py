# tests/unit/interface/admin/test_auth_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


def _make_app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _view(account_id, role, is_owner=False, name="Co"):
    v = MagicMock()
    v.membership_id = str(uuid4())
    v.account_id = account_id
    v.account_name = name
    v.role = role
    v.is_owner = is_owner
    return v


def _patches(identity, member_views):
    """Mocks de sessão + repositórios no namespace do router."""
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    sess.commit = AsyncMock()

    ident_repo = MagicMock()
    ident_repo.get_by_email = AsyncMock(return_value=identity)
    ident_repo.touch_last_login = AsyncMock()

    memb_repo = MagicMock()
    memb_repo.list_active_by_identity = AsyncMock(return_value=member_views)

    return sess, ident_repo, memb_repo


@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    """Integration-lite: real router, mocked repos and JWT."""
    ident = Identity(
        email="admin@test.com",
        password_hash=jwt_handler.hash_password("correctpass"),
        name="Admin",
        must_change_password=False,
    )
    views = [_view(uuid4(), UserRole.ADMIN, is_owner=True)]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        client = TestClient(_make_app())
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "correctpass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert "access_token" in data
        assert "expires_in" in data


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_password():
    ident = Identity(
        email="admin@test.com",
        password_hash=jwt_handler.hash_password("correctpass"),
        name="Admin",
        must_change_password=False,
    )
    sess, ir, mr = _patches(ident, [_view(uuid4(), UserRole.ADMIN)])

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        client = TestClient(_make_app())
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "wrongpass"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_401_when_user_not_found():
    sess, ir, mr = _patches(None, [])

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        client = TestClient(_make_app())
        response = client.post(
            "/admin/auth/login",
            json={"email": "nobody@test.com", "password": "pass"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_403_when_user_inactive():
    ident = Identity(
        email="inactive@test.com",
        password_hash=jwt_handler.hash_password("correctpass"),
        name="Inactive",
        must_change_password=False,
        is_active=False,
    )
    sess, ir, mr = _patches(ident, [])

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        client = TestClient(_make_app())
        response = client.post(
            "/admin/auth/login",
            json={"email": "inactive@test.com", "password": "correctpass"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_sets_httponly_cookie():
    ident = Identity(
        email="admin@test.com",
        password_hash=jwt_handler.hash_password("correctpass"),
        name="Admin",
        must_change_password=False,
    )
    views = [_view(uuid4(), UserRole.ADMIN, is_owner=True)]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        client = TestClient(_make_app())
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "correctpass"},
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
